"""
标识生成工具

保持与重构前完全一致的ID格式：
    会话: session_<16位十六进制>
    消息: msg_<16位十六进制>
"""

import uuid

from app.config import get_settings


def new_session_id() -> str:
    """生成会话ID（同时作为 LangGraph thread_id）"""
    settings = get_settings()
    return f"{settings.session_id_prefix}{uuid.uuid4().hex[: settings.id_length]}"


def new_message_id() -> str:
    """生成消息ID"""
    settings = get_settings()
    return f"{settings.message_id_prefix}{uuid.uuid4().hex[: settings.id_length]}"


def build_session_title(question: str) -> str:
    """
    依据首个问题生成会话标题

    与原实现一致：超过 20 个字符时截断并追加省略号。

    Args:
        question: 用户首个问题

    Returns:
        会话标题
    """
    settings = get_settings()
    limit = settings.title_max_length
    return question[:limit] + "..." if len(question) > limit else question


def ephemeral_thread_id() -> str:
    """
    生成瞬时线程ID

    未登录用户没有会话，但 LangGraph 绑定检查点后强制要求 thread_id，
    因此用该ID承载「用完即弃」的内存检查点，不会写入 PostgreSQL。
    """
    return f"ephemeral_{uuid.uuid4().hex}"


def new_run_id() -> str:
    """生成一次批处理运行的标识（资讯工作流日志用）"""
    return f"run_{uuid.uuid4().hex[:16]}"
