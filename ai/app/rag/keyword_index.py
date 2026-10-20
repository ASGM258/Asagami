"""
BM25 关键词索引

为什么要有一路关键词检索：向量检索对**专有名词**天生弱。
用户问「绫弥一条是谁」，embedding 给出的近邻往往是各类"角色介绍"泛文本，
而真正含这三个字的那段反而可能排不到前面。BM25 按词频/逆文档频率算，
专有名词一旦出现就能精确命中，与向量检索互补。

实现选择：
- 用 `langchain_community.retrievers.BM25Retriever`（封装好的），底层是 `rank_bm25`
- 中文必须分词：`preprocess_func=jieba.lcut`。默认按空格切分，
  中文整句会变成一个 token，BM25 直接失效
- 索引按需构建并缓存；知识库增删时由 store 调用 `invalidate()` 失效

注意：BM25 返回的是**排序**，不参与分数融合的绝对值比较 —— 融合用 RRF
（Reciprocal Rank Fusion），只看名次，因此不需要对齐两路的分数尺度。
"""

import logging
import re
import threading

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def default_tokenizer(text: str) -> list[str]:
    """
    默认分词器：jieba 词 + 汉字二元组

    **为什么要加二元组**：jieba 的词库不可能覆盖二次元作品里的所有专有名词。
    实测「绫弥一条是村正的女主角」会被切成
    `['绫','弥','一条','是','村','正','的','女主角']` —— 「村正」这种词典外的名字
    直接退化成单字，既降低区分度，又让「的」「是」这类单字噪声满屏。

    汉字二元组（character bigram）不依赖词典：「绫弥」「弥一」「一条」「村正」
    这些两字组合天然包含专有名词，是中文关键词检索的常用兜底手段。
    两者并用：词典词保证常规词的准确，二元组兜住 OOV 专名。

    Args:
        text: 原始文本

    Returns:
        token 列表（词 + 汉字二元组）
    """
    import jieba

    lowered = (text or "").strip().lower()
    if not lowered:
        return []

    words = [
        token.strip()
        for token in jieba.lcut(lowered)
        if token.strip() and token.isprintable()
    ]

    # 只对连续汉字段做二元组，避免跨标点/空格拼出无意义组合
    bigrams: list[str] = []
    for segment in re.findall(r"[\u4e00-\u9fff]+", lowered):
        bigrams.extend(segment[i : i + 2] for i in range(len(segment) - 1))

    return words + bigrams


class KeywordIndex:
    """BM25 索引（针对某个知识库快照）"""

    def __init__(self, retriever: BM25Retriever | None) -> None:
        self._retriever = retriever

    @property
    def ready(self) -> bool:
        return self._retriever is not None

    @classmethod
    def build(
        cls,
        records: list[dict],
        tokenizer=default_tokenizer,
    ) -> "KeywordIndex":
        """
        从知识库快照构建索引

        Args:
            records: [{"id": 块id, "content": 文本, "metadata": {...}}, ...]
            tokenizer: 分词函数，默认 jieba

        Returns:
            KeywordIndex；没有可用文本时返回空索引（`ready=False`）
        """
        documents: list[Document] = []
        for record in records or []:
            content = str(record.get("content") or "").strip()
            if not content:
                continue
            documents.append(
                Document(
                    page_content=content,
                    # chunk_key 用于把关键词结果与向量结果对齐（同一个块）
                    metadata={"chunk_key": str(record.get("id") or ""), **(record.get("metadata") or {})},
                )
            )

        if not documents:
            logger.info("[BM25] 知识库为空，跳过关键词索引构建")
            return cls(None)

        try:
            retriever = BM25Retriever.from_documents(
                documents,
                preprocess_func=tokenizer,
                k=len(documents),
            )
        except Exception as exc:  # noqa: BLE001 - 索引失败不应让检索整体不可用
            logger.error("[BM25] 索引构建失败，本次仅用向量检索: %s", exc)
            return cls(None)

        logger.info("[BM25] 关键词索引就绪: %d 个块", len(documents))
        return cls(retriever)

    def search(self, query: str, k: int = 20) -> list[dict]:
        """
        关键词检索

        Args:
            query: 查询文本
            k: 返回条数上限

        Returns:
            [{"chunk_key", "content", "metadata"}, ...]，按 BM25 相关度降序
        """
        if not self.ready or not (query or "").strip():
            return []

        retriever = self._retriever
        assert retriever is not None
        # BM25Retriever 用 self.k 控制返回条数，这里按需调整
        retriever.k = max(1, int(k))

        try:
            documents = retriever.invoke(query)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[BM25] 关键词检索失败: %s", exc)
            return []

        return [
            {
                "chunk_key": str(doc.metadata.get("chunk_key") or ""),
                "content": doc.page_content,
                "metadata": dict(doc.metadata),
            }
            for doc in documents
            if doc.metadata.get("chunk_key")
        ]


class KeywordIndexCache:
    """
    按知识库版本缓存的 BM25 索引

    与查全库元数据相比，BM25 建索引要分词整个语料，代价更高，
    因此缓存到「知识库有变更」为止。
    """

    def __init__(self) -> None:
        self._index: KeywordIndex | None = None
        self._lock = threading.Lock()

    def get(self, loader) -> KeywordIndex:
        """获取索引，缺失时用 loader 构建（loader 返回 records）"""
        if self._index is not None:
            return self._index

        with self._lock:
            if self._index is None:
                self._index = KeywordIndex.build(loader())
            return self._index

    def invalidate(self) -> None:
        """知识库变更后调用"""
        with self._lock:
            self._index = None
