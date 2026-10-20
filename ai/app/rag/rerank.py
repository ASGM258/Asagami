"""
重排（rerank）：百炼 DashScope 的 text-rerank API

## 为什么要重排

向量检索与 BM25 都是「先取回候选」的粗排，两者的分数尺度不同、且都不看
query 与文档的**逐字交互**。cross-encoder 类重排模型把 (query, 文档) 拼在
一起过一遍模型，判相关性明显更准，但代价是每个候选都要一次前向计算，
因此只能作用在少量候选上（本实现 10~20 条）。

## 为什么调 API 而不是本地跑

本地模型 `reranker_models/bge-reranker-v2-m3` 是 fp32 的 XLM-R large（2.1 GB 权重），
要跑起来必须额外装 torch（~2.6 GB），而 CPU 上单次打分要 1~3 秒。
百炼的 `gte-rerank-v2` 实测 300ms 左右、按 token 计费（一次 20 条约几百 token），
对当前规模更划算。

## 为什么不直接用 langchain_community 的 DashScopeRerank

那个封装有两个问题：
1. 它把模型名**硬编码**成 `dashscope.TextReRank.Models.gte_rerank`（即 `gte-rerank`），
   而该模型在当前账号上直接 403 AccessDenied（实测），只有 `gte-rerank-v2` 可用；
   要绕过就得传入它的私有 `client` 属性，属于钻封装内部；
2. 它会引入整个 `dashscope` SDK（含 aiohttp 等）只为发一个 HTTP POST。

本项目调用百炼的 embedding 也是直接 HTTP（见 `embeddings.py`），风格一致。
接口语义完全按官方文档：POST /api/v1/services/rerank/text-rerank/text-rerank。
"""

import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

#: 重排服务的固定路径（与 OpenAI 兼容模式的 /compatible-mode/v1 不同）
RERANK_PATH = "/api/v1/services/rerank/text-rerank/text-rerank"


def rerank_endpoint(base_url: str) -> str:
    """
    由配置的 base_url 推导重排端点

    配置里的 `DASHSCOPE_BASE_URL` 是 OpenAI 兼容模式地址
    （`https://dashscope.aliyuncs.com/compatible-mode/v1`），
    重排走的是另一条原生路径，因此只保留 scheme + host。

    Args:
        base_url: 例如 https://dashscope.aliyuncs.com/compatible-mode/v1

    Returns:
        完整的重排端点
    """
    parsed = urlparse((base_url or "").strip())
    host = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
    if not host:
        host = "https://dashscope.aliyuncs.com"
    return host + RERANK_PATH


class DashScopeReranker:
    """百炼重排客户端（同步 HTTP，供检索线程直接调用）"""

    def __init__(
        self,
        api_key: str,
        model: str = "gte-rerank-v2",
        base_url: str = "https://dashscope.aliyuncs.com",
        timeout: int = 15,
    ) -> None:
        if not api_key:
            raise ValueError("重排需要配置 DASHSCOPE_API_KEY")

        self._api_key = api_key
        self._model = model
        self._url = rerank_endpoint(base_url)
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        对候选文档重排

        Args:
            query: 查询
            documents: 候选文档正文（顺序即输入顺序）
            top_n: 返回条数，None 表示全部返回

        Returns:
            [(原始下标, 相关度 0-1), ...]，按相关度降序

        Raises:
            RuntimeError: 接口不可用或返回异常（调用方负责降级）
        """
        if not documents:
            return []

        parameters: dict = {"return_documents": False}
        if top_n is not None and top_n > 0:
            parameters["top_n"] = min(top_n, len(documents))

        payload = {
            "model": self._model,
            "input": {"query": query, "documents": documents},
            "parameters": parameters,
        }

        try:
            response = requests.post(
                self._url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"重排请求失败: {exc}") from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"重排接口返回 {response.status_code}: {response.text[:200]}"
            )

        try:
            results = response.json()["output"]["results"]
        except (ValueError, KeyError) as exc:
            raise RuntimeError(f"重排返回结构异常: {exc}") from exc

        ordered = [
            (int(item["index"]), float(item["relevance_score"]))
            for item in results
            if item.get("index") is not None
        ]
        ordered.sort(key=lambda pair: pair[1], reverse=True)
        return ordered

    def close(self) -> None:
        """无长连接需要释放，保留接口一致性"""
        return None
