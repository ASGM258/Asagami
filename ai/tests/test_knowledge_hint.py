"""
知识库清单注入（KnowledgeHintMiddleware）测试

要解决的真实问题：用户问「绫弥一条」，模型不认识这个名字，直接回答"没有相关资料"，
用户提醒"RAG 里有它才去检索 —— 因为模型不知道知识库里有什么。

验证：
1. 提示文本包含文件名与"未检索不得声称没有资料"的硬规则
2. 中间件只在每轮开头注入（工具循环中不重复），使用固定 id 避免堆积
3. 注入内容真的到达模型（端到端）
4. 流式过滤器会挡掉这条注入消息
5. 知识库为空 / 读取失败时不注入、不影响对话
6. 文件清单有缓存，且上传新文件后立即失效
"""

import asyncio

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

import app.agent.knowledge as K
from app.agent.graph import AnimeAgentFactory
from app.agent.knowledge import (
    KNOWLEDGE_HINT_ID,
    KNOWLEDGE_HINT_SOURCE,
    KnowledgeHintMiddleware,
    build_knowledge_hint,
)
from app.config import Settings
from app.rag.loaders import TextChunk
from app.services.stream_filter import is_internal_chunk


class FakeStore:
    """只提供 list_sources 的假知识库"""

    def __init__(self, files=None, failing: bool = False) -> None:
        self._files = files or []
        self.failing = failing
        self.calls = 0

    def list_sources(self):
        self.calls += 1
        if self.failing:
            raise RuntimeError("chroma 挂了")
        return list(self._files)


class RecordingModel(BaseChatModel):
    """记录每次模型调用收到的消息"""

    prompts: list[list] = []

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN201
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        type(self).prompts.append(list(messages))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="收到"))]
        )


def make_settings() -> Settings:
    return Settings(deepseek_api_key="t", llm_model="fake")


FILES = [
    {"source": "绫弥一条简介.txt", "chunks": 2},
    {"source": "rag_test.txt", "chunks": 1},
]


# ==================== 1. 提示文本 ====================


class TestHintText:
    def test_lists_file_names(self):
        hint = build_knowledge_hint(FILES)

        assert hint is not None
        assert "绫弥一条简介.txt" in hint
        assert "2 个文件" in hint
        assert "3 个片段" in hint

    def test_contains_hard_rule_against_premature_denial(self):
        hint = build_knowledge_hint(FILES)
        assert "search_knowledge_base" in hint
        assert "未检索之前" in hint
        assert "没有相关资料" in hint

    def test_mentions_name_overlap_hint(self):
        """提示模型：用户提到的名字与文件名重合时必须检索"""
        hint = build_knowledge_hint(FILES)
        assert "文件名" in hint
        assert "重合" in hint

    def test_empty_knowledge_base_returns_none(self):
        assert build_knowledge_hint([]) is None
        assert build_knowledge_hint([{"source": "", "chunks": 0}]) is None

    def test_caps_listed_files(self):
        many = [{"source": f"file{i}.txt", "chunks": 1} for i in range(50)]
        hint = build_knowledge_hint(many)

        assert hint is not None
        assert "file0.txt" in hint
        assert "50 个文件" in hint
        # 只列前若干个，避免把 prompt 撑爆
        assert hint.count(".txt") <= K.MAX_LISTED_FILES


# ==================== 2. 中间件行为 ====================


class TestMiddleware:
    def test_injects_on_turn_start(self):
        middleware = KnowledgeHintMiddleware(store_provider=lambda: FakeStore(FILES))
        result = middleware.before_model({"messages": [HumanMessage(content="绫弥一条")]}, None)

        assert result is not None
        message = result["messages"][0]
        assert isinstance(message, SystemMessage)
        assert message.id == KNOWLEDGE_HINT_ID
        assert message.additional_kwargs["lc_source"] == KNOWLEDGE_HINT_SOURCE
        assert "绫弥一条简介.txt" in message.content

    def test_does_not_inject_after_tool_message(self):
        """工具调用后的续写不应重复注入"""
        middleware = KnowledgeHintMiddleware(store_provider=lambda: FakeStore(FILES))
        state = {"messages": [HumanMessage(content="q"), ToolMessage(content="{}", tool_call_id="1")]}

        assert middleware.before_model(state, None) is None

    def test_does_not_inject_after_ai_message(self):
        middleware = KnowledgeHintMiddleware(store_provider=lambda: FakeStore(FILES))
        state = {"messages": [HumanMessage(content="q"), AIMessage(content="a")]}

        assert middleware.before_model(state, None) is None

    def test_empty_knowledge_base_skips_injection(self):
        middleware = KnowledgeHintMiddleware(store_provider=lambda: FakeStore([]))
        assert middleware.before_model({"messages": [HumanMessage(content="q")]}, None) is None

    def test_store_failure_does_not_break_turn(self):
        middleware = KnowledgeHintMiddleware(
            store_provider=lambda: FakeStore(failing=True)
        )
        assert middleware.before_model({"messages": [HumanMessage(content="q")]}, None) is None

    def test_empty_messages(self):
        middleware = KnowledgeHintMiddleware(store_provider=lambda: FakeStore(FILES))
        assert middleware.before_model({"messages": []}, None) is None
        assert middleware.before_model({}, None) is None


# ==================== 3. 端到端：模型真的看到了清单 ====================


class TestEndToEnd:
    def test_model_receives_inventory(self, monkeypatch):
        RecordingModel.prompts = []
        monkeypatch.setattr(K, "get_knowledge_store", lambda: FakeStore(FILES))

        factory = AnimeAgentFactory(make_settings())
        factory.build(InMemorySaver(), llm=RecordingModel())
        config = {"configurable": {"thread_id": "kb-hint-e2e"}}

        asyncio.run(
            factory.agent.ainvoke(
                {"messages": [HumanMessage(content="绫弥一条是谁")], "user_id": 1}, config
            )
        )

        assert RecordingModel.prompts, "模型应至少被调用一次"
        joined = "\n".join(str(m.content) for m in RecordingModel.prompts[0])
        assert "绫弥一条简介.txt" in joined, "模型没收到知识库清单"
        assert "search_knowledge_base" in joined

    def test_injected_hint_does_not_leak_to_frontend(self):
        """注入的 SystemMessage 必须被流式过滤器挡掉"""
        assert is_internal_chunk(
            {"langgraph_node": "KnowledgeHintMiddleware.before_model"}
        )
        assert is_internal_chunk({"lc_source": KNOWLEDGE_HINT_SOURCE})
        # 正常模型节点不受影响
        assert not is_internal_chunk({"langgraph_node": "model"})

    def test_hint_does_not_accumulate_across_turns(self, monkeypatch):
        """固定 id 应让注入消息被原地替换，而不是每轮堆一条"""
        RecordingModel.prompts = []
        monkeypatch.setattr(K, "get_knowledge_store", lambda: FakeStore(FILES))

        factory = AnimeAgentFactory(make_settings())
        factory.build(InMemorySaver(), llm=RecordingModel())
        config = {"configurable": {"thread_id": "kb-hint-repeat"}}

        async def two_turns():
            for question in ("绫弥一条是谁", "她有什么弱点"):
                await factory.agent.ainvoke(
                    {"messages": [HumanMessage(content=question)], "user_id": 1}, config
                )
            snapshot = await factory.agent.aget_state(config)
            return list(snapshot.values.get("messages") or [])

        messages = asyncio.run(two_turns())
        hints = [
            m
            for m in messages
            if isinstance(m, SystemMessage) and m.id == KNOWLEDGE_HINT_ID
        ]

        assert len(hints) == 1, f"注入消息堆积了 {len(hints)} 条"
        assert "绫弥一条简介.txt" in hints[0].content


# ==================== 4. 文件清单缓存 ====================


class TestSourceCache:
    def _store(self):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        from app.rag.store import KnowledgeStore

        client = chromadb.EphemeralClient(
            settings=ChromaSettings(
                anonymized_telemetry=False, allow_reset=True, is_persistent=False
            )
        )
        client.reset()

        class StubEmbeddings:
            name = "stub"
            semantic = True
            identity = "stub-1024"

            def embed_documents(self, texts):
                return [[0.1] * 1024 for _ in texts]

            def embed_query(self, text):
                return [0.1] * 1024

        return KnowledgeStore(make_settings(), StubEmbeddings(), client=client)

    def test_list_sources_is_cached(self):
        store = self._store()
        store.add_chunks(
            "a.txt", b"abc", [TextChunk(content="内容", index=0, source="a.txt")]
        )

        first = store.list_sources()
        second = store.list_sources()

        assert first == second
        assert store._sources_cache is not None

    def test_cache_invalidated_after_upload(self):
        """上传新文件后必须立刻反映到清单，否则模型看到的还是旧清单"""
        store = self._store()
        store.add_chunks(
            "a.txt", b"abc", [TextChunk(content="内容1", index=0, source="a.txt")]
        )
        assert [item["source"] for item in store.list_sources()] == ["a.txt"]

        store.add_chunks(
            "绫弥一条简介.txt",
            b"xyz",
            [TextChunk(content="角色资料", index=0, source="绫弥一条简介.txt")],
        )

        sources = [item["source"] for item in store.list_sources()]
        assert "绫弥一条简介.txt" in sources

    def test_cache_invalidated_after_delete(self):
        store = self._store()
        store.add_chunks(
            "a.txt", b"abc", [TextChunk(content="内容1", index=0, source="a.txt")]
        )
        assert store.list_sources()

        store.delete_by_source("a.txt")
        assert store.list_sources() == []
