"""
问答接口

    POST /api/anime-chat          非流式问答
    POST /api/anime-chat-stream   流式问答（SSE）

响应体字段与重构前的 Flask 版本完全一致。
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core import sse
from app.core.errors import BusinessError
from app.core.responses import success_response
from app.dependencies import get_chat_service
from app.schemas import ChatAnswerData, ChatRequest, SuccessEnvelope
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["问答"])


@router.post(
    "/anime-chat",
    response_model=SuccessEnvelope,
    summary="动漫AI问答（非流式）",
)
async def anime_chat(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    动漫AI问答接口（非流式）

    Request Body:
        {"question": "用户的问题", "user_id": 123, "session_id": "session_xxx"}

    Response:
        {"success": true, "message": "问答成功", "timestamp": ..., "data": {...}}
    """
    question = (payload.question or "").strip()
    if not question:
        raise BusinessError(
            message="问题不能为空",
            error_code="EMPTY_QUESTION",
            http_status=400,
        )

    result = await chat_service.answer(question, payload.user_id, payload.session_id)

    data = ChatAnswerData(
        answer=result["answer"],
        is_anime_related=result["is_anime_related"],
        user_id=result.get("user_id"),
        session_id=result.get("session_id"),
        message_id=result.get("message_id"),
    )

    # 非动漫相关问题保持与旧版一致的固定 message
    message = "问答成功" if result["is_anime_related"] else "非动漫相关问题"
    return success_response(data=data.model_dump(), message=message)


@router.post(
    "/anime-chat-stream",
    summary="动漫AI问答（SSE 流式）",
    response_class=StreamingResponse,
)
async def anime_chat_stream(
    payload: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    动漫AI问答接口（流式输出）

    使用 Server-Sent Events (SSE) 实现流式响应，事件格式：

        event: message
        data: {"success": true, "chunk": "文本片段", "type": "content"}

        event: end
        data: {"success": true, "chunk": "", "type": "end",
               "session_id": "会话ID", "message_id": "消息ID"}
    """
    question = (payload.question or "").strip()

    # 参数错误在流开始前以正规错误响应返回，与旧版语义一致
    if not question:
        raise BusinessError(
            message="问题不能为空",
            error_code="EMPTY_QUESTION",
            http_status=400,
        )

    stream = chat_service.stream_answer(
        question, payload.user_id, payload.session_id
    )

    return StreamingResponse(stream, **sse.sse_response_kwargs())
