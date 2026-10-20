"""
会话服务

职责边界：
- 会话元数据（标题、归属用户、软删除）→ PostgreSQL `chat_sessions` 表
- 会话消息（对话状态）→ LangGraph 检查点，按 thread_id == session_id 存取

因此「会话是否存在」一律以元数据表为准，而不是以检查点是否存在为准 ——
这样空会话（刚创建、尚未对话）与软删除的会话语义都与重构前一致。
"""

import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agent.graph import SUMMARIZATION_SOURCE, AnimeAgentFactory
from app.agent.state import thread_config
from app.config import Settings
from app.core.errors import SessionCreateFailedError, SessionNotFoundError
from app.db.postgres import PostgresStore, format_timestamp
from app.services.stream_filter import message_answer_text
from app.utils.ids import build_session_title, new_session_id

logger = logging.getLogger(__name__)

# 角色映射：LangChain 消息类 → 对外 role 字段
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


class SessionService:
    """会话与消息的读写服务"""

    def __init__(
        self,
        store: PostgresStore,
        agent_factory: AnimeAgentFactory,
        settings: Settings,
    ) -> None:
        self._store = store
        self._agent_factory = agent_factory
        self._settings = settings

    # ==================== 会话元数据 ====================

    def create_session(self, user_id: int, title: str | None = None) -> dict:
        """
        创建新会话

        Args:
            user_id: 用户ID
            title: 会话标题，缺省为「新会话」

        Returns:
            {session_id, title}
        """
        session_id = new_session_id()
        session_title = title or self._settings.default_session_title

        created = self._store.create_session(session_id, user_id, session_title)
        if not created:
            raise SessionCreateFailedError()

        logger.info("会话已创建: session_id=%s, user_id=%s", session_id, user_id)
        return {"session_id": session_id, "title": session_title}

    def list_sessions(self, user_id: int, limit: int = 50) -> list[dict]:
        """
        获取用户的会话列表

        Returns:
            [{session_id, title, created_at, updated_at}, ...]
        """
        return self._store.get_user_sessions(user_id, limit)

    def get_session(self, session_id: str) -> dict | None:
        """获取未删除会话的元数据，不存在返回 None"""
        return self._store.get_session_info(session_id)

    def require_session(self, session_id: str) -> dict:
        """
        获取会话元数据，不存在则抛 404 业务异常

        Raises:
            SessionNotFoundError: 会话不存在或已被删除
        """
        session = self._store.get_session_info(session_id)
        if not session:
            raise SessionNotFoundError()
        return session

    def update_title(self, session_id: str, title: str) -> bool:
        """
        更新会话标题

        Returns:
            是否更新成功（会话不存在时为 False）
        """
        return self._store.update_title(session_id, title)

    def delete_session(self, session_id: str, hard: bool = False) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID
            hard: True 为彻底删除（含检查点消息）

        Returns:
            是否删除成功
        """
        if hard:
            return self._store.hard_delete_session(session_id)
        return self._store.soft_delete_session(session_id)

    # ==================== 消息（来自 LangGraph 检查点） ====================

    def get_messages(self, session_id: str, limit: int = 100) -> list[dict]:
        """
        从检查点读取会话的消息历史（同步接口）

        ⚠️ 仅供离线/测试使用。生产链路走 `get_messages_async` ——
        检查点已切换为 AsyncPostgresSaver，其同步接口未实现。

        Args:
            session_id: 会话ID
            limit: 返回的最大消息条数（保留最近 limit 条）

        Returns:
            按时间正序排列的消息列表
        """
        agent = self._agent_factory.agent
        snapshot = agent.get_state(thread_config(session_id))
        return self._format_snapshot(snapshot, limit)

    async def get_messages_async(self, session_id: str, limit: int = 100) -> list[dict]:
        """
        从检查点读取会话的消息历史（异步）

        FastAPI 路由必须调用本方法：AsyncPostgresSaver 未实现同步接口，
        而同步 PostgresSaver 未实现异步接口，两者不可混用。

        Args:
            session_id: 会话ID
            limit: 返回的最大消息条数（保留最近 limit 条）

        Returns:
            按时间正序排列的消息列表
        """
        agent = self._agent_factory.agent
        snapshot = await agent.aget_state(thread_config(session_id))
        return self._format_snapshot(snapshot, limit)

    def _format_snapshot(self, snapshot, limit: int) -> list[dict]:
        """把 LangGraph 状态快照映射为对外的消息列表"""
        messages: list[BaseMessage] = []
        if snapshot and snapshot.values:
            messages = list(snapshot.values.get("messages", []))

        # 检查点时间戳为 ISO 字符串，对外统一为 'YYYY-MM-DD HH:MM:SS'
        created_at = format_timestamp(snapshot.created_at) if snapshot else None

        formatted = [
            item
            for item in (self._format_message(message, created_at) for message in messages)
            if item is not None
        ]

        formatted = self._merge_consecutive_assistant(formatted)

        # 保留最近 limit 条
        if limit and limit > 0:
            formatted = formatted[-limit:]

        return formatted

    @staticmethod
    def _merge_consecutive_assistant(items: list[dict]) -> list[dict]:
        """
        合并连续的 assistant 消息

        一轮对话里模型可能说「我来查询一下你的记录。」（这条带 tool_calls）
        → 调工具 → 再说最终答案，于是检查点里有多条带正文的 AIMessage。

        流式链路把它们逐字累加进**同一个气泡**，历史接口若原样返回就会变成
        好几个气泡、内容还对不上。因此这里按同样的规则把它们拼成一条。

        ToolMessage 已在 _format_message 被跳过，所以工具前后的两条 AI 消息
        在这里正好相邻。不同轮次之间隔着 HumanMessage，不会被误合并。
        """
        merged: list[dict] = []

        for item in items:
            previous = merged[-1] if merged else None
            if (
                previous is not None
                and previous["role"] == ROLE_ASSISTANT
                and item["role"] == ROLE_ASSISTANT
            ):
                previous["content"] += item["content"]
                # 合并后的气泡以最后一条消息的 id 为准（message_id 由此产生）
                previous["message_id"] = item["message_id"] or previous["message_id"]
                continue
            merged.append(dict(item))

        return merged

    @staticmethod
    def _format_message(message: BaseMessage, created_at: str | None) -> dict | None:
        """
        将 LangChain 消息映射为接口契约要求的字典

        非 HumanMessage / AIMessage（如 ToolMessage、SystemMessage）返回 None 以跳过。

        上下文压缩生成的摘要以 SystemMessage 入状态，因此天然不出现；
        这里再加一道按 `lc_source` 标记的判断，防止 LangChain 将来把它改回
        HumanMessage 时，前端又冒出一条用户没发过的"发言"。
        """
        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
        if isinstance(additional_kwargs, dict) and (
            additional_kwargs.get("lc_source") == SUMMARIZATION_SOURCE
        ):
            return None

        if isinstance(message, HumanMessage):
            role = ROLE_USER
            content = message.content if isinstance(message.content, str) else ""
        elif isinstance(message, AIMessage):
            role = ROLE_ASSISTANT
            # 只取正文，reasoning 永远不出现在历史里
            content = message_answer_text(message)
        else:
            return None

        # 跳过工具调用产生的空内容消息
        if not content.strip():
            return None

        message_id = additional_kwargs.get("message_id") or message.id or ""

        return {
            "message_id": message_id,
            "role": role,
            "content": content,
            "created_at": created_at,
        }

    # ==================== 工具方法 ====================

    def build_title_from_question(self, question: str) -> str:
        """依据首个问题生成会话标题"""
        return build_session_title(question)

    def touch(self, session_id: str) -> None:
        """刷新会话活跃时间（失败不阻断主流程）"""
        self._store.touch_session(session_id)
