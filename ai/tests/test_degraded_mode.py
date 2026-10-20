"""
会话/问答接口在数据库不可用时的降级行为

场景：PostgreSQL 未配置或未启动时，app.main 的 lifespan 会把
app.state.session_service / chat_service 置为 None。
此时接口应返回干净的 503 + 统一错误体，而不是 500 与未捕获的 ASGI 异常。

该用例是回归测试：修复前 GET /api/sessions 会抛出
`AttributeError: 'NoneType' object has no attribute 'list_sessions'`。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def degraded_client():
    """模拟「数据库不可用」的降级状态"""
    with TestClient(app) as client:
        # lifespan 已跳过数据库初始化（SKIP_DB_INIT=true），
        # 这里显式确保服务为 None，与真实降级路径一致
        app.state.session_service = None
        app.state.chat_service = None
        yield client


class TestDegradedSessions:
    """会话接口在服务不可用时应返回 503"""

    @pytest.mark.parametrize(
        "method,path,kwargs",
        [
            ("GET", "/api/sessions?user_id=4&limit=50", {}),
            ("POST", "/api/session/create", {"json": {"user_id": 4}}),
            ("GET", "/api/session/session_x/messages", {}),
            ("PUT", "/api/session/session_x/title", {"json": {"title": "t"}}),
            ("DELETE", "/api/session/session_x", {}),
        ],
    )
    def test_session_endpoints_return_503(self, degraded_client, method, path, kwargs):
        # 注意：使用 app.state 为 None 的降级状态，不能沿用 run_in_threadpool 崩溃路径
        response = degraded_client.request(method, path, **kwargs)

        assert response.status_code == 503, (
            f"{method} {path} 期望 503，实际 {response.status_code}"
        )
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
        # 必须给出可诊断的提示，而不是空消息
        assert body["error"]["message"]
        assert isinstance(body["error"]["timestamp"], float)


class TestDegradedChat:
    """问答接口在服务不可用时应返回 503"""

    def test_non_stream_chat_returns_503(self, degraded_client):
        response = degraded_client.post(
            "/api/anime-chat", json={"question": "推荐动漫", "user_id": 4}
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"

    def test_stream_chat_returns_503(self, degraded_client):
        response = degraded_client.post(
            "/api/anime-chat-stream", json={"question": "推荐动漫", "user_id": 4}
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


class TestDegradedIsolation:
    """降级时不应影响不依赖数据库的接口"""

    def test_health_still_works(self, degraded_client):
        response = degraded_client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_index_still_works(self, degraded_client):
        assert degraded_client.get("/").status_code == 200
