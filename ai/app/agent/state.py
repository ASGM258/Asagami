"""
LangGraph Agent 状态定义

消息统一使用 LangChain 消息类（HumanMessage / AIMessage / ToolMessage），
由 `add_messages` 归约器负责追加与合并，不再手拼 {"role": ..., "content": ...} 字典。
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """
    Agent 会话状态

    该状态会被 LangGraph 检查点完整持久化到 PostgreSQL：
    - messages：完整对话历史，检查点自动恢复，无需手工拼装
    - user_id：当前用户ID，每轮请求注入，供工具查询个人数据

    对外暴露的 message_id 存放在各条 AIMessage 的 additional_kwargs 中，
    随消息一起持久化，因此不需要额外的状态字段。
    """

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: int | None


def build_user_message(content: str) -> HumanMessage:
    """
    构造用户消息（HumanMessage）

    这里直接带上业务消息 id（additional_kwargs.message_id），与 AI 回答保持一致。
    否则读取历史时用户消息只能回退到 LangChain 内部 id（形如
    `bf0d58af-dd45-461c-...`），与助手消息的 `msg_xxx` 格式不统一。

    Args:
        content: 用户问题原文

    Returns:
        HumanMessage 实例
    """
    from app.utils.ids import new_message_id

    return HumanMessage(
        content=content,
        additional_kwargs={"message_id": new_message_id()},
    )


def make_state(content: str, user_id: int | None) -> dict[str, Any]:
    """
    构造一次调用的初始状态片段

    只传入新增的用户消息，历史消息由检查点自动恢复，
    user_id 由本轮请求覆盖。

    Args:
        content: 用户问题
        user_id: 用户ID

    Returns:
        可传给 agent.stream / agent.ainvoke 的状态字典
    """
    return {
        "messages": [build_user_message(content)],
        "user_id": user_id,
    }


def thread_config(session_id: str) -> dict[str, Any]:
    """
    构造 LangGraph 调用配置

    session_id 直接作为 thread_id，从而与对外接口的会话标识一一对应。

    Args:
        session_id: 会话ID

    Returns:
        RunnableConfig 字典
    """
    return {"configurable": {"thread_id": session_id}}
