"""
LangGraph 检查点（Checkpointer）装配

使用 langgraph-checkpoint-postgres 将对话状态持久化到 PostgreSQL。
每个会话对应一个 thread_id（即对外的 session_id），因此多轮对话的上下文
由检查点自动恢复，无需手工拼装历史消息。

⚠️ 必须使用 **AsyncPostgresSaver**，不能用同步的 PostgresSaver：

    本服务走 FastAPI 异步路由，对话链路使用 `agent.astream()` /
    `agent.aget_state()`。同步 PostgresSaver 未实现异步接口，
    `BaseCheckpointSaver.aget_tuple()` 会直接抛 NotImplementedError，
    导致整个流式问答不可用（这就是历史故障的根因）。

    同理，进程级单例的同步连接池（app.db.postgres）也无法供异步 saver 使用，
    因此这里自建一个 psycopg 异步连接池。
"""

import logging
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)


class CheckpointerFactory:
    """
    AsyncPostgresSaver 工厂

    生命周期：`open()` 建立异步连接池并执行幂等建表迁移，
    `close()` 释放连接池。两者都应在应用 lifespan 中调用。
    """

    def __init__(
        self,
        database_url: str,
        min_size: int = 1,
        max_size: int = 10,
        connect_timeout: int = 30,
    ) -> None:
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._connect_timeout = connect_timeout

        self._stack: AsyncExitStack | None = None
        self._pool: AsyncConnectionPool | None = None
        self._saver: AsyncPostgresSaver | None = None

    @property
    def saver(self) -> AsyncPostgresSaver:
        """获取已就绪的 AsyncPostgresSaver"""
        if self._saver is None:
            raise RuntimeError("检查点存储尚未初始化，请先调用 open()")
        return self._saver

    @property
    def pool(self) -> AsyncConnectionPool | None:
        """获取异步连接池（仅用于诊断）"""
        return self._pool

    async def open(self) -> AsyncPostgresSaver:
        """
        建立异步连接池、创建 saver 并执行建表迁移（幂等）

        会创建 checkpoints / checkpoint_blobs / checkpoint_writes /
        checkpoint_migrations 四张表。

        Returns:
            就绪的 AsyncPostgresSaver
        """
        if self._saver is not None:
            return self._saver

        stack = AsyncExitStack()
        try:
            pool = AsyncConnectionPool(
                conninfo=self._database_url,
                min_size=self._min_size,
                max_size=self._max_size,
                # AsyncPostgresSaver 的硬性要求：autocommit + dict_row
                kwargs={"autocommit": True, "row_factory": dict_row},
                open=False,
            )
            await pool.open(wait=True, timeout=self._connect_timeout)
            await stack.enter_async_context(pool)

            saver = AsyncPostgresSaver(pool)
            await saver.setup()

            self._pool = pool
            self._saver = saver
            self._stack = stack

            logger.info("LangGraph 检查点存储已就绪（AsyncPostgresSaver）")
            return saver
        except Exception:
            # 初始化失败时释放已占用的资源，避免连接泄漏
            await stack.aclose()
            raise

    async def close(self) -> None:
        """释放异步连接池"""
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._pool = None
            self._saver = None
            logger.info("LangGraph 检查点连接池已关闭")


# ==================== 进程级单例 ====================

_factory: CheckpointerFactory | None = None


def init_checkpointer_factory(**kwargs: Any) -> CheckpointerFactory:
    """初始化进程级检查点工厂"""
    global _factory
    if _factory is None:
        _factory = CheckpointerFactory(**kwargs)
    return _factory


def get_checkpointer_factory() -> CheckpointerFactory:
    """获取进程级检查点工厂"""
    if _factory is None:
        raise RuntimeError("检查点工厂尚未初始化")
    return _factory


async def close_checkpointer_factory() -> None:
    """关闭进程级检查点工厂"""
    global _factory
    if _factory is not None:
        await _factory.close()
        _factory = None
