"""
会话与聊天服务的契约测试

覆盖「图 + 检查点 + 服务 + SSE」全链路（检查点使用 InMemorySaver），
重点验证对外字段与重构前的接口契约完全一致。
"""

import asyncio
import json

import pytest

from app.core.errors import SessionNotFoundError
from app.services.chat_service import NON_ANIME_REPLY
from tests.conftest import FAKE_ANSWER

# 契约要求的时间格式
TIMESTAMP_FORMAT_HINT = "2026-01-01 00:00:00"


def parse_frames(frames: list[str]) -> list[dict]:
    """把 SSE 片段列表解析为负载列表"""
    payloads = []
    for frame in frames:
        assert frame.startswith("data: ")
        assert frame.endswith("\n\n")
        payloads.append(json.loads(frame[len("data: "): -2]))
    return payloads


def run_stream(chat_service, question, user_id, session_id):
    """同步执行异步流式接口，返回 SSE 片段列表"""

    async def collect():
        return [frame async for frame in chat_service.stream_answer(question, user_id, session_id)]

    return asyncio.run(collect())


def run_answer(chat_service, question, user_id, session_id):
    """同步执行异步非流式接口"""
    return asyncio.run(chat_service.answer(question, user_id, session_id))


class TestSessionContract:
    """会话元数据接口契约"""

    def test_create_session_shape(self, session_service):
        result = session_service.create_session(user_id=7)

        # 契约：{session_id, title}
        assert set(result.keys()) == {"session_id", "title"}
        assert result["session_id"].startswith("session_")
        assert result["title"] == "新会话"

    def test_create_session_with_title(self, session_service):
        result = session_service.create_session(user_id=7, title="我的会话")
        assert result["title"] == "我的会话"

    def test_list_sessions_items_shape(self, session_service):
        session_service.create_session(user_id=7, title="会话A")

        sessions = session_service.list_sessions(user_id=7)

        assert len(sessions) == 1
        # 契约：列表条目仅含这四个字段
        assert set(sessions[0].keys()) == {
            "session_id",
            "title",
            "created_at",
            "updated_at",
        }

    def test_list_sessions_filters_by_user(self, session_service):
        session_service.create_session(user_id=7)
        session_service.create_session(user_id=8)

        assert len(session_service.list_sessions(user_id=7)) == 1
        assert len(session_service.list_sessions(user_id=99)) == 0

    def test_require_session_raises_for_unknown(self, session_service):
        with pytest.raises(SessionNotFoundError) as exc_info:
            session_service.require_session("session_not_exist")

        assert exc_info.value.error_code == "SESSION_NOT_FOUND"
        assert exc_info.value.http_status == 404

    def test_soft_deleted_session_is_not_found(self, session_service):
        session_id = session_service.create_session(user_id=7)["session_id"]
        session_service.delete_session(session_id, hard=False)

        with pytest.raises(SessionNotFoundError):
            session_service.require_session(session_id)

    def test_update_title(self, session_service):
        session_id = session_service.create_session(user_id=7)["session_id"]

        assert session_service.update_title(session_id, "新标题") is True
        assert session_service.require_session(session_id)["title"] == "新标题"

    def test_update_title_unknown_session_returns_false(self, session_service):
        assert session_service.update_title("session_nope", "x") is False

    def test_hard_delete_removes_session(self, session_service):
        session_id = session_service.create_session(user_id=7)["session_id"]

        assert session_service.delete_session(session_id, hard=True) is True
        assert session_service.get_session(session_id) is None


class TestChatNonStreaming:
    """非流式问答契约"""

    def test_answer_fields(self, chat_service):
        result = run_answer(chat_service, "请推荐一些好看的动漫", 7, None)

        # 契约字段
        assert set(result.keys()) == {
            "answer",
            "is_anime_related",
            "user_id",
            "session_id",
            "message_id",
        }
        assert result["answer"] == FAKE_ANSWER
        assert result["is_anime_related"] is True
        assert result["user_id"] == 7
        assert result["session_id"].startswith("session_")
        # message_id 由中间件写入，格式为 msg_ + 16 位
        assert result["message_id"].startswith("msg_")

    def test_answer_creates_session_with_question_title(self, chat_service, store):
        result = run_answer(chat_service, "请推荐一些好看的动漫作品谢谢啦", 7, None)
        session = store.get_session_info(result["session_id"])

        assert session["user_id"] == 7
        # 标题取问题前 20 字
        assert session["title"] == "请推荐一些好看的动漫作品谢谢啦"[:20]

    def test_answer_without_user_has_no_session(self, chat_service):
        result = run_answer(chat_service, "请推荐一些好看的动漫", None, None)

        # 未登录用户不产生任何会话
        assert result["session_id"] is None
        assert result["user_id"] is None
        # 但回答本身仍应正常返回并带有消息ID
        assert result["answer"] == FAKE_ANSWER
        assert result["message_id"].startswith("msg_")

    def test_answer_without_user_creates_no_checkpoint(self, chat_service, store):
        """未登录用户不应留下任何会话元数据"""
        run_answer(chat_service, "请推荐一些好看的动漫", None, None)
        assert store.sessions == {}

    def test_non_anime_question_short_circuits(self, chat_service, store):
        result = run_answer(chat_service, "请帮我写一段快速排序的代码实现", 7, None)

        assert result["is_anime_related"] is False
        assert result["answer"] == NON_ANIME_REPLY
        # 不应创建会话
        assert store.sessions == {}

    def test_answer_rejects_unknown_session(self, chat_service):
        with pytest.raises(SessionNotFoundError):
            run_answer(chat_service, "请推荐动漫", 7, "session_ghost")


class TestChatStreaming:
    """流式问答与 SSE 契约"""

    def test_stream_frame_sequence(self, chat_service):
        frames = run_stream(chat_service, "请推荐一些好看的动漫", 7, None)
        payloads = parse_frames(frames)

        content_payloads = [p for p in payloads if p["type"] == "content"]
        end_payloads = [p for p in payloads if p["type"] == "end"]

        assert content_payloads, "应至少产生一个 content 事件"
        assert len(end_payloads) == 1, "应恰好产生一个 end 事件"

        # 每个 content 事件字段
        for payload in content_payloads:
            assert set(payload.keys()) == {"success", "chunk", "type"}
            assert payload["success"] is True

        # end 事件必须是最后一个
        assert payloads[-1]["type"] == "end"

    def test_stream_accumulates_to_full_answer(self, chat_service):
        frames = run_stream(chat_service, "请推荐一些好看的动漫", 7, None)
        payloads = parse_frames(frames)

        accumulated = "".join(
            p["chunk"] for p in payloads if p["type"] == "content"
        )
        assert accumulated == FAKE_ANSWER

    def test_stream_is_token_level(self, chat_service):
        """逐 token 输出：片段数应大于 1"""
        frames = run_stream(chat_service, "请推荐一些好看的动漫", 7, None)
        payloads = parse_frames(frames)
        assert len([p for p in payloads if p["type"] == "content"]) > 1

    def test_stream_end_carries_ids(self, chat_service):
        frames = run_stream(chat_service, "请推荐一些好看的动漫", 7, None)
        end = parse_frames(frames)[-1]

        assert end["session_id"].startswith("session_")
        assert end["message_id"].startswith("msg_")
        assert end["chunk"] == ""

    def test_stream_non_anime_emits_error_event(self, chat_service):
        frames = run_stream(chat_service, "请帮我写一段快速排序的代码实现", 7, None)
        payloads = parse_frames(frames)

        assert len(payloads) == 1
        assert payloads[0]["type"] == "error"
        assert payloads[0]["is_anime_related"] is False
        assert payloads[0]["chunk"] == NON_ANIME_REPLY

    def test_stream_unknown_session_emits_error_event(self, chat_service):
        frames = run_stream(chat_service, "请推荐动漫", 7, "session_ghost")
        payloads = parse_frames(frames)

        assert payloads[0]["type"] == "error"
        assert "会话不存在" in payloads[0]["error"]

    def test_stream_without_user_still_answers(self, chat_service):
        frames = run_stream(chat_service, "请推荐一些好看的动漫", None, None)
        payloads = parse_frames(frames)

        assert payloads[-1]["type"] == "end"
        assert payloads[-1]["session_id"] is None


class TestCheckpointHistory:
    """检查点驱动的消息历史契约"""

    def test_messages_shape_and_roles(self, chat_service, session_service):
        result = run_answer(chat_service, "请推荐一些好看的动漫", 7, None)
        session_id = result["session_id"]

        messages = session_service.get_messages(session_id)

        assert len(messages) == 2
        # 契约：每条消息四个字段
        for message in messages:
            assert set(message.keys()) == {
                "message_id",
                "role",
                "content",
                "created_at",
            }

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "请推荐一些好看的动漫"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == FAKE_ANSWER

    def test_assistant_message_id_matches_answer(self, chat_service, session_service):
        """历史里的 message_id 应与当轮返回的一致"""
        result = run_answer(chat_service, "请推荐一些好看的动漫", 7, None)
        messages = session_service.get_messages(result["session_id"])

        assert messages[1]["message_id"] == result["message_id"]

    def test_multi_turn_history_restored_from_checkpoint(
        self, chat_service, session_service
    ):
        """多轮对话由检查点自动恢复，无需手工拼装历史"""
        first = run_answer(chat_service, "请推荐一些好看的动漫", 7, None)
        session_id = first["session_id"]

        run_answer(chat_service, "那第二部呢动漫", 7, session_id)

        messages = session_service.get_messages(session_id)
        assert len(messages) == 4
        assert [m["role"] for m in messages] == [
            "user",
            "assistant",
            "user",
            "assistant",
        ]

    def test_history_has_no_tool_messages(self, chat_service, session_service):
        """工具调用的中间消息不应出现在对外历史中"""
        result = run_answer(chat_service, "我的追番历史怎么样", 7, None)
        messages = session_service.get_messages(result["session_id"])

        assert all(m["role"] in ("user", "assistant") for m in messages)

    def test_message_limit_returns_most_recent(self, chat_service, session_service):
        result = run_answer(chat_service, "请推荐一些好看的动漫", 7, None)
        session_id = result["session_id"]
        run_answer(chat_service, "那第二部呢动漫", 7, session_id)

        # 只取最近 2 条（应为第二轮的一问一答）
        messages = session_service.get_messages(session_id, limit=2)

        assert len(messages) == 2
        assert messages[0]["content"] == "那第二部呢动漫"

    def test_history_created_at_is_string(self, chat_service, session_service):
        result = run_answer(chat_service, "请推荐一些好看的动漫", 7, None)
        messages = session_service.get_messages(result["session_id"])

        assert isinstance(messages[0]["created_at"], str)
        # 'YYYY-MM-DD HH:MM:SS'
        assert len(messages[0]["created_at"]) == len(TIMESTAMP_FORMAT_HINT)

    def test_empty_history_for_new_session(self, session_service):
        session_id = session_service.create_session(user_id=7)["session_id"]

        # 尚未对话：检查点不存在，应返回空列表而非报错
        assert session_service.get_messages(session_id) == []

    def test_touch_called_on_answer(self, chat_service, store):
        run_answer(chat_service, "请推荐一些好看的动漫", 7, None)
        assert store.touch_count >= 1
