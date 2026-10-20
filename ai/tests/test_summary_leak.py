"""
上下文摘要不得泄漏到前端的回归测试

背景：`stream_mode="messages"` 会把图上**所有**模型调用的产出都流出来，
包括 `SummarizationMiddleware` 为了压缩上下文而发起的摘要调用。
实测这类 chunk 的 metadata 带 `lc_source="summarization"`，
或 `langgraph_node == "ContextSummaryMiddleware.before_model"`。

测试用一个「会看 prompt 的假模型」：只有摘要调用（prompt 含"对话压缩助手"）
才返回带标记的文本，正常回答返回固定答案。这样标记一旦出现在对外出口，
就一定是内部笔记泄漏，而不是被误判的正常回答。
"""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import AnimeAgentFactory
from app.config import Settings
from app.dependencies import get_chat_service, get_session_service
from app.main import app
from app.services.chat_service import ChatService
from app.services.session_service import SessionService
from app.services.stream_filter import INTERNAL_NODE_PREFIXES, is_internal_chunk
from tests.conftest import FakeSessionStore

#: 摘要里埋的标记：只要它出现在对外的任何位置，就说明内部笔记泄漏了
LEAK_MARKER = "SUMMARY_INTERNAL_MARKER"
#: 真实的回答文本
ANSWER = "这是最终回答。"
#: 摘要 prompt 的特征串（CONTEXT_SUMMARY_PROMPT 的首句）
SUMMARY_PROMPT_HINT = "对话压缩助手"


class PromptAwareFakeModel(BaseChatModel):
    """摘要调用返回带标记的文本，正常回答返回固定答案"""

    @property
    def _llm_type(self) -> str:
        return "prompt-aware-fake"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN201
        return self

    @staticmethod
    def _prompt_of(messages) -> str:  # noqa: ANN001
        return "\n".join(str(getattr(message, "content", "")) for message in messages)

    def _text_for(self, messages) -> str:  # noqa: ANN001
        if SUMMARY_PROMPT_HINT in self._prompt_of(messages):
            return f"{LEAK_MARKER} 用户问过命运石之门，未完成：魔法使之夜"
        return ANSWER

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ANN001
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self._text_for(messages)))]
        )

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        # 逐字吐出，模拟真实模型的 token 流
        for char in self._text_for(messages):
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=char))
            if run_manager:
                run_manager.on_llm_new_token(char, chunk=chunk)
            yield chunk


def make_settings() -> Settings:
    """把压缩阈值调低，保证第二轮就触发摘要"""
    return Settings(
        deepseek_api_key="test",
        llm_model="fake",
        context_summarization_enabled=True,
        context_trigger_messages=2,
        context_trigger_tokens=0,
        context_keep_messages=1,
    )


@pytest.fixture
def summarizing_client():
    settings = make_settings()
    store = FakeSessionStore()
    factory = AnimeAgentFactory(settings)
    factory.build(InMemorySaver(), llm=PromptAwareFakeModel())

    session_service = SessionService(store, factory, settings)
    chat_service = ChatService(store, factory, session_service)

    app.dependency_overrides[get_chat_service] = lambda: chat_service
    app.dependency_overrides[get_session_service] = lambda: session_service

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def parse_sse(text: str) -> list[dict]:
    payloads = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            payloads.append(json.loads(block[len("data: "):]))
    return payloads


def stream_question(client, question: str, session_id: str | None = None) -> list[dict]:
    payload = {"question": question, "user_id": 1}
    if session_id:
        payload["session_id"] = session_id
    response = client.post("/api/anime-chat-stream", json=payload)
    assert response.status_code == 200
    return parse_sse(response.text)


class TestIsInternalChunk:
    """metadata 判据本身（用实测到的真实结构）"""

    def test_detects_summarization_source(self):
        # 摘要模型调用：带 lc_source
        assert is_internal_chunk({"lc_source": "summarization"})

    def test_detects_summarization_node(self):
        # 摘要中间件作为节点出现（含它注入的 SystemMessage）
        metadata = {
            "langgraph_node": "ContextSummaryMiddleware.before_model",
            "langgraph_step": 6,
        }
        assert is_internal_chunk(metadata)

    def test_real_model_node_is_kept(self):
        assert not is_internal_chunk({"langgraph_node": "model", "langgraph_step": 7})

    def test_tool_node_is_kept(self):
        assert not is_internal_chunk({"langgraph_node": "tools"})

    def test_missing_or_empty_metadata(self):
        assert not is_internal_chunk(None)
        assert not is_internal_chunk({})

    def test_prefix_list_matches_our_middleware(self):
        from app.agent.graph import ContextSummaryMiddleware

        assert ContextSummaryMiddleware.__name__ in INTERNAL_NODE_PREFIXES


class TestSummaryDoesNotLeak:
    """真实链路：触发压缩后，内部笔记不能出现在任何对外出口"""

    def test_streaming_never_contains_summary(self, summarizing_client):
        first = stream_question(summarizing_client, "命运石之门怎么样")
        session_id = [p for p in first if p.get("type") == "end"][0]["session_id"]

        # 第二轮：历史变长，触发摘要压缩
        second = stream_question(summarizing_client, "魔法使之夜呢", session_id)

        content = "".join(p.get("chunk", "") for p in second if p.get("type") == "content")
        assert LEAK_MARKER not in content, f"摘要内容泄漏到流式正文: {content!r}"
        assert ANSWER in content, f"正常回答被误删: {content!r}"

    def test_history_never_contains_summary(self, summarizing_client):
        first = stream_question(summarizing_client, "命运石之门怎么样")
        session_id = [p for p in first if p.get("type") == "end"][0]["session_id"]
        stream_question(summarizing_client, "魔法使之夜呢", session_id)

        messages = summarizing_client.get(
            f"/api/session/{session_id}/messages"
        ).json()["data"]["messages"]

        joined = "".join(m["content"] for m in messages)
        assert LEAK_MARKER not in joined, f"摘要内容泄漏到历史接口: {joined!r}"

    def test_non_streaming_answer_never_contains_summary(self, summarizing_client):
        first = summarizing_client.post(
            "/api/anime-chat", json={"question": "命运石之门怎么样", "user_id": 1}
        ).json()["data"]
        session_id = first["session_id"]

        second = summarizing_client.post(
            "/api/anime-chat",
            json={"question": "魔法使之夜呢", "user_id": 1, "session_id": session_id},
        ).json()["data"]

        assert second["answer"] == ANSWER, second["answer"]
        assert LEAK_MARKER not in second["answer"]

    def test_summarization_really_happened(self, summarizing_client):
        """确保这条回归测试真的走到了压缩路径，否则等于没测"""
        first = stream_question(summarizing_client, "命运石之门怎么样")
        session_id = [p for p in first if p.get("type") == "end"][0]["session_id"]
        stream_question(summarizing_client, "魔法使之夜呢", session_id)

        messages = summarizing_client.get(
            f"/api/session/{session_id}/messages"
        ).json()["data"]["messages"]

        # 压缩后历史里应出现"已摘要"的痕迹：轮次被折叠，只剩最近几条
        assert len(messages) <= 3, f"历史未被压缩: {messages}"

    def test_stream_still_produces_an_answer(self, summarizing_client):
        """过滤不能过头"""
        payloads = stream_question(summarizing_client, "命运石之门怎么样")
        content = "".join(p.get("chunk", "") for p in payloads if p.get("type") == "content")

        assert content.strip(), "过滤内部调用时不能把正常回答一起丢掉"
        assert len([p for p in payloads if p.get("type") == "end"]) == 1
