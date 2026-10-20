"""API 路由"""

from app.api import (
    routes_chat,
    routes_health,
    routes_knowledge,
    routes_news,
    routes_sessions,
)

__all__ = [
    "routes_chat",
    "routes_health",
    "routes_knowledge",
    "routes_news",
    "routes_sessions",
]
