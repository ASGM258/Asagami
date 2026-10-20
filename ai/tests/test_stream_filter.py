"""
流式过滤与上下文压缩测试

策略（简化版）：
1. 正文（含工具调用前的过渡语）一律实时下发
2. ToolMessage 只转成"正在思考"提示，内容绝不外发
3. 工具调用发 tool 提示事件，不再有 retract 撤回
4. reasoning（思维链）无论出现在哪个字段，都不进正文
5. 流式拼出的正文 == 历史/非流式拼出的正文（同一条规则）
6. 上下文压缩中间件已挂载
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.graph import (
    SUMMARIZATION_SOURCE,
    AnimeAgentFactory,
    ContextSummaryMiddleware,
)
from app.config import Settings
from app.services.stream_filter import (
    AnswerStreamFilter,
    final_answer_from_messages,
    has_reasoning,
    last_turn_messages,
    message_answer_text,
)


def ai(text: str = "", tool_calls=None, blocks=None, **kwargs):
    if blocks is not None:
        return AIMessage(content=blocks, additional_kwargs=kwargs)
    return AIMessage(content=text, tool_calls=tool_calls or [], additional_kwargs=kwargs)


def tool_result(text: str = "工具结果 JSON"):
    return ToolMessage(content=text, tool_call_id="call_1")


def call(name: str, call_id: str = "c1"):
    return {"name": name, "args": {}, "id": call_id}


def render(events) -> str:
    """按前端语义还原展示文本：content 追加，thinking/tool 只影响提示符"""
    return "".join(e.text for e in events if e.kind == "content")


def kinds(events) -> list[str]:
    return [e.kind for e in events]


class TestDirectAnswerStreaming:
    """无工具调用：正文逐块实时下发（保住 token 级流式）"""

    def test_tokens_streamed_immediately(self):
        f = AnswerStreamFilter()
        events = []
        for piece in ["这是", "一段", "测试回答"]:
            events.extend(f.feed(ai(piece)))

        contents = [e.text for e in events if e.kind == "content"]
        assert contents == ["这是", "一段", "测试回答"]
        assert len(contents) > 1, "应是多块而非合并成一块"

    def test_no_thinking_event_without_tools(self):
        f = AnswerStreamFilter()
        events = f.feed(ai("直接回答"))
        assert all(e.kind != "thinking" for e in events)

    def test_no_retract_ever(self):
        """新策略不撤回任何已下发内容"""
        f = AnswerStreamFilter()
        events = []
        events += f.feed(ai("我来查询一下"))
        events += f.feed(ai("", tool_calls=[call("get_anime_info")]))
        events += f.feed(tool_result())
        events += f.feed(ai("你的记录如下"))
        assert "retract" not in kinds(events)


class TestToolMessageFiltered:
    """ToolMessage 的内容绝不外发，只作为状态信号"""

    def test_tool_message_produces_no_content(self):
        f = AnswerStreamFilter()
        events = f.feed(tool_result('{"secret": "internal json"}'))
        assert not [e for e in events if e.kind == "content"]
        assert '{"secret"' not in render(events)

    def test_tool_message_switches_to_thinking_hint(self):
        """工具执行完 → 提示前端切回"正在思考"，等模型续写"""
        f = AnswerStreamFilter()
        events = f.feed(tool_result())
        assert [e.kind for e in events] == ["thinking"]
        assert events[0].stage == "thinking"


class TestTransitionalTextShown:
    """过渡语属于正常回答的一部分，必须照常输出"""

    def test_transitional_text_is_streamed(self):
        f = AnswerStreamFilter()
        events = []
        events += f.feed(ai("我来查询一下"))
        events += f.feed(ai("你的追番记录。"))
        events += f.feed(ai("", tool_calls=[call("get_user_anime_history")]))

        assert render(events) == "我来查询一下你的追番记录。"

    def test_text_and_tool_call_in_same_chunk_keeps_text_first(self):
        """同一 chunk 既有正文又有 tool_calls：正文先发，再发工具提示"""
        f = AnswerStreamFilter()
        events = f.feed(ai("我先查一下。", tool_calls=[call("get_anime_info")]))

        assert kinds(events) == ["content", "tool"]
        assert events[0].text == "我先查一下。"
        assert events[1].tool == "get_anime_info"

    def test_text_after_tool_streams_immediately_not_buffered(self):
        """工具周期内正文不再缓冲 —— 这是与旧策略最大的区别"""
        f = AnswerStreamFilter()
        f.feed(tool_result())
        events = f.feed(ai("根据结果"))
        assert [e.text for e in events if e.kind == "content"] == ["根据结果"]


class TestMultiRoundToolCalls:
    """多轮工具调用：每轮都转一次圈"""

    def test_full_react_flow(self):
        f = AnswerStreamFilter()
        collected = []

        collected += f.feed_with_step(ai("先查资料。"), 1)
        collected += f.feed_with_step(ai("", tool_calls=[call("get_anime_info")]), 1)
        collected += f.feed_with_step(tool_result("{}"), 2)
        collected += f.feed_with_step(ai("再查一下。"), 3)
        collected += f.feed_with_step(
            ai("", tool_calls=[call("search_anime_by_name", "c2")]), 3
        )
        collected += f.feed_with_step(tool_result("{}"), 4)
        collected += f.feed_with_step(ai("最终答案：EVA 由庵野秀明执导。"), 5)

        shown = render(collected)
        # 过渡语 + 最终答案都在，工具结果不在
        assert shown == "先查资料。再查一下。最终答案：EVA 由庵野秀明执导。"
        assert "工具结果" not in shown

        tools = [e.tool for e in collected if e.kind == "tool"]
        assert tools == ["get_anime_info", "search_anime_by_name"]

    def test_same_tool_not_announced_twice_within_one_step(self):
        """流式下工具名只在首个分片出现，重复分片不应再提示"""
        f = AnswerStreamFilter()
        events = []
        events += f.feed_with_step(ai("", tool_calls=[call("get_anime_info")]), 1)
        events += f.feed_with_step(ai("", tool_calls=[call("get_anime_info")]), 1)
        assert len([e for e in events if e.kind == "tool"]) == 1


class TestReasoningNeverLeaks:
    """reasoning 绝不能混进正文"""

    def test_reasoning_in_additional_kwargs(self):
        f = AnswerStreamFilter()
        events = []
        events += f.feed(ai("", reasoning_content="用户想要推荐，先看他的追番历史"))
        events += f.feed(ai("推荐这几部："))

        shown = render(events)
        assert shown == "推荐这几部："
        assert "用户想要推荐" not in shown
        assert "reasoning" in [e.stage for e in events if e.kind == "thinking"]

    def test_reasoning_hint_only_once_per_step(self):
        f = AnswerStreamFilter()
        events = []
        for _ in range(5):
            events += f.feed_with_step(ai("", reasoning_content="想想"), 1)
        assert len([e for e in events if e.kind == "thinking"]) == 1, "不应逐块刷提示"

    def test_reasoning_in_content_blocks(self):
        f = AnswerStreamFilter()
        blocks = [
            {"type": "reasoning", "reasoning": "内部推理：用户偏好科幻"},
            {"type": "text", "text": "你偏爱科幻番。"},
        ]
        events = f.feed(ai(blocks=blocks))

        assert render(events) == "你偏爱科幻番。"
        assert "内部推理" not in render(events)

    def test_reasoning_and_text_in_same_chunk(self):
        """同一 chunk 的 reasoning 与正文必须分开：只出正文"""
        f = AnswerStreamFilter()
        blocks = [
            {"type": "thinking", "thinking": "先别输出这句"},
            {"type": "text", "text": "这句要输出"},
        ]
        events = f.feed(ai(blocks=blocks))
        assert render(events) == "这句要输出"

    def test_has_reasoning_helper(self):
        assert has_reasoning(ai("", reasoning_content="思考"))
        assert has_reasoning(ai(blocks=[{"type": "reasoning", "reasoning": "x"}]))
        assert not has_reasoning(ai("普通回答"))

    def test_reasoning_never_in_history_text(self):
        message = ai("", reasoning_content="不该出现的推理")
        assert message_answer_text(message) == ""


class TestNonStreamingConsistency:
    """流式拼出的正文必须与历史/非流式拼出的完全一致"""

    def test_concatenates_transition_and_answer(self):
        messages = [
            HumanMessage(content="EVA 的导演是谁"),
            ai("我需要查一下。", tool_calls=[call("t")]),
            tool_result(),
            ai("最终答案：庵野秀明。"),
        ]
        assert final_answer_from_messages(messages) == "我需要查一下。最终答案：庵野秀明。"

    def test_skips_tool_and_reasoning(self):
        messages = [
            HumanMessage(content="q"),
            ai("思考中", tool_calls=[call("t")], reasoning_content="隐秘推理"),
            tool_result(),
            ai("答案"),
        ]
        joined = final_answer_from_messages(messages)
        assert joined == "思考中答案"
        assert "隐秘推理" not in joined
        assert "工具结果" not in joined

    def test_matches_stream_render(self):
        """同一个消息序列，流式渲染与非流式拼接必须相同"""
        messages = [
            ai("我来查询一下", tool_calls=[call("get_anime_info")]),
            tool_result(),
            ai("你的记录如下"),
        ]

        f = AnswerStreamFilter()
        collected = []
        for index, message in enumerate(messages):
            collected += f.feed_with_step(message, index)

        assert render(collected) == final_answer_from_messages(messages)

    def test_handles_empty_and_none(self):
        assert final_answer_from_messages([]) == ""
        assert final_answer_from_messages(None) == ""

    def test_empty_list_when_no_text(self):
        messages = [ai("", tool_calls=[call("t")]), tool_result()]
        assert final_answer_from_messages(messages) == ""


class TestTurnScoping:
    """按 HumanMessage 切分轮次：不能让历史各轮的答案串进来"""

    def test_last_turn_messages_anchors_on_human(self):
        messages = [
            HumanMessage(content="q1"),
            ai("答案1"),
            HumanMessage(content="q2"),
            ai("答案2"),
        ]
        turn = last_turn_messages(messages)
        assert [type(m).__name__ for m in turn] == ["HumanMessage", "AIMessage"]
        assert final_answer_from_messages(messages) == "答案1答案2"  # 整份列表按规则拼接
        assert final_answer_from_messages(turn) == "答案2"          # 本轮切片才对

    def test_last_turn_handles_no_human(self):
        messages = [ai("孤立的回答")]
        assert last_turn_messages(messages) == messages

    def test_last_turn_handles_empty(self):
        assert last_turn_messages([]) == []
        assert last_turn_messages(None) == []

    def test_last_turn_keeps_tool_chain_of_current_turn(self):
        """本轮里工具调用的多个 AI 片段都要包含进来"""
        messages = [
            HumanMessage(content="q1"),
            ai("答案1"),
            HumanMessage(content="q2"),
            ai("我来查一下", tool_calls=[call("get_anime_info")]),
            tool_result(),
            ai("你的记录如下"),
        ]
        assert final_answer_from_messages(last_turn_messages(messages)) == (
            "我来查一下你的记录如下"
        )

    def test_chat_service_non_streaming_uses_current_turn(self):
        """
        非流式接口多轮时只能返回本轮的答案

        切轮次发生在入口（ChatService.answer / _persisted_message_id），
        下面两个私有 helper 保持纯粹：传什么就处理什么。
        """
        from app.services.chat_service import ChatService

        messages = [
            HumanMessage(content="q1"),
            ai("第一轮答案"),
            HumanMessage(content="q2"),
            ai("第二轮答案"),
        ]
        assert ChatService._last_ai_content(last_turn_messages(messages)) == "第二轮答案"

    def test_chat_service_message_id_follows_current_turn(self):
        from app.services.chat_service import ChatService

        old = ai("第一轮答案")
        old.additional_kwargs["message_id"] = "msg_old"
        new = ai("第二轮答案")
        new.additional_kwargs["message_id"] = "msg_new"

        messages = [HumanMessage(content="q1"), old, HumanMessage(content="q2"), new]
        assert ChatService._last_ai_message_id(last_turn_messages(messages)) == "msg_new"


class TestHistoryMerging:
    """历史接口把相邻 assistant 条目合并成一个气泡"""

    def test_merges_adjacent_assistant(self):
        from app.services.session_service import SessionService

        items = [
            {"message_id": "m1", "role": "user", "content": "问题", "created_at": None},
            {"message_id": "m2", "role": "assistant", "content": "我来查一下", "created_at": None},
            {"message_id": "m3", "role": "assistant", "content": "你的记录如下", "created_at": None},
        ]
        merged = SessionService._merge_consecutive_assistant(items)

        assert len(merged) == 2
        assert merged[1]["content"] == "我来查一下你的记录如下"
        assert merged[1]["message_id"] == "m3", "合并后取最后一条的 id"

    def test_does_not_merge_across_human(self):
        from app.services.session_service import SessionService

        items = [
            {"message_id": "m1", "role": "user", "content": "q1", "created_at": None},
            {"message_id": "m2", "role": "assistant", "content": "a1", "created_at": None},
            {"message_id": "m3", "role": "user", "content": "q2", "created_at": None},
            {"message_id": "m4", "role": "assistant", "content": "a2", "created_at": None},
        ]
        merged = SessionService._merge_consecutive_assistant(items)

        assert [m["role"] for m in merged] == ["user", "assistant", "user", "assistant"]
        assert merged[1]["content"] == "a1"
        assert merged[3]["content"] == "a2"

    def test_does_not_mutate_input(self):
        from app.services.session_service import SessionService

        items = [
            {"message_id": "m1", "role": "assistant", "content": "a", "created_at": None},
            {"message_id": "m2", "role": "assistant", "content": "b", "created_at": None},
        ]
        SessionService._merge_consecutive_assistant(items)
        assert items[0]["content"] == "a", "不应就地修改调用方传入的字典"


class TestSummaryHiddenFromHistory:
    """上下文摘要不得出现在会话历史里"""

    def test_format_message_skips_summary_system_message(self):
        from app.services.session_service import SessionService

        summary = ContextSummaryMiddleware._build_new_messages("旧对话摘要")[0]
        assert SessionService._format_message(summary, None) is None

    def test_format_message_skips_marked_human_message(self):
        """
        防御性：即使 LangChain 将来把摘要改回 HumanMessage，
        只要带 lc_source 标记也不能返回给前端
        """
        from app.services.session_service import SessionService

        message = HumanMessage(
            content="Here is a summary of the conversation to date:\n\n旧对话",
            additional_kwargs={"lc_source": SUMMARIZATION_SOURCE},
        )
        assert SessionService._format_message(message, None) is None

    def test_plain_system_message_skipped(self):
        from app.services.session_service import SessionService

        assert SessionService._format_message(SystemMessage(content="内部提示"), None) is None

    def test_snapshot_with_summary_returns_only_real_turns(self):
        """压缩过的会话：历史里只剩真实的 user / assistant 气泡"""
        from types import SimpleNamespace

        from app.services.session_service import SessionService

        summary = ContextSummaryMiddleware._build_new_messages("早期对话摘要")[0]
        snapshot = SimpleNamespace(
            values={
                "messages": [
                    summary,
                    HumanMessage(content="之前的消息被压缩了"),
                    ai("这是被保留下来的上一轮回答"),
                    HumanMessage(content="本轮问题"),
                    ai("本轮回答"),
                ]
            },
            created_at=None,
        )

        # 只用到映射逻辑，依赖传 None 即可
        service = SessionService(None, None, None)
        formatted = service._format_snapshot(snapshot, 0)

        roles = [item["role"] for item in formatted]
        assert roles == ["user", "assistant", "user", "assistant"]
        joined = "".join(item["content"] for item in formatted)
        assert "摘要" not in joined


class TestContextSummarizationConfigured:
    """上下文压缩中间件必须被挂载"""

    def test_middleware_enabled_by_default(self):
        factory = AnimeAgentFactory(Settings(deepseek_api_key="t", llm_model="fake"))
        assert factory._settings.context_summarization_enabled is True

    def test_summarization_middleware_built(self):
        """能构造出上下文摘要中间件（不实际调用模型）"""
        from app.agent.graph import ContextSummaryMiddleware

        factory = AnimeAgentFactory(Settings(deepseek_api_key="t", llm_model="fake"))
        llm = factory._create_llm()
        mw = factory._build_summarization_middleware(llm)

        assert isinstance(mw, ContextSummaryMiddleware)
        # 仍然是 LangChain 的 SummarizationMiddleware，只是改了摘要消息的构造
        assert type(mw).__mro__[1].__name__ == "SummarizationMiddleware"

    def test_summary_message_is_system_message(self):
        """
        摘要必须以 SystemMessage 入状态

        默认实现用 HumanMessage，历史接口会把它当用户发言返回，
        前端就冒出一条用户没发过的英文"发言"。
        """
        from langchain_core.messages import SystemMessage

        from app.agent.graph import SUMMARIZATION_SOURCE, ContextSummaryMiddleware

        messages = ContextSummaryMiddleware._build_new_messages("用户喜欢科幻番")

        assert len(messages) == 1
        message = messages[0]
        assert isinstance(message, SystemMessage), type(message).__name__
        assert message.additional_kwargs["lc_source"] == SUMMARIZATION_SOURCE
        assert "用户喜欢科幻番" in message.content
        # 前缀措辞用于告诉模型这是背景，不是用户发言
        assert "摘要" in message.content

    def test_summary_prompt_is_chinese(self):
        from app.agent.prompts import CONTEXT_SUMMARY_PROMPT

        assert "{messages}" in CONTEXT_SUMMARY_PROMPT
        assert "摘要" in CONTEXT_SUMMARY_PROMPT

    def test_can_disable_via_config(self):
        factory = AnimeAgentFactory(
            Settings(
                deepseek_api_key="t",
                llm_model="fake",
                context_summarization_enabled=False,
            )
        )
        assert factory._settings.context_summarization_enabled is False

    def test_summarization_actually_compresses_history(self):
        """
        功能验证：历史超过阈值后必须被压缩，而不是无限增长

        注意：这里用的是返回固定文本的假模型，所以摘要内容本身无意义
        （会看到 LangChain 的 "Here is a summary..." 前缀）；
        真实模型会按 CONTEXT_SUMMARY_PROMPT 生成中文摘要。
        本测试只关心「消息数是否真的被压下来」。
        """
        import asyncio

        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from langgraph.checkpoint.memory import InMemorySaver

        class SimpleFake(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

        settings = Settings(
            deepseek_api_key="t",
            llm_model="fake",
            context_summarization_enabled=True,
            context_trigger_messages=6,  # 超过 6 条即触发
            context_trigger_tokens=0,    # 只看消息数
            context_keep_messages=2,
        )

        model = SimpleFake(responses=[AIMessage(content=f"回答{i}") for i in range(40)])
        factory = AnimeAgentFactory(settings)
        factory.build(InMemorySaver(), llm=model)
        agent = factory.agent
        cfg = {"configurable": {"thread_id": "summarize-test"}}

        counts = []

        async def chat_rounds():
            for i in range(6):
                await agent.ainvoke(
                    {"messages": [HumanMessage(content=f"问题{i}")], "user_id": 1},
                    cfg,
                )
                snap = await agent.aget_state(cfg)
                counts.append(len(snap.values.get("messages", [])))

        asyncio.run(chat_rounds())

        # 6 轮若完全不压缩应有 12 条；被压缩后必然小于该值
        assert max(counts) <= 6, f"消息数应被控制在阈值附近，实际序列: {counts}"
        assert counts[-1] < 12, f"历史未被压缩，实际序列: {counts}"

        # 压缩后应出现摘要消息，而且必须是 SystemMessage
        from langchain_core.messages import SystemMessage

        from app.agent.graph import SUMMARIZATION_SOURCE

        snap = asyncio.run(agent.aget_state(cfg))
        messages = snap.values["messages"]

        summaries = [
            m
            for m in messages
            if isinstance(m, SystemMessage)
            and m.additional_kwargs.get("lc_source") == SUMMARIZATION_SOURCE
        ]
        assert summaries, "未发现以 SystemMessage 存储的摘要消息"

        # 摘要不能伪装成用户发言
        human_texts = [
            str(m.content) for m in messages if isinstance(m, HumanMessage)
        ]
        assert not [t for t in human_texts if "摘要" in t or "summary" in t.lower()], (
            f"摘要混进了 HumanMessage: {human_texts}"
        )


class TestSSEFrames:
    """SSE 事件编码"""

    def test_thinking_event_shape(self):
        import json

        from app.core import sse

        payload = json.loads(sse.thinking_event()[len("data: "): -2])
        assert payload["type"] == "thinking"
        assert payload["stage"] == "thinking"
        assert payload["chunk"] == ""

    def test_reasoning_stage_shape(self):
        import json

        from app.core import sse

        payload = json.loads(sse.thinking_event(stage="reasoning")[len("data: "): -2])
        assert payload["type"] == "thinking"
        assert payload["stage"] == "reasoning"

    def test_tool_event_carries_name(self):
        import json

        from app.core import sse

        payload = json.loads(
            sse.thinking_event(stage="tool", tool="get_anime_info")[len("data: "): -2]
        )
        assert payload["type"] == "thinking"
        assert payload["stage"] == "tool"
        assert payload["tool"] == "get_anime_info"

    def test_retract_event_still_encodable(self):
        """保留兼容：类型仍可编码，但业务链路已不再发出"""
        import json

        from app.core import sse

        payload = json.loads(sse.retract_event()[len("data: "): -2])
        assert payload["type"] == "retract"
        assert payload["success"] is True
