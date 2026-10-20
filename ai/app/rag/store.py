"""
知识库向量存储（Chroma）

职责：把分块后的文本写入 Chroma 持久化集合，并提供相似度检索与按文件删除。

设计要点：
- **块 id 必须确定**：由「文件指纹 + 块序号」生成，这样重复上传同一文件是
  覆盖而不是追加，不会产生重复内容。
- **集合按 embedding 空间隔离**：Chroma 集合的向量维度在创建时固定，切换
  embedding 提供方（本地兜底 512 维 ↔ DashScope 1024 维）会让写入/检索直接报
  `expecting embedding with dimension of 512, got 1024`。因此集合名带上
  provider + 模型/维度，各空间互不干扰。
- **旧集合自动迁移**：早期版本固定用 `anime_knowledge` 这个名字，切到新空间时
  会用当前 embedding 把旧数据重新向量化后搬过来，用户不必重新上传文件。
- 集合使用 cosine 距离，检索结果换算成 0-1 的相似度便于展示与过滤。
- 库里保存的是**文件相对路径**（basename），不保存用户的绝对路径。
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import Settings
from app.rag.embeddings import BaseEmbeddings
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.keyword_index import KeywordIndex, KeywordIndexCache
from app.rag.loaders import TextChunk
from app.rag.rerank import DashScopeReranker

logger = logging.getLogger(__name__)

#: 集合名前缀
COLLECTION_PREFIX = "anime_knowledge"

#: 早期版本使用的固定集合名（无 embedding 空间后缀），作为迁移源
LEGACY_COLLECTION_NAME = "anime_knowledge"


def collection_name_for(embeddings: BaseEmbeddings) -> str:
    """
    按 embedding 空间生成集合名

    Chroma 集合的维度在创建时固定，混用不同提供方的向量必然报错，
    因此把 provider（以及模型名/维度）写进集合名。

    Examples:
        dashscope-text-embedding-v3 -> anime_knowledge__dashscope_text_embedding_v3
        local-hash-512              -> anime_knowledge__local_hash_512
    """
    identity = getattr(embeddings, "identity", None) or embeddings.name or "default"
    slug = re.sub(r"[^a-z0-9]+", "_", str(identity).lower()).strip("_") or "default"
    return f"{COLLECTION_PREFIX}__{slug}"


@dataclass
class SearchHit:
    """一条检索结果"""

    content: str
    score: float
    source: str
    chunk_index: int


def _cosine(a: list[float], b: list[float]) -> float:
    """两向量的余弦相似度（向量可能来自 Chroma，需转 numpy）"""
    try:
        import numpy as np

        va = np.asarray(a, dtype="float32")
        vb = np.asarray(b, dtype="float32")
        denominator = float(np.linalg.norm(va) * np.linalg.norm(vb))
        if denominator <= 0:
            return 0.0
        return float(np.dot(va, vb) / denominator)
    except Exception:  # noqa: BLE001 - 兜底用纯 Python
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        return dot / (norm_a * norm_b)


class KnowledgeStore:
    """知识库向量存储"""

    def __init__(
        self,
        settings: Settings,
        embeddings: BaseEmbeddings,
        persist_dir: str | None = None,
        client: chromadb.ClientAPI | None = None,
    ) -> None:
        self._settings = settings
        self._embeddings = embeddings
        self._persist_dir = persist_dir or settings.chroma_persist_dir
        #: 测试可注入 EphemeralClient，避免落地文件
        self._injected_client = client
        self._client: chromadb.ClientAPI | None = None
        self._collection = None
        #: 文件清单缓存：每轮对话都要注入「知识库清单」，不能每次都扫全库元数据
        self._sources_cache: list[dict[str, Any]] | None = None
        #: BM25 索引缓存（知识库变更时失效）
        self._keyword_cache = KeywordIndexCache()
        #: 重排客户端；False 表示尚未初始化，None 表示不可用
        self._reranker_client: Any = False

    # ==================== 初始化 ====================

    @property
    def collection(self):
        """惰性初始化 Chroma 集合（首次检索/写入时创建）"""
        if self._collection is None:
            if self._injected_client is not None:
                self._client = self._injected_client
            else:
                os.makedirs(self._persist_dir, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self._persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )

            name = collection_name_for(self._embeddings)
            self._collection = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )

            # 新集合还是空的 → 看看有没有旧固定名集合需要搬过来
            if self._collection.count() == 0:
                self._migrate_legacy_collection(self._collection, name)

            logger.info(
                "Chroma 知识库已就绪: path=%s, collection=%s, 现有块数=%d",
                "(注入的客户端)" if self._injected_client is not None else self._persist_dir,
                name,
                self._collection.count(),
            )
            self._warn_other_spaces(name)

        return self._collection

    # ==================== 迁移与诊断 ====================

    def _existing_collection_names(self) -> set[str]:
        """当前客户端下的集合名集合（兼容返回对象/字符串两种 API 形态）"""
        try:
            collections = self._client.list_collections() if self._client else []
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取 Chroma 集合列表失败: %s", exc)
            return set()
        return {getattr(item, "name", item) for item in collections}

    def _migrate_legacy_collection(self, target, target_name: str) -> None:
        """
        把旧固定名集合的数据迁移到当前 embedding 空间

        旧集合的向量维度很可能与当前提供方不同（本地 512 维 → DashScope 1024 维），
        不能直接复制向量，必须用当前 embedding **重新向量化**。

        只有在成功写入后才删除旧集合，避免中途失败导致数据丢失。
        """
        if LEGACY_COLLECTION_NAME == target_name:
            return
        if LEGACY_COLLECTION_NAME not in self._existing_collection_names():
            return

        try:
            legacy = self._client.get_collection(LEGACY_COLLECTION_NAME)  # type: ignore[union-attr]
            total = legacy.count()
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取旧集合失败，跳过迁移: %s", exc)
            return

        if total == 0:
            try:
                self._client.delete_collection(LEGACY_COLLECTION_NAME)  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001 - 空集合删不掉不影响使用
                pass
            return

        logger.warning(
            "检测到旧集合 %s（%d 块），正在用当前 embedding(%s) 重建到 %s ...",
            LEGACY_COLLECTION_NAME,
            total,
            self._embeddings.identity,
            target_name,
        )

        try:
            data = legacy.get(include=["documents", "metadatas"])
            ids = [str(i) for i in (data.get("ids") or [])]
            documents = [str(d or "") for d in (data.get("documents") or [])]
            metadatas = [
                {**(m or {}), "semantic": self._embeddings.semantic}
                for m in (data.get("metadatas") or [])
            ]
            if not ids:
                return

            vectors = self._embeddings.embed_documents(documents)
            target.upsert(
                ids=ids, documents=documents, embeddings=vectors, metadatas=metadatas
            )
        except Exception as exc:  # noqa: BLE001 - 迁移失败不能阻断正常上传
            logger.error("旧集合迁移失败（旧数据已保留，下次启动会重试）: %s", exc)
            return

        deleted = False
        try:
            self._client.delete_collection(LEGACY_COLLECTION_NAME)  # type: ignore[union-attr]
            deleted = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("旧集合迁移完成但删除失败: %s", exc)

        logger.info(
            "旧集合迁移完成: %d 块已用 %s 重建到 %s（旧集合%s）",
            len(ids),
            self._embeddings.identity,
            target_name,
            "已删除" if deleted else "仍保留",
        )

    def _warn_other_spaces(self, active_name: str) -> None:
        """提示存在其他 embedding 空间的知识库，否则用户会疑惑「我的文件呢」"""
        others: list[str] = []
        for name in self._existing_collection_names():
            if name == active_name or not str(name).startswith(COLLECTION_PREFIX):
                continue
            try:
                count = self._client.get_collection(name).count()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                continue
            if count:
                others.append(f"{name}({count} 块)")

        if others:
            logger.warning(
                "另有其他 embedding 空间的集合: %s —— 当前使用 %s，它们不会被检索。"
                "切换 EMBEDDING_PROVIDER / EMBEDDING_MODEL 后需重新上传，或切回原配置。",
                ", ".join(others),
                active_name,
            )

    @property
    def embeddings(self) -> BaseEmbeddings:
        """当前 embedding 提供方（供接口回显）"""
        return self._embeddings

    @property
    def collection_name(self) -> str:
        """当前集合名（供接口回显/排查）"""
        return collection_name_for(self._embeddings)

    # ==================== 写入 ====================

    @staticmethod
    def _file_fingerprint(filename: str, content: bytes) -> str:
        """文件指纹：同名不同内容视为不同文件，用于生成稳定的块 id"""
        digest = hashlib.md5()
        digest.update(filename.encode("utf-8"))
        digest.update(content)
        return digest.hexdigest()[:16]

    def add_chunks(
        self,
        filename: str,
        file_bytes: bytes,
        chunks: list[TextChunk],
        extra_metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        写入（或覆盖）某个文件的全部文本块

        Args:
            filename: 原始文件名（作为 source 元数据）
            file_bytes: 原始文件内容（用于计算指纹）
            chunks: 文本块
            extra_metadata: 附加元数据

        Returns:
            实际写入的块数
        """
        if not chunks:
            return 0

        fingerprint = self._file_fingerprint(filename, file_bytes)
        # 先清掉同一文件的旧块，避免重复上传产生重复内容
        self.delete_by_source(filename)

        ids = [f"{fingerprint}-{c.index}" for c in chunks]
        documents = [c.content for c in chunks]

        logger.info("正在向量化 %d 个文本块（provider=%s）...", len(chunks), self._embeddings.name)
        vectors = self._embeddings.embed_documents(documents)

        metadatas = [
            {
                "source": filename,
                "chunk_index": c.index,
                "offset": c.offset,
                "fingerprint": fingerprint,
                "semantic": self._embeddings.semantic,
                **(extra_metadata or {}),
            }
            for c in chunks
        ]

        self.collection.upsert(
            ids=ids, documents=documents, embeddings=vectors, metadatas=metadatas
        )
        # 文件清单变了，清掉缓存，否则下一轮注入的还是旧清单
        self._sources_cache = None
        # BM25 索引也要重建，否则新块检索不到
        self._keyword_cache.invalidate()
        logger.info("已写入知识库: file=%s, 块数=%d", filename, len(ids))
        return len(ids)

    def delete_by_source(self, filename: str) -> int:
        """删除某个来源文件的全部块"""
        try:
            existing = self.collection.get(where={"source": filename}, include=[])
            ids = existing.get("ids") or []
            if ids:
                self.collection.delete(ids=ids)
                self._sources_cache = None
                self._keyword_cache.invalidate()
                logger.info("已删除旧块: file=%s, 块数=%d", filename, len(ids))
            return len(ids)
        except Exception as exc:  # noqa: BLE001 - 删除失败不应阻断上传
            logger.warning("删除旧块失败: file=%s, error=%s", filename, exc)
            return 0

    # ==================== 检索 ====================

    def search(self, query: str, top_k: int = 4, min_score: float | None = None) -> list[SearchHit]:
        """
        混合检索：向量 + BM25 → RRF 融合 → 重排

        管线（任一步不可用都自动降级，不阻断检索）：

            向量检索(候选池) ┐
                             ├─ RRF 融合 → 前 N 条 → 百炼重排 → top_k
            BM25 检索(候选池) ┘

        Args:
            query: 查询文本
            top_k: 最终返回条数
            min_score: 最低相关度（0-1），None 表示不过滤

        Returns:
            检索结果（按相关度降序）
        """
        if not query or not query.strip():
            return []

        total = self.collection.count()
        if total == 0:
            return []

        pool = max(int(top_k), int(self._settings.rag_candidate_pool), 1)

        # ---- 第 1 路：向量检索 ----
        vector_rows, query_vector = self._vector_candidates(query, min(pool, total))

        # ---- 第 2 路：BM25 关键词检索 ----
        keyword_rows: list[dict] = []
        if self._settings.rag_bm25_enabled:
            try:
                keyword_rows = self._keyword_index().search(query, k=pool)
            except Exception as exc:  # noqa: BLE001 - 关键词路失败不影响向量路
                logger.warning("[检索] BM25 检索异常，降级为纯向量: %s", exc)

        # ---- 融合 ----
        candidates = self._fuse(vector_rows, keyword_rows, query_vector)

        if not candidates:
            return []

        # ---- 重排 ----
        ranked = self._rerank(query, candidates, top_k)

        hits: list[SearchHit] = []
        for row, score in ranked:
            if min_score is not None and score < min_score:
                continue
            metadata = row.get("metadata") or {}
            hits.append(
                SearchHit(
                    content=row.get("content") or "",
                    score=round(float(score), 4),
                    source=str(metadata.get("source", "未知")),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                )
            )
            if len(hits) >= top_k:
                break

        return hits

    # ---------- 检索内部步骤 ----------

    def _vector_candidates(self, query: str, n_results: int) -> tuple[list[dict], list[float]]:
        """向量检索候选（带真实相似度），并返回查询向量供后续复用"""
        vector = self._embeddings.embed_query(query)
        result = self.collection.query(
            query_embeddings=[vector],
            n_results=max(1, n_results),
            include=["documents", "metadatas", "distances"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        rows: list[dict] = []
        for chunk_id, content, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            rows.append(
                {
                    "chunk_key": str(chunk_id),
                    "content": content or "",
                    "metadata": dict(metadata or {}),
                    # cosine 距离 → 相似度
                    "similarity": max(0.0, min(1.0, 1.0 - float(distance))),
                }
            )
        return rows, vector

    def _cosine_scores(
        self, query_vector: list[float], rows: list[dict]
    ) -> dict[str, float]:
        """
        为候选补上「与查询的余弦相似度」

        为什么需要：BM25 命中的片段可能不在向量候选里（这正是它救回来的部分），
        它没有相似度可展示。而 RRF 分数是名次派生的相对值（第一名恒为 1.0），
        直接当相似度展示会把「弱相关」显示成 0.97，误导模型。

        这里直接从 Chroma 取回这些块**已存储**的向量本地算余弦 ——
        不产生任何额外的 embedding 请求。
        """
        scores: dict[str, float] = {}
        missing = [row["chunk_key"] for row in rows if row.get("similarity") is None]

        if missing:
            try:
                data = self.collection.get(ids=missing, include=["embeddings"])
                for chunk_id, embedding in zip(
                    data.get("ids") or [], data.get("embeddings")
                ):
                    scores[str(chunk_id)] = _cosine(query_vector, embedding)
            except Exception as exc:  # noqa: BLE001 - 取不到就退回 RRF 分
                logger.warning("[检索] 读取候选向量失败: %s", exc)

        for row in rows:
            key = row["chunk_key"]
            if key in scores:
                continue
            similarity = row.get("similarity")
            if similarity is not None:
                scores[key] = float(similarity)
        return scores

    def _keyword_index(self) -> "KeywordIndex":
        """惰性构建（并缓存）BM25 索引"""
        def load_records() -> list[dict]:
            data = self.collection.get(include=["documents", "metadatas"])
            return [
                {
                    "id": str(chunk_id),
                    "content": content or "",
                    "metadata": dict(metadata or {}),
                }
                for chunk_id, content, metadata in zip(
                    data.get("ids") or [],
                    data.get("documents") or [],
                    data.get("metadatas") or [],
                )
            ]

        return self._keyword_cache.get(load_records)

    def _fuse(
        self, vector_rows: list[dict], keyword_rows: list[dict], query_vector: list[float]
    ) -> list[dict]:
        """
        两路融合（RRF）并按融合分排序，返回候选

        RRF 只决定**顺序**；对外展示的分数用余弦相似度（重排成功时用重排分），
        避免把名次派生的相对值当成相似度。
        """
        by_key: dict[str, dict] = {}
        for row in vector_rows:
            by_key[row["chunk_key"]] = row
        for row in keyword_rows:
            by_key.setdefault(row["chunk_key"], row)

        rankings: list[list[str]] = []
        weights: list[float] = []

        if vector_rows:
            rankings.append([row["chunk_key"] for row in vector_rows])
            weights.append(float(self._settings.rag_vector_weight))
        if keyword_rows:
            rankings.append([row["chunk_key"] for row in keyword_rows])
            weights.append(float(self._settings.rag_bm25_weight))

        if not rankings:
            return []

        fused = reciprocal_rank_fusion(
            rankings, weights=weights, k=int(self._settings.rag_rrf_k)
        )

        limit = max(int(self._settings.rag_pre_rerank_k), 1)
        picked: list[dict] = []
        for chunk_key, _raw in fused:
            row = by_key.get(chunk_key)
            if row is None:
                continue
            picked.append(row)
            if len(picked) >= limit:
                break

        # 统一补上余弦相似度作为展示分（重排成功时会被真实相关度覆盖）
        cosine = self._cosine_scores(query_vector, picked)
        return [
            {**row, "fused_score": float(cosine.get(row["chunk_key"], 0.0))}
            for row in picked
        ]

    def _rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[tuple[dict, float]]:
        """
        重排；接口不可用时降级为融合顺序

        Returns:
            [(候选行, 展示用分数 0-1), ...]
        """
        if not candidates:
            return []

        if not self._settings.rag_rerank_enabled:
            return [(row, row["fused_score"]) for row in candidates]

        reranker = self._reranker()
        if reranker is None:
            return [(row, row["fused_score"]) for row in candidates]

        try:
            ordered = reranker.rerank(
                query, [row.get("content") or "" for row in candidates], top_n=top_k
            )
        except Exception as exc:  # noqa: BLE001 - 重排失败必须能降级
            logger.warning("[检索] 重排失败，使用融合排序: %s", exc)
            return [(row, row["fused_score"]) for row in candidates]

        if not ordered:
            return [(row, row["fused_score"]) for row in candidates]

        results: list[tuple[dict, float]] = []
        for index, score in ordered:
            if 0 <= index < len(candidates):
                results.append((candidates[index], score))
        return results or [(row, row["fused_score"]) for row in candidates]

    def _reranker(self) -> Any | None:
        """惰性创建重排客户端（未配置 key 时返回 None）"""
        if self._reranker_client is not False:
            return self._reranker_client or None

        api_key = getattr(self._settings, "dashscope_api_key", "") or ""
        if not api_key:
            logger.warning("[检索] 未配置 DASHSCOPE_API_KEY，跳过重排")
            self._reranker_client = None
            return None

        self._reranker_client = DashScopeReranker(
            api_key=api_key,
            model=self._settings.rag_rerank_model,
            base_url=self._settings.dashscope_base_url,
            timeout=self._settings.rag_rerank_timeout,
        )
        logger.info("[检索] 重排已启用: %s", self._settings.rag_rerank_model)
        return self._reranker_client

    # ==================== 统计 ====================

    def count(self) -> int:
        """块总数"""
        try:
            return self.collection.count()
        except Exception as exc:  # noqa: BLE001
            logger.error("统计知识库块数失败: %s", exc)
            return 0

    def list_sources(self) -> list[dict[str, Any]]:
        """
        列出已入库的文件及其块数

        Returns:
            [{source, chunks}, ...]（按文件名排序）
        """
        if self._sources_cache is not None:
            return [dict(item) for item in self._sources_cache]

        try:
            data = self.collection.get(include=["metadatas"])
        except Exception as exc:  # noqa: BLE001
            logger.error("读取知识库文件列表失败: %s", exc)
            return []

        counter: dict[str, int] = {}
        for metadata in data.get("metadatas") or []:
            source = str((metadata or {}).get("source", "未知"))
            counter[source] = counter.get(source, 0) + 1

        result = [
            {"source": name, "chunks": chunks}
            for name, chunks in sorted(counter.items())
        ]
        self._sources_cache = result
        return [dict(item) for item in result]


# ==================== 进程级单例 ====================

_store: KnowledgeStore | None = None


def init_knowledge_store(settings: Settings) -> KnowledgeStore:
    """初始化进程级知识库单例"""
    global _store
    if _store is None:
        from app.rag.embeddings import build_embeddings

        _store = KnowledgeStore(settings, build_embeddings(settings))
    return _store


def get_knowledge_store() -> KnowledgeStore:
    """获取进程级知识库单例"""
    if _store is None:
        raise RuntimeError("知识库尚未初始化")
    return _store
