"""
健康检查与首页接口

    GET /             API 首页（接口清单）
    GET /api/health   健康检查
"""

import time

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["系统"])


@router.get("/api/health", summary="健康检查")
async def health_check():
    """健康检查接口（字段与重构前保持一致）"""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.service_name,
        "timestamp": time.time(),
    }


@router.get("/", summary="API 首页")
async def index():
    """API 首页（接口清单与重构前保持一致）"""
    settings = get_settings()
    return {
        "message": "欢迎使用动漫AI问答系统",
        "version": settings.service_version,
        "endpoints": {
            "POST /api/anime-chat": "动漫AI问答接口（非流式）",
            "POST /api/anime-chat-stream": "动漫AI问答接口（流式输出，推荐）",
            "GET /api/health": "健康检查",
            "POST /api/session/create": "创建新会话",
            "GET /api/sessions": "获取用户会话列表",
            "GET /api/session/{session_id}/messages": "获取会话历史消息",
            "PUT /api/session/{session_id}/title": "更新会话标题",
            "DELETE /api/session/{session_id}": "删除会话",
        },
        "example_request": {
            "question": "我的追番历史怎么样？",
            "user_id": 1,
        },
    }
