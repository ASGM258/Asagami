"""
知识库集合的维度隔离与旧集合迁移测试

背景：Chroma 集合的向量维度在创建时固定，切换 embedding 提供方
（本地兜底 512 维 ↔ DashScope 1024 维）会直接报
`Collection expecting embedding with dimension of 512, got 1024`。

验证：
1. 集合名带上 embedding 空间标识，不同提供方互不干扰
2. 旧固定名集合会被用当前 embedding 重新向量化后迁移，并删除
3. 迁移失败时旧数据保留、不阻断正常上传
4. 同一空间重复初始化不会重复迁移
"""

import chromadb
import pytest
from chromadb.config import Settings as ChromaSettings

from app.config import Settings
from app.rag.embeddings import BaseEmbeddings, DashScopeEmbeddings, LocalHashEmbeddings
from app.rag.loaders import TextChunk
from app.rag.store import (
    LEGACY_COLLECTION_NAME,
    KnowledgeStore,
    collection_name_for,
)


@pytest.fixture
def client():
    """
    内存 Chroma 客户端

    注意 chromadb 的 EphemeralClient 在**同一进程内共享后端状态**，
    不做 reset 会串味到其他测试（能看到别的测试建的集合），因此前后都清一次。
    """
    ephemeral = chromadb.EphemeralClient(
        settings=ChromaSettings(
            anonymized_telemetry=False, allow_reset=True, is_persistent=False
        )
    )
    ephemeral.reset()
    try:
        yield ephemeral
    finally:
        try:
            ephemeral.reset()
        except Exception:  # noqa: BLE001 - 清理失败不影响断言结果
            pass


class StubEmbeddings(BaseEmbeddings):
    """固定维度的假 embedding（不发网络请求）"""

    def __init__(self, dim: int, identity: str, semantic: bool = True, failing: bool = False):
        self._dim = dim
        self._identity = identity
        self.semantic = semantic
        self.name = f"stub-{identity}"
        self.failing = failing
        self.embed_calls = 0

    @property
    def identity(self) -> str:
        return self._identity

    def _vectors(self, count: int) -> list[list[float]]:
        # 第 i 位取 (i+1)/dim，保证非零且与维度绑定
        base = [(i + 1) / self._dim for i in range(self._dim)]
        return [list(base) for _ in range(count)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        if self.failing:
            raise RuntimeError("embedding 服务不可用")
        return self._vectors(len(texts))

    def embed_query(self, text: str) -> list[float]:
        if self.failing:
            raise RuntimeError("embedding 服务不可用")
        return self._vectors(1)[0]


def make_settings(**overrides) -> Settings:
    defaults = dict(deepseek_api_key="t", llm_model="fake")
    defaults.update(overrides)
    return Settings(**defaults)


def make_chunks(count: int = 2, source: str = "a.txt") -> list[TextChunk]:
    return [
        TextChunk(content=f"第{i}段内容", index=i, source=source, offset=i * 10)
        for i in range(count)
    ]


def seed_legacy_collection(client, dim: int = 512, count: int = 2) -> None:
    """模拟早期版本：固定名集合 + 512 维向量"""
    legacy = client.get_or_create_collection(
        name=LEGACY_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    legacy.upsert(
        ids=[f"fp-{i}" for i in range(count)],
        documents=[f"旧块{i}" for i in range(count)],
        embeddings=[[0.5] * dim for _ in range(count)],
        metadatas=[
            {
                "source": "old.txt",
                "chunk_index": i,
                "offset": 0,
                "fingerprint": "fp",
                "semantic": False,
            }
            for i in range(count)
        ],
    )


def collection_names(client) -> set[str]:
    return {getattr(item, "name", item) for item in client.list_collections()}


# ==================== 1. 集合命名 ====================


class TestCollectionNaming:
    def test_local_embeddings_name_contains_dim(self):
        assert collection_name_for(LocalHashEmbeddings()) == (
            "anime_knowledge__local_hash_512"
        )

    def test_dashscope_name_contains_model(self):
        embeddings = DashScopeEmbeddings(
            api_key="x", model="text-embedding-v3", base_url="https://example.com/v1"
        )
        assert collection_name_for(embeddings) == (
            "anime_knowledge__dashscope_text_embedding_v3"
        )

    def test_different_spaces_get_different_collections(self):
        local = LocalHashEmbeddings()
        dashscope = DashScopeEmbeddings(
            api_key="x", model="text-embedding-v3", base_url="https://example.com/v1"
        )
        assert collection_name_for(local) != collection_name_for(dashscope)

    def test_switching_model_changes_collection(self):
        v3 = DashScopeEmbeddings(
            api_key="x", model="text-embedding-v3", base_url="https://example.com/v1"
        )
        v4 = DashScopeEmbeddings(
            api_key="x", model="text-embedding-v4", base_url="https://example.com/v1"
        )
        assert collection_name_for(v3) != collection_name_for(v4)

    def test_name_is_chroma_safe(self):
        """Chroma 集合名只允许字母数字与 _ -，且 3-512 字符"""
        for embeddings in (
            LocalHashEmbeddings(),
            DashScopeEmbeddings(api_key="x", model="BAAI/bge-m3", base_url="https://e/v1"),
        ):
            name = collection_name_for(embeddings)
            assert 3 <= len(name) <= 512
            assert name.replace("_", "").isalnum(), name


# ==================== 2. 旧集合迁移 ====================


class TestLegacyMigration:
    def test_migrates_512_to_1024(self, client):
        seed_legacy_collection(client, dim=512, count=2)

        store = KnowledgeStore(
            make_settings(),
            StubEmbeddings(1024, "dashscope-text-embedding-v3"),
            client=client,
        )

        # 访问 collection 时触发迁移
        assert store.count() == 2
        assert LEGACY_COLLECTION_NAME not in collection_names(client)
        assert store.collection_name in collection_names(client)

    def test_migrated_vectors_use_new_dimension(self, client):
        """迁移后必须能用新维度检索，否则等于没修"""
        seed_legacy_collection(client, dim=512, count=2)

        store = KnowledgeStore(
            make_settings(), StubEmbeddings(1024, "dashscope-v3"), client=client
        )

        hits = store.search("查询", top_k=2)
        assert hits, "迁移后应能检索到旧数据"
        assert {hit.source for hit in hits} == {"old.txt"}

    def test_migration_updates_semantic_flag(self, client):
        seed_legacy_collection(client, dim=512, count=1)

        store = KnowledgeStore(
            make_settings(),
            StubEmbeddings(1024, "semantic-model", semantic=True),
            client=client,
        )
        data = store.collection.get(include=["metadatas"])

        assert all(m.get("semantic") is True for m in data["metadatas"])

    def test_no_migration_without_legacy_collection(self, client):
        store = KnowledgeStore(make_settings(), StubEmbeddings(1024, "v3"), client=client)

        assert store.count() == 0
        assert store.collection_name in collection_names(client)

    def test_failed_migration_keeps_old_data(self, client):
        seed_legacy_collection(client, dim=512, count=2)

        store = KnowledgeStore(
            make_settings(),
            StubEmbeddings(1024, "broken", failing=True),
            client=client,
        )

        # 迁移失败不应抛异常，也不应删除旧集合
        assert store.count() == 0
        assert LEGACY_COLLECTION_NAME in collection_names(client)
        assert client.get_collection(LEGACY_COLLECTION_NAME).count() == 2

    def test_empty_legacy_collection_is_discarded(self, client):
        client.get_or_create_collection(
            name=LEGACY_COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

        store = KnowledgeStore(make_settings(), StubEmbeddings(1024, "v3"), client=client)
        assert store.count() == 0
        assert LEGACY_COLLECTION_NAME not in collection_names(client)

    def test_same_space_reinit_does_not_migrate_again(self, client):
        seed_legacy_collection(client, dim=512, count=2)
        embeddings = StubEmbeddings(1024, "v3")

        first = KnowledgeStore(make_settings(), embeddings, client=client)
        assert first.count() == 2
        calls_after_first = embeddings.embed_calls

        second = KnowledgeStore(make_settings(), embeddings, client=client)
        assert second.count() == 2
        assert embeddings.embed_calls == calls_after_first, "第二次不应重新向量化"


# ==================== 3. 切空间后写入不再报维度错误 ====================


class TestWriteAfterSwitch:
    def test_add_chunks_uses_space_specific_collection(self, client):
        # 先用 512 维写一份（模拟配置密钥之前）
        local_store = KnowledgeStore(
            make_settings(), StubEmbeddings(512, "local-hash-512"), client=client
        )
        local_store.add_chunks("a.txt", b"abc", make_chunks(1))
        assert local_store.count() == 1

        # 再切到 1024 维写另一份：不应报维度错误
        dash_store = KnowledgeStore(
            make_settings(), StubEmbeddings(1024, "dashscope-v3"), client=client
        )
        written = dash_store.add_chunks("b.txt", b"xyz", make_chunks(2, source="b.txt"))

        assert written == 2
        assert dash_store.count() == 2
        # 两个空间各自存在，互不干扰
        assert local_store.collection_name != dash_store.collection_name
        names = collection_names(client)
        assert local_store.collection_name in names
        assert dash_store.collection_name in names
