"""
RAG 混合检索测试：BM25 关键词路 + RRF 融合 + 百炼重排

背景：
- 向量检索对专有名词（角色名/作品名）天生弱，加一路 BM25 补上词面精确命中
- 两路分数尺度不同（余弦相似度 0-1 vs 无上界的 BM25 分），用 RRF 按名次融合
- 重排走百炼 text-rerank API（本地 bge-reranker 需要 torch，未采用）

覆盖：
1. RRF 融合：单路/多路、权重、同分顺序、归一化
2. BM25 索引：中文分词生效、专有名词能命中、空库降级
3. 混合检索：两路都被采纳、重排失败可降级、只走向量路时保留余弦相似度
4. 重排客户端：端点推导、请求体/解析、异常抛出
"""

import json

import pytest
from chromadb.config import Settings as ChromaSettings

from app.config import Settings
from app.rag.embeddings import BaseEmbeddings
from app.rag.fusion import normalize_scores, reciprocal_rank_fusion
from app.rag.keyword_index import KeywordIndex, KeywordIndexCache, default_tokenizer
from app.rag.loaders import TextChunk
from app.rag.rerank import DashScopeReranker, RERANK_PATH, rerank_endpoint
from app.rag.store import KnowledgeStore


def make_settings(**overrides) -> Settings:
    defaults = dict(
        deepseek_api_key="t",
        llm_model="fake",
        dashscope_api_key="",  # 默认关闭重排，避免测试触网
    )
    defaults.update(overrides)
    return Settings(**defaults)


class StubEmbeddings(BaseEmbeddings):
    """
    可编排的假 embedding

    文档用内容哈希生成确定性向量；查询若命中 `keyword`，就返回「包含该关键词的
    那篇文档」的向量（相似度 1.0），否则用查询自身的哈希向量。
    这样能精确构造「向量路排错、BM25 路排对」的场景。
    """

    name = "stub"
    semantic = True
    identity = "stub-8"

    def __init__(self, keyword: str = "", dim: int = 8) -> None:
        self._keyword = keyword
        self._dim = dim
        self._by_text: dict[str, list[float]] = {}

    def _hash_vector(self, text: str) -> list[float]:
        import hashlib

        digest = hashlib.md5(text.encode("utf-8")).digest()
        return [(digest[i] + 1) / 256.0 for i in range(self._dim)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = self._hash_vector(text)
            self._by_text[text] = vector
            vectors.append(vector)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        if self._keyword:
            for doc_text, vector in self._by_text.items():
                if self._keyword in doc_text:
                    return list(vector)
        return self._hash_vector(text)


# ==================== 1. RRF 融合 ====================


class TestRRF:
    def test_single_ranking_keeps_order(self):
        fused = reciprocal_rank_fusion([["a", "b", "c"]])
        assert [key for key, _ in fused] == ["a", "b", "c"]

    def test_document_in_both_lists_wins(self):
        """两路都靠前的文档应胜过只有一路第一的文档"""
        vector = ["a", "b", "c"]
        keyword = ["c", "b", "d"]
        fused = dict(reciprocal_rank_fusion([vector, keyword]))

        # b: 两路都是第 2 → 2/62；c: 第 3 + 第 1 → 1/63 + 1/61
        top_keys = [key for key, _ in reciprocal_rank_fusion([vector, keyword])]
        assert top_keys[0] in ("b", "c")
        assert fused["b"] > fused["a"], "多路共同命中的文档应高于单路命中"

    def test_weights_shift_ranking(self):
        vector = ["a", "b"]
        keyword = ["b", "a"]

        # 权重全给向量路 → a 第一
        biased = reciprocal_rank_fusion([vector, keyword], weights=[1.0, 0.0])
        assert [key for key, _ in biased] == ["a", "b"]

    def test_empty_inputs(self):
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []

    def test_weights_length_mismatch(self):
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([["a"]], weights=[1.0, 2.0])

    def test_skips_blank_keys(self):
        fused = reciprocal_rank_fusion([["a", "", "b"]])
        assert [key for key, _ in fused] == ["a", "b"]

    def test_normalize_scores(self):
        normalized = dict(normalize_scores([("a", 0.02), ("b", 0.01)]))
        assert normalized["a"] == pytest.approx(1.0)
        assert normalized["b"] == pytest.approx(0.5)

    def test_normalize_empty(self):
        assert normalize_scores([]) == []


# ==================== 2. BM25 索引 ====================


class TestKeywordIndex:
    RECORDS = [
        {
            "id": "chunk-a",
            "content": "绫弥一条是《装甲恶鬼村正》的女主角，性格绝对正义，重度路痴。",
            "metadata": {"source": "a.txt", "chunk_index": 0},
        },
        {
            "id": "chunk-b",
            "content": "《命运石之门》是一部科幻悬疑动画，讲时间旅行与因果。",
            "metadata": {"source": "b.txt", "chunk_index": 0},
        },
        {
            "id": "chunk-c",
            "content": "B站上有很多斩服少女的 MAD 与名场面剪辑。",
            "metadata": {"source": "c.txt", "chunk_index": 0},
        },
    ]

    def test_chinese_tokenizer_splits_words(self):
        tokens = default_tokenizer("绫弥一条是村正的女主角")
        # 不分词的话整句会是一个 token，中文 BM25 直接失效
        assert len(tokens) >= 6

    def test_bigrams_rescue_oov_names(self):
        """
        jieba 词典里没有的专有名词会被切成单字（「村正」→「村」「正」），
        二元组必须补上，否则区分度太低、且单字噪声会污染 BM25
        """
        tokens = default_tokenizer("绫弥一条是村正的女主角")

        assert "村正" in tokens, "OOV 专名应被二元组兜住"
        assert "绫弥" in tokens
        assert "一条" in tokens

    def test_tokenizer_ignores_empty(self):
        assert default_tokenizer("") == []
        assert default_tokenizer("   ") == []

    def test_finds_exact_entity(self):
        index = KeywordIndex.build(self.RECORDS)
        hits = index.search("绫弥一条", k=3)

        assert hits, "专有名词应能被 BM25 命中"
        assert hits[0]["chunk_key"] == "chunk-a"

    def test_unrelated_query_does_not_hit_entity(self):
        index = KeywordIndex.build(self.RECORDS)
        hits = index.search("命运石之门", k=3)

        assert hits[0]["chunk_key"] == "chunk-b"

    def test_empty_records(self):
        index = KeywordIndex.build([])
        assert index.ready is False
        assert index.search("任意") == []

    def test_returns_chunk_key_and_metadata(self):
        index = KeywordIndex.build(self.RECORDS)
        hit = index.search("村正", k=1)[0]

        assert hit["chunk_key"].startswith("chunk-")
        assert hit["metadata"]["source"].endswith(".txt")

    def test_cache_invalidation(self):
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return self.RECORDS

        cache = KeywordIndexCache()
        first = cache.get(loader)
        second = cache.get(loader)
        assert first is second and calls["n"] == 1

        cache.invalidate()
        cache.get(loader)
        assert calls["n"] == 2


# ==================== 3. 重排客户端 ====================


class TestReranker:
    def test_endpoint_from_compatible_base_url(self):
        endpoint = rerank_endpoint("https://dashscope.aliyuncs.com/compatible-mode/v1")
        assert endpoint == "https://dashscope.aliyuncs.com" + RERANK_PATH

    def test_endpoint_falls_back_to_default_host(self):
        assert rerank_endpoint("") == "https://dashscope.aliyuncs.com" + RERANK_PATH

    def test_requires_api_key(self):
        with pytest.raises(ValueError):
            DashScopeReranker(api_key="")

    def test_parses_and_sorts_results(self, monkeypatch):
        captured = {}

        class FakeResponse:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "output": {
                        "results": [
                            {"index": 0, "relevance_score": 0.1},
                            {"index": 2, "relevance_score": 0.9},
                            {"index": 1, "relevance_score": 0.5},
                        ]
                    }
                }

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            return FakeResponse()

        import app.rag.rerank as R

        monkeypatch.setattr(R.requests, "post", fake_post)

        reranker = DashScopeReranker(api_key="k", model="gte-rerank-v2")
        ordered = reranker.rerank("q", ["d0", "d1", "d2"], top_n=3)

        assert [index for index, _ in ordered] == [2, 1, 0]
        assert captured["payload"]["model"] == "gte-rerank-v2"
        assert captured["payload"]["input"]["query"] == "q"
        assert captured["payload"]["input"]["documents"] == ["d0", "d1", "d2"]
        assert captured["payload"]["parameters"]["top_n"] == 3
        assert captured["headers"]["Authorization"] == "Bearer k"

    def test_http_error_raises(self, monkeypatch):
        class FakeResponse:
            status_code = 403
            text = "AccessDenied"

            def json(self):
                return {}

        import app.rag.rerank as R

        monkeypatch.setattr(R.requests, "post", lambda *a, **k: FakeResponse())
        reranker = DashScopeReranker(api_key="k")

        with pytest.raises(RuntimeError) as exc:
            reranker.rerank("q", ["d0"])
        assert "403" in str(exc.value)

    def test_empty_documents_short_circuits(self):
        reranker = DashScopeReranker(api_key="k")
        assert reranker.rerank("q", []) == []


# ==================== 4. 混合检索（store 级） ====================


@pytest.fixture
def hybrid_store():
    import chromadb

    def _build(settings: Settings, embeddings: BaseEmbeddings, chunks: list[TextChunk]):
        client = chromadb.EphemeralClient(
            settings=ChromaSettings(
                anonymized_telemetry=False, allow_reset=True, is_persistent=False
            )
        )
        client.reset()
        store = KnowledgeStore(settings, embeddings, client=client)
        groups: dict[str, list[TextChunk]] = {}
        for chunk in chunks:
            groups.setdefault(chunk.source, []).append(chunk)
        for source, items in groups.items():
            store.add_chunks(source, source.encode("utf-8"), items)
        return store

    return _build


def make_chunks() -> list[TextChunk]:
    return [
        TextChunk(content="绫弥一条是装甲恶鬼村正的女主角，绝对正义", index=0, source="a.txt"),
        TextChunk(content="命运石之门讲时间旅行与因果", index=0, source="b.txt"),
        TextChunk(content="斩服少女是 trigger 的动画", index=0, source="c.txt"),
    ]


class TestHybridSearch:
    def test_bm25_rescues_exact_entity(self, hybrid_store):
        """
        向量路被故意做成"只看关键词"，于是会把含「时间旅行」的那篇排前面；
        加上 BM25 后，精确含「绫弥一条」的那篇必须被拉回第一。

        反向对照见 `test_bm25_disabled_uses_vector_only`（关掉 BM25 时排第一的是 b.txt）。
        """
        settings = make_settings(
            rag_bm25_enabled=True,
            rag_bm25_weight=2.0,
            rag_rerank_enabled=False,
            rag_pre_rerank_k=5,
        )
        store = hybrid_store(settings, StubEmbeddings(keyword="时间旅行"), make_chunks())

        hits = store.search("绫弥一条", top_k=3)

        assert hits[0].source == "a.txt", f"BM25 应把精确命中拉回第一，实际: {[h.source for h in hits]}"

    def test_bm25_disabled_uses_vector_only(self, hybrid_store):
        settings = make_settings(rag_bm25_enabled=False, rag_rerank_enabled=False)
        store = hybrid_store(settings, StubEmbeddings(keyword="时间旅行"), make_chunks())

        hits = store.search("绫弥一条", top_k=3)

        # 向量路只认关键词，故命中 时间旅行 那篇
        assert hits[0].source == "b.txt"

    def test_vector_only_scores_keep_cosine_semantics(self, hybrid_store):
        """只走向量路时应返回真实相似度，而不是 RRF 相对分（否则全是 1.0）"""
        settings = make_settings(rag_bm25_enabled=False, rag_rerank_enabled=False)
        store = hybrid_store(settings, StubEmbeddings(keyword="时间旅行"), make_chunks())

        hits = store.search("时间旅行", top_k=3)

        assert hits[0].score == pytest.approx(1.0, abs=1e-3)
        assert hits[-1].score < hits[0].score, "非同分条目应体现相似度差距"

    def test_rerank_reorders(self, hybrid_store, monkeypatch):
        settings = make_settings(rag_bm25_enabled=True, dashscope_api_key="fake-key")
        store = hybrid_store(settings, StubEmbeddings(keyword="时间旅行"), make_chunks())

        class FakeReranker:
            model = "fake"

            def rerank(self, query, documents, top_n=None):
                # 把最后一条强行排第一，验证重排结果被采纳
                return [(len(documents) - 1, 0.99)] + [
                    (i, 0.5 - i * 0.01) for i in range(len(documents) - 1)
                ]

        monkeypatch.setattr(store, "_reranker", lambda: FakeReranker())

        hits = store.search("任意", top_k=3)

        assert hits[0].score == pytest.approx(0.99, abs=1e-3)

    def test_rerank_failure_falls_back(self, hybrid_store, monkeypatch):
        settings = make_settings(rag_bm25_enabled=True, dashscope_api_key="fake-key")
        store = hybrid_store(settings, StubEmbeddings(keyword="时间旅行"), make_chunks())

        class BrokenReranker:
            def rerank(self, query, documents, top_n=None):
                raise RuntimeError("重排挂了")

        monkeypatch.setattr(store, "_reranker", lambda: BrokenReranker())

        hits = store.search("绫弥一条", top_k=2)

        assert hits, "重排失败不能导致检索整体失败"
        assert hits[0].source == "a.txt"

    def test_no_reranker_without_api_key(self, hybrid_store):
        settings = make_settings(dashscope_api_key="")
        store = hybrid_store(settings, StubEmbeddings(keyword="时间旅行"), make_chunks())

        assert store._reranker() is None

    def test_empty_query(self, hybrid_store):
        store = hybrid_store(make_settings(), StubEmbeddings(), make_chunks())
        assert store.search("   ") == []

    def test_new_chunks_are_searchable(self, hybrid_store, monkeypatch):
        """BM25 索引必须在上传后失效重建，否则新文件检索不到"""
        settings = make_settings(rag_rerank_enabled=False)
        store = hybrid_store(settings, StubEmbeddings(), make_chunks())

        store.add_chunks(
            "d.txt",
            b"new",
            [TextChunk(content="新增角色：凑斗景明", index=0, source="d.txt")],
        )

        hits = store.search("凑斗景明", top_k=3)
        assert any(hit.source == "d.txt" for hit in hits)
