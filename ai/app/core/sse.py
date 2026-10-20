"""
Server-Sent Events (SSE) 编码工具

事件负载结构与重构前完全一致，新增 `thinking` 类型用于展示思考/工具调用状态：

    data: {"success": true, "chunk": "文本", "type": "content"}\\n\\n
    data: {"success": true, "chunk": "", "type": "thinking", "stage": "thinking"}\\n\\n
    data: {"success": true, "chunk": "", "type": "thinking", "stage": "reasoning"}\\n\\n
    data: {"success": true, "chunk": "", "type": "thinking", "stage": "tool", "tool": "get_anime_info"}\\n\\n
    data: {"success": true, "chunk": "", "type": "end", "session_id": ..., "message_id": ...}\\n\\n
    data: {"success": false, "error": "...", "chunk": "...", "type": "error"}\\n\\n

`retract` 类型仍保留（前端已实现容错），但当前策略不再发出：
中间过渡语现在直接展示给用户，无需撤回。
"""

import json
from typing import Any, AsyncIterator, Iterator

# SSE 事件类型
TYPE_CONTENT = "content"
TYPE_END = "end"
TYPE_ERROR = "error"
# 思考/工具调用提示（不携带正文，仅供前端显示转圈）
TYPE_THINKING = "thinking"
# 保留兼容：撤回已下发的正文。当前不再发出（见模块说明）
TYPE_RETRACT = "retract"

# thinking 事件的阶段
STAGE_THINKING = "thinking"
STAGE_REASONING = "reasoning"
STAGE_TOOL = "tool"

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def encode_event(payload: dict) -> str:
    """
    将字典编码为一个 SSE 事件

    Args:
        payload: 事件负载

    Returns:
        SSE 文本片段
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def content_event(chunk: str) -> str:
    """内容片段事件"""
    return encode_event({"success": True, "chunk": chunk, "type": TYPE_CONTENT})


def thinking_event(stage: str = STAGE_THINKING, tool: str | None = None) -> str:
    """
    「思考中 / reasoning 中 / 正在调用工具」事件

    这是本服务**新增**的事件类型，只用于前端展示转圈提示，不携带回答正文。
    前端需保证对未知 type 做容错（旧版前端会忽略它，不影响正文渲染）。

    Args:
        stage: thinking（等待模型续写）| reasoning（模型在产出思维链）| tool（正在调用工具）
        tool: 工具名（stage=tool 时提供）
    """
    payload: dict[str, Any] = {
        "success": True,
        "chunk": "",
        "type": TYPE_THINKING,
        "stage": stage,
    }
    if tool:
        payload["tool"] = tool
    return encode_event(payload)


def retract_event() -> str:
    """
    撤回事件：告知前端清空当前气泡里已显示的内容

    ⚠️ 当前策略已不再发出该事件 —— 中间过渡语现在直接展示给用户，
    不需要撤回。函数与事件类型保留，供前端/旧版本兼容与将来可能的回滚。

    旧版前端会忽略未知 type，因此即使发出也不会破坏兼容性。
    """
    return encode_event(
        {"success": True, "chunk": "", "type": TYPE_RETRACT}
    )


def end_event(session_id: str | None, message_id: str | None) -> str:
    """结束事件（携带 session_id 与 message_id）"""
    return encode_event(
        {
            "success": True,
            "chunk": "",
            "type": TYPE_END,
            "session_id": session_id,
            "message_id": message_id,
        }
    )


def error_event(message: str, chunk: str = "", is_anime_related: bool | None = None) -> str:
    """
    错误事件

    Args:
        message: 错误消息
        chunk: 需要展示给用户的文本
        is_anime_related: 为 False 时前端不会抛出异常（非动漫问题场景）
    """
    payload: dict[str, Any] = {
        "success": False,
        "error": message,
        "chunk": chunk,
        "type": TYPE_ERROR,
    }
    if is_anime_related is not None:
        payload["is_anime_related"] = is_anime_related
    return encode_event(payload)


def sse_response_kwargs() -> dict:
    """构造 StreamingResponse 所需的媒体类型与响应头"""
    return {
        "media_type": "text/event-stream",
        "headers": dict(SSE_HEADERS),
    }


# 类型别名：流式生成器可产出同步或异步片段
SSEStream = Iterator[str] | AsyncIterator[str]
