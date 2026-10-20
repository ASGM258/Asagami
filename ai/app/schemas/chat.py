"""
请求 / 响应数据模型

字段严格对齐重构前的接口契约，因此响应模型采用「只读输出」而非严格校验，
实际响应体由 app.core.responses 统一构造，此处的模型主要用于
OpenAPI 文档、请求体校验与类型提示。
"""

from typing import Any

from pydantic import BaseModel, Field


# ==================== 通用响应 ====================


class ErrorDetail(BaseModel):
    """错误详情"""

    message: str
    code: str
    timestamp: float
    data: Any | None = None


class SuccessEnvelope(BaseModel):
    """成功响应外壳"""

    success: bool = True
    message: str = "操作成功"
    timestamp: float
    data: Any | None = None


class ErrorEnvelope(BaseModel):
    """失败响应外壳"""

    success: bool = False
    error: ErrorDetail


# ==================== 问答 ====================


class ChatRequest(BaseModel):
    """问答请求体"""

    question: str = Field(..., description="用户问题")
    user_id: int | None = Field(None, description="用户ID，用于查询个人数据")
    session_id: str | None = Field(None, description="会话ID，继续已有对话时传入")


class ChatAnswerData(BaseModel):
    """非流式问答的 data 部分"""

    answer: str
    is_anime_related: bool
    user_id: int | None = None
    session_id: str | None = None
    message_id: str | None = None


# ==================== 会话 ====================


class SessionCreateRequest(BaseModel):
    """创建会话请求体"""

    user_id: int = Field(..., description="用户ID")
    title: str | None = Field(None, description="会话标题")


class SessionCreatedData(BaseModel):
    """创建会话的 data 部分"""

    session_id: str
    title: str


class SessionItem(BaseModel):
    """会话列表条目"""

    session_id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None


class SessionListData(BaseModel):
    """会话列表的 data 部分"""

    sessions: list[SessionItem]
    count: int


class MessageItem(BaseModel):
    """消息条目"""

    message_id: str
    role: str
    content: str
    created_at: str | None = None


class MessageListData(BaseModel):
    """消息列表的 data 部分"""

    session_id: str
    messages: list[MessageItem]
    count: int


class SessionIdData(BaseModel):
    """仅返回会话ID的 data 部分"""

    session_id: str


class TitleUpdateRequest(BaseModel):
    """更新标题请求体"""

    title: str = Field(..., description="新标题")


# ==================== 健康检查 ====================


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    service: str
    timestamp: float
