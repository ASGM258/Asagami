"""
Embedding 提供方抽象

RAG 必须有 embedding 模型，而本项目的大模型（DeepSeek）**不提供 embedding 接口**，
因此单独抽一层，便于替换提供方：

- `DashScopeEmbeddings` —— 阿里云百炼（默认，OpenAI 兼容端点，需 DASHSCOPE_API_KEY）
- `LocalHashEmbeddings` —— 纯本地兜底，零依赖零密钥，**仅用于离线开发/自测**

本地兜底的取舍：它基于字符 n-gram 特征哈希，只能做词面匹配，语义检索能力明显弱于
bge-m3 / text-embedding-v3（问「压抑治愈番」找不到「致郁」类内容）。
生产请配置 DASHSCOPE_API_KEY 走真实模型。
"""

import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod

import requests

from app.config import Settings

logger = logging.getLogger(__name__)

# 本地兜底向量维度
LOCAL_EMBEDDING_DIM = 512


class BaseEmbeddings(ABC):
    """Embedding 提供方接口"""

    #: 提供方名称（日志/接口回显用）
    name: str = "base"

    #: 是否为真实语义模型（否则为本地兜底）
    semantic: bool = False

    @property
    def identity(self) -> str:
        """
        向量空间标识（用于 Chroma 集合命名）

        不同提供方 / 不同模型的向量维度与语义空间都不兼容，
        用一个稳定的标识把它们的向量分开存放，避免切换提供方时
        「Collection expecting embedding with dimension of 512, got 1024」。
        """
        return self.name

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化文档"""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """向量化查询"""


class DashScopeEmbeddings(BaseEmbeddings):
    """
    阿里云百炼（DashScope）embedding

    走 OpenAI 兼容端点，直接 HTTP 调用，避免额外引入 dashscope SDK。

    端点：https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
    常用模型：text-embedding-v3 / text-embedding-v4
    """

    name = "dashscope"
    semantic = True

    def __init__(self, api_key: str, model: str, base_url: str, timeout: int = 30) -> None:
        if not api_key:
            raise ValueError("DashScope embedding 需要配置 DASHSCOPE_API_KEY")
        self._api_key = api_key
        self._model = model
        self._url = base_url.rstrip("/") + "/embeddings"
        self._timeout = timeout

    def _call(self, texts: list[str]) -> list[list[float]]:
        # DashScope 单次请求对批量条数有限制，分批提交
        batch_size = 10
        vectors: list[list[float]] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                response = requests.post(
                    self._url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self._model, "input": batch},
                    timeout=self._timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                raise RuntimeError(f"DashScope embedding 请求失败: {exc}") from exc

            data = payload.get("data") or []
            if len(data) != len(batch):
                raise RuntimeError(
                    f"DashScope 返回条数不匹配: 期望 {len(batch)}, 实际 {len(data)}"
                )
            # 按 index 排序，保证顺序与入参一致
            for item in sorted(data, key=lambda x: x.get("index", 0)):
                vectors.append(item["embedding"])

        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._call(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._call([text])[0]

    @property
    def identity(self) -> str:
        # 同一 provider 下换模型（v3 → v4）向量空间也不同，因此带上模型名
        return f"{self.name}-{self._model}"























































class LocalHashEmbeddings(BaseEmbeddings):
    """
    本地兜底 embedding（字符 n-gram 特征哈希）

    **仅供离线开发与自测**：无需密钥、无需下载模型，可在无外网环境下跑通
    上传 → 分块 → 入库 → 检索 全链路。检索质量仅相当于词面匹配。

    实现：把文本切分为字符 1/2/3-gram，哈希到固定维度后做次线性加权（sublinear tf）
    并做 L2 归一化，从而与 cosine 距离配合。
    """

    name = "local-hash"
    semantic = False

    def __init__(self, dim: int = LOCAL_EMBEDDING_DIM) -> None:
        self._dim = dim

    @staticmethod
    def _normalize_text(text: str) -> str:
        # 统一小写并压缩空白，提升中文/英文混合场景的稳定性
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    @staticmethod
    def _grams(text: str) -> list[str]:
        """生成字符 1/2/3-gram 特征"""
        grams: list[str] = []
        length = len(text)
        for n in (1, 2, 3):
            if length < n:
                continue
            for i in range(length - n + 1):
                grams.append(text[i : i + n])
        return grams

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        normalized = self._normalize_text(text)

        counts: dict[int, int] = {}
        for gram in self._grams(normalized):
            digest = hashlib.md5(gram.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dim
            counts[index] = counts.get(index, 0) + 1

        for index, count in counts.items():
            # sublinear tf：抑制高频特征
            vector[index] = 1.0 + math.log(count)

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @property
    def identity(self) -> str:
        # 维度是这个提供方唯一的可变参数
        return f"{self.name}-{self._dim}"

























def build_embeddings(settings: Settings) -> BaseEmbeddings:
    """
    按配置构造 embedding 提供方

    provider=dashscope 且已配置 key 时使用 DashScope；
    否则回退到本地兜底并给出显式警告（避免「静默降级导致检索质量莫名变差」）。
    """
    provider = (settings.embedding_provider or "").strip().lower()

    if provider == "dashscope":
        if settings.dashscope_api_key:
            logger.info(
                "Embedding 提供方: DashScope(%s)", settings.embedding_model
            )
            return DashScopeEmbeddings(
                api_key=settings.dashscope_api_key,
                model=settings.embedding_model,
                base_url=settings.dashscope_base_url,
            )
        logger.warning(
            "EMBEDDING_PROVIDER=dashscope 但未配置 DASHSCOPE_API_KEY，"
            "已回退到本地兜底 embedding —— 检索质量会明显下降，生产环境请补上密钥"
        )

    if provider not in ("local", "dashscope", ""):
        logger.warning("未知的 EMBEDDING_PROVIDER=%r，使用本地兜底 embedding", provider)

    logger.info("Embedding 提供方: 本地兜底(字符 n-gram 哈希, dim=%d)", LOCAL_EMBEDDING_DIM)
    return LocalHashEmbeddings()
