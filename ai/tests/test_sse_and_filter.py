"""SSE 编码与相关性过滤的单元测试"""

import json

import pytest

from app.agent.filter import is_anime_related_question
from app.core import sse


def parse_event(frame: str) -> dict:
    """把单个 SSE 片段解析回字典"""
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    return json.loads(frame[len("data: "): -2])


class TestSSEEncoding:
    """SSE 事件负载结构必须与前端解析逻辑一致"""

    def test_content_event(self):
        payload = parse_event(sse.content_event("你好"))
        assert payload == {"success": True, "chunk": "你好", "type": "content"}

    def test_content_event_keeps_unicode(self):
        # ensure_ascii=False：中文不被转义
        assert "你好" in sse.content_event("你好")

    def test_end_event(self):
        payload = parse_event(sse.end_event("session_abc", "msg_def"))
        assert payload["type"] == "end"
        assert payload["success"] is True
        assert payload["chunk"] == ""
        assert payload["session_id"] == "session_abc"
        assert payload["message_id"] == "msg_def"

    def test_end_event_allows_none_ids(self):
        payload = parse_event(sse.end_event(None, None))
        assert payload["session_id"] is None
        assert payload["message_id"] is None

    def test_error_event_without_flag(self):
        payload = parse_event(sse.error_event("出错了", "兜底文案"))
        assert payload["type"] == "error"
        assert payload["success"] is False
        assert payload["error"] == "出错了"
        assert payload["chunk"] == "兜底文案"
        # 未传入时不输出该字段
        assert "is_anime_related" not in payload

    def test_error_event_non_anime_flag(self):
        # 前端依赖 is_anime_related is False 来避免抛异常
        payload = parse_event(sse.error_event("非动漫相关问题", "提示", False))
        assert payload["is_anime_related"] is False

    def test_response_kwargs(self):
        kwargs = sse.sse_response_kwargs()
        assert kwargs["media_type"] == "text/event-stream"
        assert kwargs["headers"]["Cache-Control"] == "no-cache"


class TestAnimeFilter:
    """相关性过滤行为需与重构前一致"""

    @pytest.mark.parametrize(
        "question",
        [
            "请推荐一些好看的动漫",
            "我的追番历史怎么样",
            "这部番的评分高吗",
            "anime recommendation",
            "你好",
            "我看了3部",
            "短",
        ],
    )
    def test_related_questions_pass(self, question):
        assert is_anime_related_question(question) is True

    def test_unrelated_long_question_rejected(self):
        assert is_anime_related_question("请帮我写一段快速排序的代码实现") is False

    def test_empty_question_rejected(self):
        assert is_anime_related_question("") is False
