"""
端点级集成测试：真实工具调用下的流式过滤

用会真正调用工具的假模型 + InMemorySaver，走完整的
「HTTP 端点 → ChatService → AnswerStreamFilter → SSE 帧」链路，
验证：
1. ToolMessage 内容不会出现在 SSE 正文里
2. 过渡语（"我需要先查询一下资料。"）会正常展示
3. 会发出 tool / thinking 事件供前端转圈，且没有 retract
4. 最终正文 = 过渡语 + 最终答案，与历史接口拼接结果一致

这样即使没有 PostgreSQL 也能验证接线是否正确。
"""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graph import AnimeAgentFactory
from app.config import Settings
from app.dependencies import get_chat_service, get_session_service
from app.main import app
from app.services.chat_service import ChatService
from app.services.session_service import SessionService
from tests.conftest import FakeSessionStore

# 模型先说的那句过渡语，新策略下应当照常展示
TRANSITION = "我需要先查询一下资料。"
FINAL_ANSWER = "最终答案：庵野秀明执导 EVA。"
FULL_TEXT = TRANSITION + FINAL_ANSWER


class ToolCallingFakeModel(FakeMessagesListChatModel):
    """先输出过渡语 + 调用真实工具，再输出最终答案"""

    def bind_tools(self, tools, **kwargs):
        return self


def build_tool_calling_model(final_answer: str) -> ToolCallingFakeModel:
    """
    构造一个会调用真实工具（get_anime_info）的模型

    注意工具名必须是注册过的真实工具，否则会返回 "not a valid tool"
    而干扰断言。
    """
    return ToolCallingFakeModel(
        responses=[
            # 第 1 轮：过渡语 + 工具调用
            AIMessage(
                content=TRANSITION,
                tool_calls=[
                    {
                        "name": "get_anime_info",
                        "args": {"anime_id": 1},
                        "id": "call_1",
                    }
                ],
            ),
            # 第 2 轮：最终答案
            AIMessage(content=final_answer),
            # 备用，避免轮次不够
            AIMessage(content=final_answer),
        ]
    )


@pytest.fixture
def streaming_client(monkeypatch):
    """构造注入了「会调工具」的 Agent 与内存会话存储的测试客户端"""
    settings = Settings(deepseek_api_key="test", llm_model="fake")
    store = FakeSessionStore()

    factory = AnimeAgentFactory(settings)
    factory.build(InMemorySaver(), llm=build_tool_calling_model(FINAL_ANSWER))

    session_service = SessionService(store, factory, settings)
    chat_service = ChatService(store, factory, session_service)

    # 覆盖依赖，避免走需要 PostgreSQL 的真实服务
    app.dependency_overrides[get_chat_service] = lambda: chat_service
    app.dependency_overrides[get_session_service] = lambda: session_service

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def parse_sse(text: str) -> list[dict]:
    """解析 SSE 文本为负载列表"""
    payloads = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            payloads.append(json.loads(block[len("data: "):]))
    return payloads


def render_like_frontend(payloads: list[dict]) -> str:
    """按前端语义还原展示文本（content 追加；retract 已不再出现）"""
    shown = ""
    for p in payloads:
        if p.get("type") == "content":
            shown += p.get("chunk", "")
        elif p.get("type") == "retract":
            shown = ""
    return shown


class TestStreamFilteringThroughEndpoint:
    """经真实 HTTP 端点验证过滤效果"""

    def test_transition_text_and_final_answer_reach_frontend(self, streaming_client):
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )

        assert response.status_code == 200
        payloads = parse_sse(response.text)
        content_text = "".join(
            p.get("chunk", "") for p in payloads if p.get("type") == "content"
        )
        shown = render_like_frontend(payloads)

        # 过渡语 + 最终答案都在，且顺序正确
        assert shown == FULL_TEXT, f"实际展示: {shown!r}"
        assert shown == content_text

    def test_tool_result_never_leaks(self, streaming_client):
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        payloads = parse_sse(response.text)
        content_text = "".join(
            p.get("chunk", "") for p in payloads if p.get("type") == "content"
        )

        # 工具返回的原始 JSON 结构不能出现在正文里
        assert "anime_title" not in content_text
        assert "watch_status" not in content_text

    def test_no_retract_frames(self, streaming_client):
        """新策略不撤回已下发内容"""
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        payloads = parse_sse(response.text)
        assert not [p for p in payloads if p.get("type") == "retract"]

    def test_thinking_events_emitted_for_spinner(self, streaming_client):
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        payloads = parse_sse(response.text)

        thinking = [p for p in payloads if p.get("type") == "thinking"]
        assert thinking, "应至少发出一个 thinking 事件，供前端显示转圈"

        tools = [p.get("tool") for p in thinking if p.get("stage") == "tool"]
        assert "get_anime_info" in tools, f"应携带真实工具名，实际: {tools}"

        # 工具执行完还会切回「正在思考」
        assert "thinking" in [p.get("stage") for p in thinking]

    def test_no_tool_message_frames(self, streaming_client):
        """SSE 帧里不应出现工具结果的痕迹"""
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )

        # 整体响应文本里不应出现工具返回的 JSON 结构
        assert "anime_title" not in response.text
        assert "watch_status_text" not in response.text

    def test_exactly_one_end_and_no_error(self, streaming_client):
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        payloads = parse_sse(response.text)

        assert len([p for p in payloads if p.get("type") == "end"]) == 1
        assert not [p for p in payloads if p.get("type") == "error"]

    def test_end_carries_ids(self, streaming_client):
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        end = [p for p in parse_sse(response.text) if p.get("type") == "end"][0]

        assert end["session_id"].startswith("session_")
        assert end["message_id"].startswith("msg_")

    def test_history_matches_streamed_bubble(self, streaming_client):
        """
        刷新会话看到的历史必须和流式时那个气泡一模一样

        过渡语是单独一条 AIMessage，历史接口若原样返回会变成两个气泡。
        """
        response = streaming_client.post(
            "/api/anime-chat-stream",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        payloads = parse_sse(response.text)
        streamed = render_like_frontend(payloads)
        session_id = [p for p in payloads if p.get("type") == "end"][0]["session_id"]

        history = streaming_client.get(f"/api/session/{session_id}/messages")
        assert history.status_code == 200

        messages = history.json()["data"]["messages"]
        assistants = [m for m in messages if m["role"] == "assistant"]

        assert len(assistants) == 1, f"应合并成一个气泡，实际 {len(assistants)} 个"
        assert assistants[0]["content"] == streamed

        # 合并后的 message_id 必须与 end 事件一致
        end_message_id = [p for p in payloads if p.get("type") == "end"][0]["message_id"]
        assert assistants[0]["message_id"] == end_message_id


class TestNonStreamingConsistency:
    """非流式接口返回同一份正文"""

    def test_non_stream_answer_includes_transition(self, streaming_client):
        response = streaming_client.post(
            "/api/anime-chat",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["answer"] == FULL_TEXT
        assert "anime_title" not in data["answer"]
        assert data["message_id"].startswith("msg_")


def build_multi_turn_model() -> ToolCallingFakeModel:
    """两轮对话，每轮都是「过渡语 + 工具 + 最终答案」"""
    return ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="我来查一下。",
                tool_calls=[{"name": "get_anime_info", "args": {"anime_id": 1}, "id": "c1"}],
            ),
            AIMessage(content="第一轮答案。"),
            AIMessage(
                content="我再查一下。",
                tool_calls=[{"name": "get_anime_info", "args": {"anime_id": 2}, "id": "c2"}],
            ),
            AIMessage(content="第二轮答案。"),
            AIMessage(content="备用"),
            AIMessage(content="备用"),
        ]
    )


@pytest.fixture
def multi_turn_client():
    settings = Settings(deepseek_api_key="test", llm_model="fake")
    store = FakeSessionStore()
    factory = AnimeAgentFactory(settings)
    factory.build(InMemorySaver(), llm=build_multi_turn_model())

    session_service = SessionService(store, factory, settings)
    chat_service = ChatService(store, factory, session_service)

    app.dependency_overrides[get_chat_service] = lambda: chat_service
    app.dependency_overrides[get_session_service] = lambda: session_service

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


class TestMultiTurnScoping:
    """
    多轮会话的关键回归：不能把历史各轮的答案串进本轮

    LangGraph 带检查点时 ainvoke 返回整个会话的 messages，
    早前版本直接拼接会导致第二轮 answer = 第一轮答案 + 第二轮答案。
    """

    def test_second_turn_answer_does_not_include_first_turn(self, multi_turn_client):
        first = multi_turn_client.post(
            "/api/anime-chat",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        )
        first_data = first.json()["data"]
        assert first_data["answer"] == "我来查一下。第一轮答案。"
        session_id = first_data["session_id"]

        second = multi_turn_client.post(
            "/api/anime-chat",
            json={
                "question": "我的追番历史怎么样",
                "user_id": 1,
                "session_id": session_id,
            },
        )
        second_data = second.json()["data"]

        assert second_data["answer"] == "我再查一下。第二轮答案。", (
            f"第二轮串入了历史答案: {second_data['answer']!r}"
        )
        assert "第一轮答案" not in second_data["answer"]

        # 两轮的 message_id 必须不同（不能回溯到上一轮）
        assert second_data["message_id"] != first_data["message_id"]

    def test_history_has_one_bubble_per_turn(self, multi_turn_client):
        first = multi_turn_client.post(
            "/api/anime-chat",
            json={"question": "我的追番历史怎么样", "user_id": 1},
        ).json()["data"]
        session_id = first["session_id"]

        multi_turn_client.post(
            "/api/anime-chat",
            json={
                "question": "我的追番历史怎么样",
                "user_id": 1,
                "session_id": session_id,
            },
        )

        messages = multi_turn_client.get(
            f"/api/session/{session_id}/messages"
        ).json()["data"]["messages"]

        roles = [m["role"] for m in messages]
        assert roles == ["user", "assistant", "user", "assistant"], f"实际: {roles}"

        assert messages[1]["content"] == "我来查一下。第一轮答案。"
        assert messages[3]["content"] == "我再查一下。第二轮答案。"

