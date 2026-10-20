"""
LangGraph Agent 装配

使用 langchain.agents.create_agent 构建 ReAct 风格 Agent，
并挂载 PostgreSQL 检查点，使每个 session_id（thread_id）拥有独立的持久化对话记忆。
"""

import logging

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.knowledge import KnowledgeHintMiddleware
from app.agent.prompts import CONTEXT_SUMMARY_PROMPT, SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools import ANIME_TOOLS
from app.config import Settings
from app.mcp.tools import BILIBILI_TOOLS
from app.rag.tools import KNOWLEDGE_TOOLS
from app.utils.ids import new_message_id

logger = logging.getLogger(__name__)

#: Agent 可用的全部工具 = 动漫数据 + 知识库检索 + B站视频推荐（MCP）
AGENT_TOOLS = [*ANIME_TOOLS, *KNOWLEDGE_TOOLS, *BILIBILI_TOOLS]

#: 摘要消息的标记（LangChain 自带该 additional_kwargs 键，据此可在展示层识别）
SUMMARIZATION_SOURCE = "summarization"

#: 摘要消息的正文前缀：明确告诉模型这是背景信息，别当成用户发言复述
SUMMARY_MESSAGE_PREFIX = "以下是此前对话的摘要（仅作背景参考，不要直接复述）：\n\n"


class MessageIdMiddleware(AgentMiddleware):
    """
    为 AI 回答补充业务消息ID

    LangGraph 会为消息生成内部 id，但对外接口需要稳定且符合既有格式的
    `msg_xxxxxxxxxxxxxxxx`。该中间件在每轮结束时为尚未标记的 AI 回答
    补写 additional_kwargs.message_id —— 由于该字段随消息一起进入检查点，
    多轮对话中不会被重复生成。

    这里使用 model_copy 返回同 id 的新消息，交给 add_messages 归约器做替换，
    避免整份消息列表回写造成重复追加。
    """

    def after_agent(self, state, runtime):  # noqa: ANN001 - 签名由框架约定
        updates = []
        for message in state.get("messages", []):
            if not isinstance(message, AIMessage):
                continue
            # 跳过工具调用中间态与空内容消息
            if not message.content or message.additional_kwargs.get("message_id"):
                continue

            updates.append(
                message.model_copy(
                    update={
                        "additional_kwargs": {
                            **message.additional_kwargs,
                            "message_id": new_message_id(),
                        }
                    }
                )
            )

        return {"messages": updates} if updates else None


class ContextSummaryMiddleware(SummarizationMiddleware):
    """
    上下文摘要中间件（改造版）

    LangChain 默认把历史摘要作为一条 **HumanMessage** 插回消息列表，正文是
    `"Here is a summary of the conversation to date:\\n\\n{summary}"`。
    这会带来一个展示问题：历史接口把 HumanMessage 当作「用户发言」返回，
    前端就会冒出一条用户根本没发过的、还是英文的假消息。

    这里改为 **SystemMessage**：

    - 模型侧：system 角色本身就是「背景设定」，语义比伪装成用户发言更准确
    - 展示侧：历史接口只映射 Human / AI，SystemMessage 天然不出现

    构造方式（替换默认实现）：
        ContextSummaryMiddleware(model=llm, trigger=..., keep=..., summary_prompt=...)
    """

    @staticmethod
    def _build_new_messages(summary: str) -> list[SystemMessage]:
        """把摘要包成一条带来源标记的 SystemMessage"""
        return [
            SystemMessage(
                content=SUMMARY_MESSAGE_PREFIX + summary,
                additional_kwargs={"lc_source": SUMMARIZATION_SOURCE},
            )
        ]


class AnimeAgentFactory:
    """动漫问答 Agent 工厂"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._agent = None
        self._ephemeral_agent = None
        self._llm = None

    def _create_llm(self):
        """创建 DeepSeek 模型实例"""
        return ChatOpenAI(
            model=self._settings.llm_model,
            api_key=self._settings.deepseek_api_key,
            base_url=self._settings.deepseek_api_url,
            temperature=self._settings.llm_temperature,
            max_tokens=self._settings.llm_max_tokens,
        )

    def build(self, checkpointer, llm=None):
        """
        构建（并缓存）Agent

        Args:
            checkpointer: LangGraph 检查点存储（PostgresSaver / InMemorySaver）
            llm: 可选的模型实例，主要用于测试注入；缺省用 DeepSeek

        Returns:
            编译后的 Agent 图
        """
        if self._agent is not None:
            return self._agent

        self._llm = llm if llm is not None else self._create_llm()

        self._agent = self._compile(self._llm, checkpointer)

        logger.info(
            "动漫问答 Agent 已构建: model=%s, tools=%d(动漫=%d, 知识库=%d)",
            self._settings.llm_model,
            len(AGENT_TOOLS),
            len(ANIME_TOOLS),
            len(KNOWLEDGE_TOOLS),
        )
        return self._agent

    def _compile(self, llm, checkpointer):
        """按给定模型与检查点编译 Agent 图"""
        middleware = [MessageIdMiddleware()]

        # 上下文压缩：会话过长时自动摘要旧消息，避免超出模型上下文窗口
        # （例如 summarize 后会触发一次额外模型调用，故可关闭）
        if self._settings.context_summarization_enabled:
            middleware.append(self._build_summarization_middleware(llm))

        # 知识库清单注入：放在压缩之后，避免刚注入的提示又被摘要掉
        middleware.append(KnowledgeHintMiddleware())

        return create_agent(
            llm,
            AGENT_TOOLS,
            system_prompt=SYSTEM_PROMPT,
            state_schema=AgentState,
            middleware=middleware,
            checkpointer=checkpointer,
        )

    def _build_summarization_middleware(self, llm):
        """
        构造上下文摘要压缩中间件

        策略（可在 .env 调整）：
          - 触发条件：消息数超过 context_trigger_messages；
            或估算 token 数超过 context_trigger_tokens
          - 保留窗口：最近 context_keep_messages 条完整保留
          - 被替换掉的历史由模型总结成一段中文摘要
          - 自动保证 AI/Tool 消息成对保留，避免工具调用链断裂

        基于 LangChain 内置的 SummarizationMiddleware，仅替换摘要消息的构造方式
        （见 ContextSummaryMiddleware）：摘要以 SystemMessage 入状态，不进前端历史。
        """
        triggers: list[tuple] = []
        if self._settings.context_trigger_tokens > 0:
            triggers.append(("tokens", self._settings.context_trigger_tokens))
        if self._settings.context_trigger_messages > 0:
            triggers.append(("messages", self._settings.context_trigger_messages))

        if not triggers:
            # 两个阈值都关掉时退化为消息数触发，避免空列表
            triggers = [("messages", 40)]

        logger.info(
            "已启用上下文摘要压缩: 触发=%s, 保留最近 %d 条",
            triggers,
            self._settings.context_keep_messages,
        )

        return ContextSummaryMiddleware(
            model=llm,
            trigger=triggers,
            keep=("messages", self._settings.context_keep_messages),
            summary_prompt=CONTEXT_SUMMARY_PROMPT,
        )

    @property
    def agent(self):
        """获取已构建的 Agent"""
        if self._agent is None:
            raise RuntimeError("Agent 尚未构建，请先调用 build()")
        return self._agent

    @property
    def ephemeral_agent(self):
        """
        获取「无会话」场景使用的 Agent

        未提供 user_id 时不会有会话，也就不该产生任何检查点记录；
        但 LangGraph 一旦绑定了 checkpointer 就强制要求 thread_id，
        因此这里额外编译一个绑定内存检查点的实例用于该场景。
        """
        if self._agent is None:
            raise RuntimeError("Agent 尚未构建，请先调用 build()")

        if self._ephemeral_agent is None:
            from langgraph.checkpoint.memory import InMemorySaver

            self._ephemeral_agent = self._compile(self._llm, InMemorySaver())
        return self._ephemeral_agent


# ==================== 进程级单例 ====================

_factory: AnimeAgentFactory | None = None


def init_agent_factory(settings: Settings) -> AnimeAgentFactory:
    """初始化进程级 Agent 工厂"""
    global _factory
    if _factory is None:
        _factory = AnimeAgentFactory(settings)
    return _factory


def get_agent_factory() -> AnimeAgentFactory:
    """获取进程级 Agent 工厂"""
    if _factory is None:
        raise RuntimeError("Agent 工厂尚未初始化")
    return _factory
