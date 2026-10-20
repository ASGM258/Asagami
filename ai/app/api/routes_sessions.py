"""
会话管理接口

    POST   /api/session/create              创建新会话
    GET    /api/sessions                    获取用户会话列表
    GET    /api/session/{session_id}/messages  获取会话历史消息
    PUT    /api/session/{session_id}/title     更新会话标题
    DELETE /api/session/{session_id}           删除会话（支持硬删除）

响应体字段与重构前的 Flask 版本完全一致：
- 会话列表 data.sessions[].created_at / updated_at 为 'YYYY-MM-DD HH:MM:SS' 字符串
- 消息列表 data.messages[].role 取值 user / assistant
"""

import logging

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from app.core.errors import BusinessError, MissingParameterError, SessionNotFoundError
from app.core.responses import success_response
from app.dependencies import get_session_service
from app.schemas import (
    MessageListData,
    SessionCreateRequest,
    SessionCreatedData,
    SessionIdData,
    SessionListData,
    TitleUpdateRequest,
)
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["会话"])

# 读取检查点时单次拉取的上限，接口层再按 limit 截取最近若干条
MESSAGE_FETCH_LIMIT = 1000


@router.post("/session/create", summary="创建新会话")
async def create_session(
    payload: SessionCreateRequest,
    session_service: SessionService = Depends(get_session_service),
):
    """
    创建新会话

    Request Body:
        {"user_id": 1, "title": "会话标题"}

    Response:
        {"success": true, "data": {"session_id": "...", "title": "..."}}
    """
    session = await run_in_threadpool(
        session_service.create_session, payload.user_id, payload.title
    )

    if not session:
        raise BusinessError(
            message="创建会话失败",
            error_code="SESSION_CREATE_FAILED",
            http_status=500,
        )

    data = SessionCreatedData(**session)
    return success_response(data=data.model_dump(), message="会话创建成功")


@router.get("/sessions", summary="获取用户会话列表")
async def get_sessions(
    user_id: int | None = Query(None, description="用户ID"),
    limit: int = Query(50, description="返回数量限制"),
    session_service: SessionService = Depends(get_session_service),
):
    """
    获取用户的会话列表

    Query Parameters:
        user_id: 用户ID（必填）
        limit: 返回数量限制（默认50）
    """
    if user_id is None:
        raise MissingParameterError("user_id")

    sessions = await run_in_threadpool(session_service.list_sessions, user_id, limit)

    data = SessionListData(sessions=sessions, count=len(sessions))
    return success_response(data=data.model_dump(), message="获取会话列表成功")


@router.get("/session/{session_id}/messages", summary="获取会话历史消息")
async def get_messages(
    session_id: str,
    limit: int = Query(100, description="返回消息数量限制"),
    session_service: SessionService = Depends(get_session_service),
):
    """
    获取会话的历史消息

    消息来源为 LangGraph 检查点，仅返回用户与 AI 的对话消息。
    """
    # 会话不存在或被软删除时返回 404
    session = await run_in_threadpool(session_service.require_session, session_id)
    if not session:
        raise SessionNotFoundError()

    # 消息读取走异步接口：检查点为 AsyncPostgresSaver，同步接口未实现
    messages = await session_service.get_messages_async(session_id, MESSAGE_FETCH_LIMIT)
    # 保留最近 limit 条
    if limit and limit > 0:
        messages = messages[-limit:]

    data = MessageListData(
        session_id=session_id, messages=messages, count=len(messages)
    )
    return success_response(data=data.model_dump(), message="获取消息成功")


@router.put("/session/{session_id}/title", summary="更新会话标题")
async def update_title(
    session_id: str,
    payload: TitleUpdateRequest,
    session_service: SessionService = Depends(get_session_service),
):
    """
    更新会话标题

    Request Body:
        {"title": "新标题"}
    """
    title = (payload.title or "").strip()
    if not title:
        raise BusinessError(
            message="标题不能为空",
            error_code="EMPTY_TITLE",
            http_status=400,
        )

    await run_in_threadpool(session_service.require_session, session_id)

    updated = await run_in_threadpool(
        session_service.update_title, session_id, title
    )
    if not updated:
        raise BusinessError(
            message="更新失败，会话可能不存在",
            error_code="SESSION_UPDATE_FAILED",
            http_status=404,
        )

    data = SessionIdData(session_id=session_id)
    return success_response(data=data.model_dump(), message="标题更新成功")


@router.delete("/session/{session_id}", summary="删除会话")
async def delete_session(
    session_id: str,
    hard: bool = Query(False, description="是否彻底删除（含检查点消息）"),
    session_service: SessionService = Depends(get_session_service),
):
    """
    删除会话

    Query Parameters:
        hard: true 为彻底删除（连检查点消息一并清理），否则为软删除
    """
    await run_in_threadpool(session_service.require_session, session_id)

    success = await run_in_threadpool(
        session_service.delete_session, session_id, hard
    )
    if not success:
        raise BusinessError(
            message="删除失败",
            error_code="SESSION_DELETE_FAILED",
            http_status=500,
        )

    data = SessionIdData(session_id=session_id)
    return success_response(data=data.model_dump(), message="会话已删除")
