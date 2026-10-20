"""
pytest 共享夹具

设计要点：用 InMemorySaver 替代 PostgresSaver，用内存版会话元数据存储替代
PostgreSQL —— 从而在没有数据库的环境下也能验证「图 + 检查点 + 服务 + SSE」
的完整链路。PostgreSQL 专有的连接池与建表逻辑不在此覆盖范围内。
"""

import os
import sys
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

# 保证可以 import app.*
AI_ROOT = Path(__file__).resolve().parent.parent
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

# 测试不依赖真实数据库：让 app.main 的 lifespan 跳过 PostgreSQL 初始化
# 必须在 app.config 首次实例化 Settings 之前设置
os.environ.setdefault("SKIP_DB_INIT", "true")

from app.agent.graph import AnimeAgentFactory  # noqa: E402
from app.config import Settings  # noqa: E402
from app.services.chat_service import ChatService  # noqa: E402
from app.services.session_service import SessionService  # noqa: E402
from tests.fake_model import FakeToolChatModel  # noqa: E402

# 测试用回答：逐字符流式输出
FAKE_ANSWER = "这是一段测试回答"


class FakeSessionStore:
    """内存版会话元数据存储，接口与 PostgresStore 对齐"""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.touch_count = 0

    def create_session(self, session_id: str, user_id: int, title: str = "新会话") -> bool:
        self.sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "created_at": "2026-01-01 00:00:00",
            "updated_at": "2026-01-01 00:00:00",
            "is_deleted": 0,
        }
        return True

    def get_session_info(self, session_id: str) -> dict | None:
        session = self.sessions.get(session_id)
        if session and not session["is_deleted"]:
            return session
        return None

    def get_user_sessions(self, user_id: int, limit: int = 50) -> list[dict]:
        rows = [
            {
                "session_id": s["session_id"],
                "title": s["title"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
            }
            for s in self.sessions.values()
            if s["user_id"] == user_id and not s["is_deleted"]
        ]
        return rows[:limit]

    def update_title(self, session_id: str, title: str) -> bool:
        session = self.get_session_info(session_id)
        if not session:
            return False
        session["title"] = title
        return True

    def touch_session(self, session_id: str) -> bool:
        self.touch_count += 1
        return True

    def soft_delete_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        session["is_deleted"] = 1
        return True

    def hard_delete_session(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None


@pytest.fixture
def settings() -> Settings:
    """测试配置"""
    return Settings(
        deepseek_api_key="test-key",
        llm_model="fake-model",
        default_session_title="新会话",
    )


@pytest.fixture
def store() -> FakeSessionStore:
    """内存会话元数据存储"""
    return FakeSessionStore()


@pytest.fixture
def agent_factory(settings: Settings) -> AnimeAgentFactory:
    """已构建的 Agent 工厂（内存检查点 + 假模型）"""
    factory = AnimeAgentFactory(settings)
    factory.build(
        InMemorySaver(),
        llm=FakeToolChatModel(response=FAKE_ANSWER),
    )
    return factory


@pytest.fixture
def session_service(store, agent_factory, settings) -> SessionService:
    """会话服务"""
    return SessionService(store, agent_factory, settings)


@pytest.fixture
def chat_service(store, agent_factory, session_service) -> ChatService:
    """聊天服务"""
    return ChatService(store, agent_factory, session_service)
