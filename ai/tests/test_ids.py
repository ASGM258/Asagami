"""ID 生成工具测试：格式必须与重构前完全一致"""

from app.utils.ids import build_session_title, new_message_id, new_session_id


def test_session_id_format():
    session_id = new_session_id()
    assert session_id.startswith("session_")
    assert len(session_id) == len("session_") + 16


def test_message_id_format():
    message_id = new_message_id()
    assert message_id.startswith("msg_")
    assert len(message_id) == len("msg_") + 16


def test_ids_are_unique():
    assert len({new_session_id() for _ in range(50)}) == 50


def test_title_short_question_unchanged():
    assert build_session_title("我的追番历史") == "我的追番历史"


def test_title_long_question_truncated():
    question = "这是一句非常长的动漫相关问题需要被截断处理掉多余部分"
    title = build_session_title(question)
    assert title == question[:20] + "..."
    assert len(title) == 23
