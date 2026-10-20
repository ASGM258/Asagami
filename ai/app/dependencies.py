"""
FastAPI 依赖注入

服务实例在应用启动时构建并挂载到 app.state，这里只做取用，
避免在路由内部直接依赖进程级单例。

注意：数据库不可用时（例如 PostgreSQL 未启动），lifespan 会把依赖数据库的
服务置为 None。此时必须在此处显式抛出带 503 的业务异常 —— 若直接返回 None，
调用方会在 run_in_threadpool 内部抛出 AttributeError，绕过统一异常处理器，
最终表现为 500 与未捕获的 ASGI 异常。
"""

from typing import Any

from fastapi import Request

from app.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError
from app.news.service import NewsService
from app.services.chat_service import ChatService
from app.services.session_service import SessionService


def _require(service: Any, name: str, hint: str) -> Any:
    """
    断言服务已就绪，否则抛出 503

    Args:
        service: app.state 上取到的服务实例
        name: 服务名称（用于提示）
        hint: 排查建议

    Returns:
        就绪的服务实例
    """
    if service is None:
        raise ServiceUnavailableError(f"{name}尚未就绪：{hint}")
    return service


def get_app_settings() -> Settings:
    """获取配置"""
    return get_settings()


def get_session_service(request: Request) -> SessionService:
    """
    获取会话服务实例

    依赖 PostgreSQL（会话元数据 + LangGraph 检查点）。
    """
    return _require(
        getattr(request.app.state, "session_service", None),
        "会话服务",
        "请检查 AI_DATABASE_URL 配置并确认 PostgreSQL 已启动且库已创建",
    )


def get_chat_service(request: Request) -> ChatService:
    """
    获取聊天服务实例

    同样依赖 PostgreSQL 检查点。
    """
    return _require(
        getattr(request.app.state, "chat_service", None),
        "问答服务",
        "请检查 AI_DATABASE_URL 配置并确认 PostgreSQL 已启动且库已创建",
    )


def get_news_service(request: Request) -> NewsService:
    """
    获取资讯服务实例

    依赖 MySQL（资讯表）。
    """
    return _require(
        getattr(request.app.state, "news_service", None),
        "资讯服务",
        "请检查 MySQL 配置并确认资讯表已创建",
    )


def get_knowledge_service(request: Request):
    """
    获取知识库摄取服务实例（RAG）

    依赖本地 Chroma 向量库与 embedding 提供方。
    """
    return _require(
        getattr(request.app.state, "knowledge_service", None),
        "知识库服务",
        "请检查 CHROMA_PERSIST_DIR 是否可写、embedding 配置是否正确",
    )
