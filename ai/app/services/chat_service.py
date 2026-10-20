"""
聊天服务

编排一次问答的完整流程：
    相关性过滤 → 选择/创建会话 → 调用 Agent（检查点自动持久化）→ 产出响应

消息持久化完全交给 LangGraph 检查点：一轮结束后整份状态写入 PostgreSQL，
下一轮由 checkpointer 自动恢复历史，因此这里不再有 save_message 之类的写库逻辑。
"""

import logging
from typing import AsyncIterator

from langchain_core.messages import AIMessage

from app.agent.filter import is_anime_related_question
from app.agent.graph import AnimeAgentFactory
from app.agent.state import make_state, thread_config
from app.core import sse
from app.core.errors import SessionNotFoundError
from app.db.postgres import PostgresStore
from app.services.session_service import SessionService
from app.services.stream_filter import (
    AnswerStreamFilter,
    StreamEvent,
    final_answer_from_messages,
    is_internal_chunk,
    last_turn_messages,
    message_answer_text,
)
from app.utils.ids import ephemeral_thread_id

logger = logging.getLogger(__name__)

# 非动漫相关问题的固定回复（与重构前一致）
NON_ANIME_REPLY = (
    "抱歉，我只能回答与动漫相关的问题哦！"
    "您可以问我关于追番历史、动漫推荐、观看统计等方面的问题。🎌"
)
# 异常时的兜底回复
FALLBACK_REPLY = "抱歉，处理您的问题时出现了错误，请稍后重试。"


class ChatService:
    """问答编排服务"""

    def __init__(
        self,
        store: PostgresStore,
        agent_factory: AnimeAgentFactory,
        session_service: SessionService,
    ) -> None:
        self._store = store
        self._agent_factory = agent_factory
        self._sessions = session_service

    # ==================== 会话准备 ====================

    def _resolve_session(
        self, question: str, user_id: int | None, session_id: str | None
    ) -> tuple[str | None, int | None]:
        """
        确定本轮对话所属的会话与用户

        规则与重构前一致：
        - 未提供 session_id 且提供了 user_id → 自动建会话，标题取问题前 20 字
        - 提供了 session_id → 校验存在性，用户以元数据表记录为准
        - 未提供 user_id → 无会话，纯问答不落库

        Returns:
            (session_id, user_id)
        """
        if session_id:
            session = self._sessions.require_session(session_id)
            return session_id, session.get("user_id", user_id)

        if user_id:
            session = self._sessions.create_session(
                user_id=user_id,
                title=self._sessions.build_title_from_question(question),
            )
            return session["session_id"], user_id

        return None, user_id

    # ==================== 非流式 ====================

    async def answer(
        self, question: str, user_id: int | None, session_id: str | None
    ) -> dict:
        """
        非流式问答

        Args:
            question: 用户问题
            user_id: 用户ID
            session_id: 会话ID

        Returns:
            {"answer": str, "is_anime_related": bool, "user_id": int|None,
             "session_id": str|None, "message_id": str|None}
        """
        # 前置过滤：非动漫相关问题直接返回固定话术
        if not is_anime_related_question(question):
            return {
                "answer": NON_ANIME_REPLY,
                "is_anime_related": False,
                "user_id": user_id,
                "session_id": session_id,
                "message_id": None,
            }

        session_id, effective_user_id = self._resolve_session(
            question, user_id, session_id
        )

        # 有会话 → 用带 PostgreSQL 检查点的 Agent；无会话 → 使用瞬时内存检查点
        if session_id:
            agent = self._agent_factory.agent
            config = thread_config(session_id)
        else:
            agent = self._agent_factory.ephemeral_agent
            config = thread_config(ephemeral_thread_id())

        state = make_state(question, effective_user_id)
        result = await agent.ainvoke(state, config)

        # ⚠️ 带检查点时 ainvoke 返回的是整个会话的 messages，
        # 必须先用 HumanMessage 切出本轮，否则会把历史各轮的答案拼进来
        messages = last_turn_messages(result.get("messages", []))
        answer = self._last_ai_content(messages)

        if session_id:
            self._sessions.touch(session_id)

        return {
            "answer": answer,
            "is_anime_related": True,
            "user_id": effective_user_id,
            "session_id": session_id,
            "message_id": self._last_ai_message_id(messages),
        }

    # ==================== 流式 ====================

    async def stream_answer(
        self, question: str, user_id: int | None, session_id: str | None
    ) -> AsyncIterator[str]:
        """
        流式问答，产出已编码的 SSE 事件片段

        事件序列：若干 content 事件 + 一个 end 事件；
        异常与非动漫问题走 error 事件（HTTP 状态仍为 200，与重构前一致）。

        Yields:
            SSE 文本片段
        """
        try:
            # 前置过滤：非动漫相关问题直接给固定话术
            if not is_anime_related_question(question):
                yield sse.error_event(
                    message="非动漫相关问题",
                    chunk=NON_ANIME_REPLY,
                    is_anime_related=False,
                )
                return

            session_id, effective_user_id = self._resolve_session(
                question, user_id, session_id
            )

            if session_id:
                agent = self._agent_factory.agent
                config = thread_config(session_id)
            else:
                # 无会话：使用瞬时线程，既满足 LangGraph 对 thread_id 的要求，
                # 又不对外暴露任何持久化会话
                agent = self._agent_factory.ephemeral_agent
                config = thread_config(ephemeral_thread_id())

            state = make_state(question, effective_user_id)

            # 逐 token 流式输出（stream_mode="messages"）
            # ⚠️ 该模式下会流出**所有**节点的消息：
            #   - ToolMessage（工具返回的内部数据）→ 必须过滤
            #   - 带 tool_calls 的 AIMessage 正文（"我来查询一下"之类的过渡语）
            #     → 现在按产品要求**照常下发**，不做撤回
            #   - reasoning（思维链）→ 无论来自哪个字段，都不进正文
            stream = agent.astream(state, config, stream_mode="messages")
            answer_filter = AnswerStreamFilter()

            async for chunk, metadata in stream:
                # 跳过内部维护调用：上下文摘要模型的输出是给模型看的内部笔记，
                # 一旦流给前端，用户会看到一段莫名其妙的"总结"（实测会漏）
                if is_internal_chunk(metadata):
                    continue

                step = (metadata or {}).get("langgraph_step")
                for event in answer_filter.feed_with_step(chunk, step):
                    frame = self._event_to_frame(event)
                    if frame:
                        yield frame

            # 从当前状态读取最终消息ID（由 MessageIdMiddleware 写入）
            message_id = await self._persisted_message_id(agent, config)

            if session_id:
                self._sessions.touch(session_id)

            yield sse.end_event(session_id, message_id)

        except SessionNotFoundError as exc:
            # 会话不存在：以业务错误码通知前端
            logger.warning("流式问答会话不存在: %s", exc.message)
            yield sse.error_event(message=exc.message, chunk=exc.message)
        except Exception as exc:  # noqa: BLE001 - 统一降级为 error 事件
            logger.exception("流式问答失败: %s", exc)
            yield sse.error_event(
                message=f"服务器内部错误: {exc}",
                chunk=FALLBACK_REPLY,
            )

    # ==================== 内部工具 ====================

    @staticmethod
    def _event_to_frame(event: StreamEvent) -> str | None:
        """
        把过滤器的逻辑事件编码为 SSE 帧

        - content  → 正文片段（含过渡语）
        - thinking → 提示（stage=thinking / reasoning，前端显示转圈）
        - tool     → 正在调用某工具（前端显示"正在查询…"）
        """
        if event.kind == "content":
            return sse.content_event(event.text)
        if event.kind == "thinking":
            return sse.thinking_event(stage=event.stage)
        if event.kind == "tool":
            return sse.thinking_event(stage=sse.STAGE_TOOL, tool=event.tool)
        return None

    async def _persisted_message_id(self, agent, config) -> str | None:
        """
        读取最终状态中最后一条 AI 消息的 message_id

        该 id 由 MessageIdMiddleware 在每轮结束时写入并随消息持久化，
        因此与历史接口返回的 message_id 完全一致。

        Args:
            agent: 本轮实际使用的 Agent（持久化版或瞬时版）
            config: LangGraph 调用配置（含 thread_id）
        """
        snapshot = await agent.aget_state(config)
        if not snapshot or not snapshot.values:
            return None

        # 同样只看本轮（最后一条 HumanMessage 之后），避免最终答案为空时
        # 回溯到上一轮的 AI 消息上去
        return self._last_ai_message_id(
            last_turn_messages(snapshot.values.get("messages", []))
        )

    @staticmethod
    def _last_ai_content(messages) -> str:
        """
        取展示给用户的完整正文

        与流式链路共用同一规则（final_answer_from_messages）：
        按顺序拼接所有 AIMessage 的正文（过渡语 + 最终答案），
        跳过 ToolMessage 与 reasoning，因此刷新会话看到的内容与流式时一致。

        ⚠️ 入参必须是**本轮**的消息切片（先过 `last_turn_messages()`），
        否则会把历史各轮的答案一起拼进来。
        """
        answer = final_answer_from_messages(messages)
        return answer if answer.strip() else FALLBACK_REPLY

    @staticmethod
    def _last_ai_message_id(messages) -> str | None:
        """
        取最终回答对应的业务消息ID

        取最后一条**有正文**的 AI 消息：过渡语与最终答案在展示层被拼成一个
        气泡，历史接口合并后用的也是这个 id，两边必须一致。

        ⚠️ 同样要求传入本轮切片，否则最终答案为空的轮次会回溯到上一轮的 id。
        """
        for message in reversed(list(messages or [])):
            if not isinstance(message, AIMessage):
                continue
            if message_answer_text(message).strip():
                return message.additional_kwargs.get("message_id") or message.id
        return None
