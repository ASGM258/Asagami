"""
流式输出过滤器（简化策略）

三条规则：

1. **正文一律实时下发**
   包括工具调用前的那句过渡语（"我来查询一下你的记录"）。
   它就是正常的对话内容，没必要藏起来，也没必要先发再撤回。

2. **工具调用只发提示事件**
   前端据此显示转圈（"正在查询追番记录…"）。ReAct 循环里再调一次工具，
   就再发一次，前端重新转圈即可。

3. **模型的 reasoning 绝不进入正文**
   reasoning 只有两个合法来源，都不在 `content` 里：
     - `additional_kwargs["reasoning_content"]`（DeepSeek-R1 / ChatDeepSeek）
     - `content` 块列表中 `type` 为 reasoning / thinking 的块（LC v1 content_blocks）
   `ChatOpenAI` 走 chat-completions 时这些字段会被直接丢弃，取不到也无妨；
   只要能取到，就只用作"正在思考"提示，永远不拼进正文。

与旧实现的区别：不再有 retract（撤回）与 buffer（缓冲），因此工具调用之后的
最终回答同样是逐字流式的，不会整段"啪"地出现。
"""

import logging
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

# 提示阶段
STAGE_THINKING = "thinking"    # 模型在思考 / 工具执行完等待模型续写
STAGE_REASONING = "reasoning"  # 模型正在产出 reasoning（思维链）
STAGE_TOOL = "tool"            # 正在调用某个工具

# reasoning 可能落在 additional_kwargs 的这些键上
_REASONING_KWARGS_KEYS = ("reasoning_content", "reasoning", "thinking")
# reasoning 可能对应的 content 块类型
_REASONING_BLOCK_TYPES = frozenset({"reasoning", "reasoning_content", "thinking", "thought"})
# 视为普通文本的 content 块类型
_TEXT_BLOCK_TYPES = frozenset({"text", "text_delta", "output_text"})


@dataclass
class StreamEvent:
    """
    过滤器产出的逻辑事件

    kind:
        - "content"  最终回答 / 过渡语的文本增量，直接发给前端累加
        - "thinking" 提示前端显示转圈，`stage` 说明是思考还是 reasoning
        - "tool"     观察到一次工具调用，携带工具名
    """

    kind: str
    text: str = ""
    tool: str | None = None
    stage: str = STAGE_THINKING


# ==================== 消息内容拆分 ====================


def _reasoning_from_kwargs(chunk) -> str:
    """从 additional_kwargs 里提取 reasoning 文本"""
    kwargs = getattr(chunk, "additional_kwargs", None) or {}
    if not isinstance(kwargs, dict):
        return ""

    parts: list[str] = []
    for key in _REASONING_KWARGS_KEYS:
        value = kwargs.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            # 少数提供方给的是 {"content": "..."} / {"text": "..."}
            for text_key in ("content", "text"):
                text = value.get(text_key)
                if isinstance(text, str):
                    parts.append(text)
                    break
    return "".join(parts)


def split_content(chunk) -> tuple[str, str]:
    """
    把一条消息 / 消息块拆成 (可展示正文, reasoning 文本)

    - `content` 为字符串：整段都是正文（reasoning 不在这条路径上）
    - `content` 为块列表：只把 text 类块当正文，reasoning 类块单独取出

    Returns:
        (answer_text, reasoning_text)
    """
    content = getattr(chunk, "content", None)

    if isinstance(content, str):
        return content, ""

    if not isinstance(content, list):
        return "", ""

    answer_parts: list[str] = []
    reasoning_parts: list[str] = []

    for block in content:
        if isinstance(block, str):
            answer_parts.append(block)
            continue
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type in _REASONING_BLOCK_TYPES:
            for key in ("reasoning", "thinking", "text"):
                text = block.get(key)
                if isinstance(text, str):
                    reasoning_parts.append(text)
                    break
        elif block_type is None or block_type in _TEXT_BLOCK_TYPES:
            text = block.get("text")
            if isinstance(text, str):
                answer_parts.append(text)

    return "".join(answer_parts), "".join(reasoning_parts)


def message_answer_text(message) -> str:
    """单条消息里可以展示给用户的正文（不含 reasoning）"""
    if not isinstance(message, AIMessage):
        return ""
    answer, _ = split_content(message)
    return answer


def has_reasoning(message) -> bool:
    """该消息是否带有 reasoning 内容"""
    if not isinstance(message, AIMessage):
        return False
    _, reasoning = split_content(message)
    return bool(reasoning or _reasoning_from_kwargs(message))


def _tool_names(chunk) -> list[str]:
    """
    取本次 chunk 声明要调用的工具名

    流式场景下工具名只在工具调用的第一个 chunk 出现，后续分片只有半截参数，
    因此这里过滤掉空名即可天然去重。
    """
    names: list[str] = []
    for call in getattr(chunk, "tool_calls", None) or []:
        if isinstance(call, dict):
            name = call.get("name")
        else:
            name = getattr(call, "name", None)
        if name:
            names.append(str(name))
    return names


# ==================== 过滤器 ====================


class AnswerStreamFilter:
    """
    把 LangGraph 的消息流转换为一串逻辑事件

    用法：
        f = AnswerStreamFilter()
        async for chunk, meta in agent.astream(..., stream_mode="messages"):
            for event in f.feed_with_step(chunk, meta.get("langgraph_step")):
                ...
    """

    def __init__(self) -> None:
        self._step: int | str | None = None
        # 本次模型调用的 reasoning 提示是否已经发过（每步只发一次，避免刷屏）
        self._reasoning_announced = False
        # 本次模型调用已提示过的工具名
        self._announced_tools: set[str] = set()

    # ==================== 主流程 ====================

    def feed_with_step(self, chunk, step: int | str | None) -> list[StreamEvent]:
        """
        带超步号的 feed

        超步变化意味着进入新的一次模型调用，重置「本轮已提示过什么」的状态，
        这样多轮工具调用能各自转一次圈。
        """
        if step is not None and step != self._step:
            self._step = step
            self._reasoning_announced = False
            self._announced_tools.clear()

        return self.feed(chunk)

    def feed(self, chunk) -> list[StreamEvent]:
        """处理单个 chunk，返回需要下发的事件"""
        # 工具返回的原始数据属于内部数据，永不外发；
        # 但它标志工具已执行完，接下来是模型续写 —— 切回「正在思考」提示。
        if isinstance(chunk, ToolMessage):
            logger.debug("[stream] 工具执行完毕: tool_call_id=%s", chunk.tool_call_id)
            return [StreamEvent(kind="thinking", stage=STAGE_THINKING)]

        if not isinstance(chunk, AIMessage):
            return []

        answer, reasoning = split_content(chunk)
        reasoning += _reasoning_from_kwargs(chunk)

        events: list[StreamEvent] = []

        # reasoning 只用来提示，绝不进正文
        if reasoning:
            logger.debug("[stream] 收到 reasoning %d 字符（不输出）", len(reasoning))
            if not self._reasoning_announced:
                self._reasoning_announced = True
                events.append(StreamEvent(kind="thinking", stage=STAGE_REASONING))

        # 正文一律实时下发：过渡语也好、最终答案也好，都是要说给用户听的
        if answer:
            events.append(StreamEvent(kind="content", text=answer))

        # 工具调用提示（同一轮里同名工具只提示一次）
        for name in _tool_names(chunk):
            if name in self._announced_tools:
                continue
            self._announced_tools.add(name)
            events.append(StreamEvent(kind="tool", tool=name))

        return events


# ==================== 内部调用过滤 ====================

#: 上下文摘要中间件给内部调用打的标记
INTERNAL_SOURCE = "summarization"
#: 内部节点的名字前缀（这些节点的产出不该出现在前端）
#: - 摘要中间件：压缩上下文时发起的摘要模型调用 + 它注入的摘要 SystemMessage
#: - 知识库提示中间件：每轮注入的知识库清单 SystemMessage
INTERNAL_NODE_PREFIXES = ("ContextSummaryMiddleware", "KnowledgeHintMiddleware")
#: 内部注入消息的来源标记（additional_kwargs.lc_source）
INTERNAL_SOURCES = ("summarization", "knowledge-hint")


def is_internal_chunk(metadata: dict | None) -> bool:
    """
    判断该流式 chunk 是否来自「内部维护调用」，不该展示给用户

    `stream_mode="messages"` 会把图上**所有**模型调用的产出都吐出来，
    其中包括 `SummarizationMiddleware` 为了压缩上下文而发起的摘要调用 ——
    它的输出是给模型看的内部笔记（"用户问了什么 / 有什么未完成"），
    一旦漏到前端，用户就会看到一段莫名其妙的"总结"。

    两个判据（都来自 LangGraph 注入的 metadata，实测均可命中）：
    - `lc_source` 属于内部来源（`summarization` / `knowledge-hint`）
    - `langgraph_node` 以内部中间件类名开头（中间件作为节点出现时，
      包括它注入的 SystemMessage）
    """
    if not metadata:
        return False

    if str(metadata.get("lc_source") or "").lower() in INTERNAL_SOURCES:
        return True

    node = str(metadata.get("langgraph_node") or "")
    return any(node.startswith(prefix) for prefix in INTERNAL_NODE_PREFIXES)


# ==================== 非流式路径 ====================


def last_turn_messages(messages) -> list:
    """
    取出「本轮对话」的消息切片

    LangGraph 带检查点时，`ainvoke` 返回的是**整个会话**的 messages（含历史所有轮）。
    直接把整份列表交给 `final_answer_from_messages()` 会把历史每一轮的答案都拼进来，
    所以要用最后一条 HumanMessage 作为本轮的起点。

    锚定 HumanMessage 而不是「取最后 N 条」的原因：一轮对话的消息条数不固定
    （工具调用越多次条数越多），只有 HumanMessage 是稳定的轮次分隔符。

    Args:
        messages: 完整消息列表

    Returns:
        从最后一条 HumanMessage 开始到结尾的切片；列表里没有 HumanMessage 时原样返回
    """
    items = list(messages or [])
    for index in range(len(items) - 1, -1, -1):
        if isinstance(items[index], HumanMessage):
            return items[index:]
    return items


def final_answer_from_messages(messages) -> str:
    """
    从消息列表里取出「展示给用户」的完整正文

    与流式链路保持同一规则：按顺序拼接所有 AIMessage 的正文
    （过渡语 + 最终答案），跳过 ToolMessage 与 reasoning。
    这样刷新会话看到的历史，与流式时逐字累积出来的气泡完全一致。

    ⚠️ 只拼接传入的这一段。做整轮问答时请先过 `last_turn_messages()`，
    否则会把历史各轮的答案一起拼进来。

    Args:
        messages: 一段消息列表（通常是本轮切片）

    Returns:
        拼接后的正文；没有任何正文时返回空串
    """
    parts = [message_answer_text(message) for message in (messages or [])]
    return "".join(part for part in parts if part)
