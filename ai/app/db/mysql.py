"""
MySQL 业务数据访问层

分两类用途：
1. 只读查询 —— anime / user_anime 等表归 Java 后端所有，AI 侧仅查询
2. 读写 —— news / news_review_log 两张资讯表由本服务写入

本模块的连接部分由原 ai_agent/database.py 迁移而来，行为保持不变。
"""

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)


class MySQLClient:
    """MySQL 客户端（支持只读查询与写入）"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        self._config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
        }

    # ==================== 连接管理 ====================

    def get_connection(self):
        """
        建立数据库连接

        Returns:
            MySQL 连接对象，失败返回 None
        """
        try:
            connection = mysql.connector.connect(**self._config)
            if connection.is_connected():
                return connection
        except Error as exc:
            logger.error("连接 MySQL 失败: %s", exc)
        return None

    @staticmethod
    def close_connection(connection) -> None:
        """关闭数据库连接"""
        if connection and connection.is_connected():
            connection.close()

    @contextmanager
    def cursor(self, dictionary: bool = True, commit: bool = False) -> Iterator[Any]:
        """
        连接与游标的上下文管理器

        Args:
            dictionary: 是否使用字典游标（列名 -> 值）
            commit: 退出时是否提交事务

        Yields:
            游标对象；连接失败时抛出 RuntimeError
        """
        connection = self.get_connection()
        if not connection:
            raise RuntimeError("无法连接 MySQL，请检查数据库配置与运行状态")

        try:
            cur = connection.cursor(dictionary=dictionary)
            yield cur
            if commit:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            try:
                cur.close()
            except Exception:  # noqa: BLE001 - 关闭失败无需上抛
                pass
            self.close_connection(connection)

    # ==================== 只读查询 ====================

    def execute_query(
        self, query: str, params: tuple | None = None, fetch_one: bool = False
    ) -> Any:
        """
        执行只读查询

        Args:
            query: SQL 语句
            params: 查询参数
            fetch_one: 是否只取一条记录

        Returns:
            记录列表 / 单条记录 / 失败时为 None
        """
        connection = self.get_connection()
        if not connection:
            return None

        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params) if params else cursor.execute(query)
            result = cursor.fetchone() if fetch_one else cursor.fetchall()
            cursor.close()
            return result
        except Error as exc:
            logger.error("执行查询失败: %s", exc)
            return None
        finally:
            self.close_connection(connection)

    # ==================== 写入 ====================

    def execute_update(self, query: str, params: tuple | None = None) -> int:
        """
        执行写入语句并提交

        Args:
            query: SQL 语句
            params: 参数

        Returns:
            受影响行数；失败返回 0
        """
        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.execute(query, params) if params else cursor.execute(query)
            connection.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except Error as exc:
            logger.error("执行写入失败: %s", exc)
            connection.rollback()
            return 0
        finally:
            self.close_connection(connection)

    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        """
        批量写入并在同一事务中提交

        Args:
            query: SQL 语句
            params_list: 参数列表

        Returns:
            受影响行数；失败返回 0
        """
        if not params_list:
            return 0

        connection = self.get_connection()
        if not connection:
            return 0

        try:
            cursor = connection.cursor()
            cursor.executemany(query, params_list)
            connection.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except Error as exc:
            logger.error("批量写入失败: %s", exc)
            connection.rollback()
            return 0
        finally:
            self.close_connection(connection)


# ==================== 进程级单例 ====================

_client: MySQLClient | None = None


def init_mysql_client(
    host: str, port: int, user: str, password: str, database: str
) -> MySQLClient:
    """初始化进程级 MySQL 客户端单例"""
    global _client
    if _client is None:
        _client = MySQLClient(host, port, user, password, database)
    return _client


def get_mysql_client() -> MySQLClient:
    """获取进程级 MySQL 客户端单例"""
    if _client is None:
        raise RuntimeError("MySQL 客户端尚未初始化")
    return _client


def execute_query(
    query: str, params: tuple | None = None, fetch_one: bool = False
) -> Any:
    """
    便捷只读查询（保持与原 ai_agent.database.execute_query 相同的调用方式）

    资讯工具函数直接调用此函数，避免逐个注入客户端。
    """
    return get_mysql_client().execute_query(query, params, fetch_one)


def execute_update(query: str, params: tuple | None = None) -> int:
    """便捷写入"""
    return get_mysql_client().execute_update(query, params)
