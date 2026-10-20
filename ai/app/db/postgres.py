"""
PostgreSQL 持久化层

承载两类数据，使用同一个库、同一套连接池：

1. `chat_sessions` —— 会话元数据（标题、user_id、软删除标记）。
   LangGraph 的检查点只保存对话状态，没有标题与软删除概念，故单独建表，
   并以 `thread_id == session_id` 与检查点一一对应。
2. LangGraph 检查点表（checkpoints / checkpoint_blobs / checkpoint_writes /
   checkpoint_migrations）—— 由 PostgresSaver 负责建表与读写。

注意：连接池必须开启 autocommit 并使用 dict_row 行工厂，
这是 langgraph-checkpoint-postgres 的硬性要求。
"""

import logging
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# 会话元数据表 DDL（幂等）
CHAT_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id    BIGINT      NOT NULL,
    title      VARCHAR(255) NOT NULL DEFAULT '新会话',
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted SMALLINT    NOT NULL DEFAULT 0
)
"""

CHAT_SESSIONS_INDEXES_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions (created_at)",
)


def format_timestamp(value: Any) -> str | None:
    """
    统一时间输出格式为 'YYYY-MM-DD HH:MM:SS'

    契约要求 created_at / updated_at 为字符串（前端类型声明为 string），
    且格式与旧版 MySQL TIMESTAMP 的字符串形式一致，因此无论是
    datetime 还是 LangGraph 检查点给出的 ISO 字符串，都统一转换为此格式。

    Args:
        value: datetime、ISO 字符串或已是目标格式的字符串

    Returns:
        格式化后的时间字符串，None 原样返回
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    text = str(value)
    # 兼容 ISO 8601（检查点 created_at 形如 2026-10-08T11:18:20.367616+00:00）
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


class PostgresStore:
    """PostgreSQL 连接池与会话元数据访问"""

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
        self._pool: ConnectionPool | None = None

    # ==================== 生命周期 ====================

    def connect(self) -> ConnectionPool:
        """
        创建连接池并初始化表结构

        Returns:
            已就绪的连接池

        Raises:
            RuntimeError: 连接池无法建立连接
        """
        if self._pool is not None:
            return self._pool

        pool = ConnectionPool(
            conninfo=self._database_url,
            min_size=self._min_size,
            max_size=self._max_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
        pool.open(wait=True, timeout=self._connect_timeout)
        self._pool = pool

        self._init_schema()
        logger.info("PostgreSQL 连接池已就绪")
        return pool

    def close(self) -> None:
        """关闭连接池"""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
            logger.info("PostgreSQL 连接池已关闭")

    @property
    def pool(self) -> ConnectionPool:
        """获取连接池，未初始化时抛错"""
        if self._pool is None:
            raise RuntimeError("PostgreSQL 连接池尚未初始化，请先调用 connect()")
        return self._pool

    @property
    def database_url(self) -> str:
        """连接串（供 PostgresSaver 使用）"""
        return self._database_url

    def _init_schema(self) -> None:
        """幂等创建会话元数据表与索引"""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CHAT_SESSIONS_DDL)
                for ddl in CHAT_SESSIONS_INDEXES_DDL:
                    cur.execute(ddl)
        logger.info("会话元数据表 chat_sessions 已就绪")

    # ==================== 会话元数据：写入 ====================

    def create_session(
        self, session_id: str, user_id: int, title: str = "新会话"
    ) -> bool:
        """
        创建会话元数据

        Args:
            session_id: 会话ID（同时作为 LangGraph thread_id）
            user_id: 用户ID
            title: 会话标题

        Returns:
            是否创建成功
        """
        sql = """
            INSERT INTO chat_sessions (session_id, user_id, title)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE
                SET title = EXCLUDED.title,
                    is_deleted = 0,
                    updated_at = CURRENT_TIMESTAMP
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (session_id, user_id, title))
            return True
        except Exception as exc:  # noqa: BLE001 - 统一记录并返回失败
            logger.error("创建会话失败: session_id=%s, error=%s", session_id, exc)
            return False

    def update_title(self, session_id: str, title: str) -> bool:
        """
        更新会话标题

        Returns:
            是否确实更新了记录（会话不存在时为 False）
        """
        sql = """
            UPDATE chat_sessions
               SET title = %s, updated_at = CURRENT_TIMESTAMP
             WHERE session_id = %s AND is_deleted = 0
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (title, session_id))
                    return cur.rowcount > 0
        except Exception as exc:  # noqa: BLE001
            logger.error("更新会话标题失败: session_id=%s, error=%s", session_id, exc)
            return False

    def touch_session(self, session_id: str) -> bool:
        """
        刷新会话的 updated_at

        每轮对话结束后调用，使会话列表按最近活跃时间排序。
        """
        sql = "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = %s"
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (session_id,))
                    return cur.rowcount > 0
        except Exception as exc:  # noqa: BLE001
            logger.error("刷新会话时间失败: session_id=%s, error=%s", session_id, exc)
            return False

    def soft_delete_session(self, session_id: str) -> bool:
        """软删除会话（仅置标记，保留元数据与检查点）"""
        sql = """
            UPDATE chat_sessions
               SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP
             WHERE session_id = %s
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (session_id,))
                    return cur.rowcount > 0
        except Exception as exc:  # noqa: BLE001
            logger.error("软删除会话失败: session_id=%s, error=%s", session_id, exc)
            return False

    def hard_delete_session(self, session_id: str) -> bool:
        """
        彻底删除会话

        同时清理会话元数据与 LangGraph 检查点（含消息），保证不残留。
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
                    cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (session_id,))
                    cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (session_id,))
                    cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (session_id,))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("彻底删除会话失败: session_id=%s, error=%s", session_id, exc)
            return False

    # ==================== 会话元数据：读取 ====================

    def get_session_info(self, session_id: str) -> dict | None:
        """
        获取单个未删除会话的元数据

        Returns:
            会话字典（时间为格式化字符串），不存在时返回 None
        """
        sql = """
            SELECT session_id, user_id, title, created_at, updated_at, is_deleted
              FROM chat_sessions
             WHERE session_id = %s AND is_deleted = 0
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (session_id,))
                    row = cur.fetchone()
            return self._normalize_session(row) if row else None
        except Exception as exc:  # noqa: BLE001
            logger.error("查询会话信息失败: session_id=%s, error=%s", session_id, exc)
            return None

    def get_user_sessions(self, user_id: int, limit: int = 50) -> list[dict]:
        """
        获取用户的会话列表（按最近更新时间倒序）

        Returns:
            [{session_id, title, created_at, updated_at}, ...]（字段与旧接口一致）
        """
        sql = """
            SELECT session_id, title, created_at, updated_at
              FROM chat_sessions
             WHERE user_id = %s AND is_deleted = 0
             ORDER BY updated_at DESC
             LIMIT %s
        """
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (user_id, limit))
                    rows = cur.fetchall()
            return [
                {
                    "session_id": row["session_id"],
                    "title": row["title"],
                    "created_at": format_timestamp(row["created_at"]),
                    "updated_at": format_timestamp(row["updated_at"]),
                }
                for row in rows
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("查询会话列表失败: user_id=%s, error=%s", user_id, exc)
            return []

    @staticmethod
    def _normalize_session(row: dict) -> dict:
        """统一会话元数据的时间字段格式"""
        normalized = dict(row)
        if "created_at" in normalized:
            normalized["created_at"] = format_timestamp(normalized["created_at"])
        if "updated_at" in normalized:
            normalized["updated_at"] = format_timestamp(normalized["updated_at"])
        return normalized


# ==================== 进程级单例 ====================

_store: PostgresStore | None = None


def init_postgres_store(
    database_url: str,
    min_size: int = 1,
    max_size: int = 10,
    connect_timeout: int = 30,
) -> PostgresStore:
    """初始化进程级 PostgreSQL 存储单例"""
    global _store
    if _store is None:
        _store = PostgresStore(
            database_url,
            min_size=min_size,
            max_size=max_size,
            connect_timeout=connect_timeout,
        )
        _store.connect()
    return _store


def get_postgres_store() -> PostgresStore:
    """获取进程级 PostgreSQL 存储单例"""
    if _store is None:
        raise RuntimeError("PostgreSQL 存储尚未初始化")
    return _store


def close_postgres_store() -> None:
    """关闭进程级 PostgreSQL 存储单例"""
    global _store
    if _store is not None:
        _store.close()
        _store = None
