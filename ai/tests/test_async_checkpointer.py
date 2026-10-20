"""
异步链路回归测试

背景（真实故障）：
    生产使用同步的 `PostgresSaver` 作为 checkpointer，但对话链路调用的是
    `agent.astream()` / `agent.aget_state()`，即异步接口。
    `BaseCheckpointSaver.aget_tuple()` 的默认实现直接抛 NotImplementedError
    （同步 PostgresSaver 未覆写异步版本），导致**流式问答整体不可用**，
    报错形如：

        File "langgraph/checkpoint/base/__init__.py", line 441, in aget_tuple
            raise NotImplementedError

    而当时的测试全部使用 `InMemorySaver`，它同时实现了同步与异步接口，
    因此完全掩盖了这个问题。

本文件的做法：
    用 `SyncOnlyCheckpointer` 模拟「只实现同步接口」的检查点，
    其异步方法一律抛 NotImplementedError —— 与真实 PostgresSaver 行为一致。
    这样任何「误用同步/异步接口」的回归都会在**离线环境下立刻失败**，
    无需 PostgreSQL。
"""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.news import nodes as N  # noqa: F401 - 仅为与其他测试保持一致的导入顺序
from tests.fake_model import FakeToolChatModel


class SyncOnlyCheckpointer(InMemorySaver):
    """
    只有同步接口可用的检查点（模拟同步 PostgresSaver）

    异步方法一律抛 NotImplementedError，与
    `langgraph.checkpoint.base.BaseCheckpointSaver` 的默认实现一致。
    """

    def _async_unsupported(self, *args, **kwargs):
        raise NotImplementedError(
            "AsyncPostgresSaver required: this checkpointer implements no async methods"
        )

    async def aget_tuple(self, config):
        self._async_unsupported()

    async def aput(self, config, checkpoint, metadata, new_versions):
        self._async_unsupported()

    async def aput_writes(self, config, writes, task_id, task_path=""):
        self._async_unsupported()

    async def aget_state(self, config, *, subgraphs=False):
        self._async_unsupported()


@pytest.fixture
def sync_only_agent():
    """构建绑定「同步-only 检查点」的 Agent"""
    from app.agent.graph import AnimeAgentFactory
    from app.config import Settings

    settings = Settings(deepseek_api_key="test", llm_model="fake")
    factory = AnimeAgentFactory(settings)
    factory.build(SyncOnlyCheckpointer(), llm=FakeToolChatModel(response="测试回答"))
    return factory


class TestSyncOnlyCheckpointerFails:
    """先确认这个测试替身真的会拦住异步调用（否则测试是假绿）"""

    def test_astream_raises_not_implemented(self, sync_only_agent):
        agent = sync_only_agent.agent
        config = {"configurable": {"thread_id": "t1"}}
        state = {"messages": [], "user_id": 1}

        async def run():
            async for _ in agent.astream(state, config, stream_mode="messages"):
                pass

        with pytest.raises(NotImplementedError):
            asyncio.run(run())

    def test_aget_state_raises_not_implemented(self, sync_only_agent):
        agent = sync_only_agent.agent
        config = {"configurable": {"thread_id": "t1"}}

        with pytest.raises(NotImplementedError):
            asyncio.run(agent.aget_state(config))


class TestChatServiceUsesAsyncInterface:
    """
    会话/问答服务必须走异步接口

    因为生产检查点是 AsyncPostgresSaver（同步接口未实现），
    反之亦然 —— 两者不可混用。
    """

    def test_get_messages_async_exists_and_is_coroutine(self):
        from app.services.session_service import SessionService
        import inspect

        assert hasattr(SessionService, "get_messages_async"), (
            "SessionService 必须提供 get_messages_async —— "
            "路由层不能再通过 run_in_threadpool 调同步 get_messages"
        )
        assert inspect.iscoroutinefunction(SessionService.get_messages_async)

    def test_session_route_awaits_async_message_read(self):
        """
        路由必须 await 异步消息读取

        直接检查源码，防止有人改回 run_in_threadpool(get_messages)。
        """
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent
            / "app" / "api" / "routes_sessions.py"
        ).read_text(encoding="utf-8")

        assert "get_messages_async" in source, (
            "routes_sessions 必须调用 get_messages_async"
        )
        assert "run_in_threadpool(\n        session_service.get_messages" not in source, (
            "routes_sessions 不应再在线程池中调用同步 get_messages"
        )

    def test_main_uses_async_checkpointer_factory(self):
        """lifespan 必须使用异步检查点工厂（AsyncPostgresSaver）"""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent / "app" / "main.py"
        ).read_text(encoding="utf-8")

        assert "init_checkpointer_factory" in source
        assert "await checkpointer_factory.open()" in source
        assert "close_checkpointer_factory" in source
        assert "CheckpointerFactory(store.pool)" not in source, (
            "不应再复用同步连接池构造检查点"
        )

    def test_checkpointer_module_uses_async_saver(self):
        """checkpointer 模块必须基于 AsyncPostgresSaver"""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent
            / "app" / "agent" / "checkpointer.py"
        ).read_text(encoding="utf-8")

        assert "AsyncPostgresSaver" in source
        assert "AsyncConnectionPool" in source
        # 不应回退到同步 saver
        assert "from langgraph.checkpoint.postgres import PostgresSaver" not in source


class TestAsyncPathWorksWithAsyncSaver:
    """正向验证：异步检查点下，异步链路应完全正常"""

    def test_astream_works_with_async_capable_saver(self):
        from app.agent.graph import AnimeAgentFactory
        from app.config import Settings

        settings = Settings(deepseek_api_key="test", llm_model="fake")
        factory = AnimeAgentFactory(settings)
        # InMemorySaver 同时支持同步与异步，等价于异步可用的检查点
        factory.build(InMemorySaver(), llm=FakeToolChatModel(response="流式回答"))

        agent = factory.agent
        config = {"configurable": {"thread_id": "t-ok"}}
        state = {"messages": [], "user_id": 1}

        async def collect():
            chunks = []
            async for chunk, _meta in agent.astream(
                state, config, stream_mode="messages"
            ):
                content = getattr(chunk, "content", "")
                if isinstance(content, str) and content:
                    chunks.append(content)

            snapshot = await agent.aget_state(config)
            return chunks, snapshot

        chunks, snapshot = asyncio.run(collect())

        assert "".join(chunks) == "流式回答"
        assert snapshot is not None
        assert snapshot.values.get("messages")


class TestChatServiceStreamWithSyncOnlyCheckpointer:
    """
    端到端复现原始故障：ChatService.stream_answer 在同步-only 检查点下必须暴露问题

    这正是线上报错的位置 —— `NotImplementedError` 被 stream_answer 的
    `except Exception` 捕获后降级为 SSE error 事件，用户侧表现为「AI 不回答」。
    """

    def _build_services(self, checkpointer):
        from app.agent.graph import AnimeAgentFactory
        from app.config import Settings
        from app.services.chat_service import ChatService
        from app.services.session_service import SessionService
        from tests.conftest import FakeSessionStore

        settings = Settings(deepseek_api_key="test", llm_model="fake")
        # 使用与其它测试一致的内存存储，避免因缺失方法引入无关异常
        store = FakeSessionStore()
        factory = AnimeAgentFactory(settings)
        factory.build(checkpointer, llm=FakeToolChatModel(response="正常回答"))
        session_service = SessionService(store, factory, settings)
        chat_service = ChatService(store, factory, session_service)
        return store, session_service, chat_service

    @staticmethod
    def _collect(chat_service, question, user_id, session_id):
        async def run():
            return [
                frame
                async for frame in chat_service.stream_answer(question, user_id, session_id)
            ]

        return asyncio.run(run())

    def test_stream_degrades_to_error_event_with_sync_only_checkpointer(self):
        """
        同步-only 检查点 → 流式接口降级为 SSE error 事件

        `stream_answer` 的 `except Exception` 会把检查点异常转成 error 事件
        （HTTP 仍为 200），因此用户侧表现为「AI 不回答、只看到一句兜底提示」，
        而不是明显的服务器错误 —— 这正是原始故障难以察觉的原因。

        该断言同时锁住两点：
        1. 这条路径**必须**使用异步检查点（修复的核心）
        2. 误用同步检查点时的失败形态
        """
        _store, _session_service, chat_service = self._build_services(
            SyncOnlyCheckpointer()
        )

        frames = self._collect(chat_service, "请推荐一些好看的动漫", 1, None)
        assert frames, "应至少产生一个 SSE 事件"

        payload = json.loads(frames[0][len("data: "): -2])

        assert payload["type"] == "error", (
            "同步-only 检查点会让流式问答降级为 error 事件 —— 若此处不再是 error，"
            "说明缺陷已修复或复现方式失效"
        )
        assert payload["success"] is False
        # 兜底文案 + 真实错误原因（检查点未实现异步接口）
        assert "抱歉" in payload["chunk"]
        assert "AsyncPostgresSaver" in payload["error"]

    def test_stream_succeeds_with_async_capable_checkpointer(self):
        """异步可用的检查点 → 流式接口应正常产出内容并以 end 收尾"""
        _store, _session_service, chat_service = self._build_services(InMemorySaver())

        frames = self._collect(chat_service, "请推荐一些好看的动漫", 1, None)

        payloads = [json.loads(f[len("data: "): -2]) for f in frames]

        content = "".join(p["chunk"] for p in payloads if p["type"] == "content")
        assert content == "正常回答"
        assert payloads[-1]["type"] == "end"
        assert payloads[-1]["session_id"].startswith("session_")

    def test_session_messages_async_read_works(self):
        """路由使用的异步消息读取在异步检查点下应正常"""
        _store, session_service, chat_service = self._build_services(InMemorySaver())

        # 先跑一轮对话，产生检查点
        frames = self._collect(chat_service, "请推荐一些好看的动漫", 1, None)
        payloads = [json.loads(f[len("data: "): -2]) for f in frames]
        session_id = payloads[-1]["session_id"]

        messages = asyncio.run(session_service.get_messages_async(session_id))

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
