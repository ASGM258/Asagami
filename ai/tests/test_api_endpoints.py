"""
端到端接口测试

用真实 HTTP 层（TestClient）验证路由注册、SSE 响应头与事件流，
其中会话服务替换为内存实现，因此无需 PostgreSQL。
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_chat_service, get_session_service
from app.main import app
from tests.conftest import FAKE_ANSWER


@pytest.fixture
def client(chat_service, session_service):
    """注入了内存服务的测试客户端"""
    app.dependency_overrides[get_chat_service] = lambda: chat_service
    app.dependency_overrides[get_session_service] = lambda: session_service
    # 跳过 lifespan 中的数据库初始化，直接使用注入的服务
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def parse_sse(text: str) -> list[dict]:
    """解析 SSE 响应文本为负载列表"""
    payloads = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        payloads.append(json.loads(block[len("data: "):]))
    return payloads


class TestHealthEndpoints:
    """无需数据库的接口"""

    def test_health(self, client):
        response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "anime-ai-chat"
        assert isinstance(body["timestamp"], float)

    def test_index_lists_all_endpoints(self, client):
        response = client.get("/")

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "欢迎使用动漫AI问答系统"
        assert len(body["endpoints"]) == 8
        assert body["example_request"]["user_id"] == 1


class TestChatEndpoints:
    """问答接口"""

    def test_non_stream_chat(self, client):
        response = client.post(
            "/api/anime-chat",
            json={"question": "请推荐一些好看的动漫", "user_id": 7},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "问答成功"
        assert body["data"]["answer"] == FAKE_ANSWER
        assert body["data"]["is_anime_related"] is True
        assert body["data"]["session_id"].startswith("session_")
        assert body["data"]["message_id"].startswith("msg_")

    def test_non_stream_chat_non_anime(self, client):
        response = client.post(
            "/api/anime-chat",
            json={"question": "请帮我写一段快速排序的代码实现", "user_id": 7},
        )

        body = response.json()
        assert body["success"] is True
        assert body["message"] == "非动漫相关问题"
        assert body["data"]["is_anime_related"] is False

    def test_non_stream_chat_empty_question(self, client):
        response = client.post("/api/anime-chat", json={"question": "  "})

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "EMPTY_QUESTION"

    def test_stream_chat_sse_headers_and_events(self, client):
        response = client.post(
            "/api/anime-chat-stream",
            json={"question": "请推荐一些好看的动漫", "user_id": 7},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"

        payloads = parse_sse(response.text)
        assert payloads[-1]["type"] == "end"
        assert payloads[-1]["session_id"].startswith("session_")
        assert payloads[-1]["message_id"].startswith("msg_")

        accumulated = "".join(p["chunk"] for p in payloads if p["type"] == "content")
        assert accumulated == FAKE_ANSWER

    def test_stream_chat_missing_question_is_json_error(self, client):
        response = client.post("/api/anime-chat-stream", json={})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "MISSING_PARAMETER"


class TestSessionEndpoints:
    """会话管理接口"""

    def test_create_list_update_delete_flow(self, client):
        # 创建
        created = client.post("/api/session/create", json={"user_id": 7})
        assert created.status_code == 200
        session_id = created.json()["data"]["session_id"]

        # 列表
        listed = client.get("/api/sessions", params={"user_id": 7})
        body = listed.json()
        assert body["data"]["count"] == 1
        assert set(body["data"]["sessions"][0].keys()) == {
            "session_id",
            "title",
            "created_at",
            "updated_at",
        }

        # 改名
        renamed = client.put(
            f"/api/session/{session_id}/title", json={"title": "改个名字"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["data"]["session_id"] == session_id

        # 删除（软删除）
        deleted = client.delete(f"/api/session/{session_id}", params={"hard": False})
        assert deleted.status_code == 200
        assert deleted.json()["message"] == "会话已删除"

        # 删除后列表为空
        assert client.get("/api/sessions", params={"user_id": 7}).json()["data"]["count"] == 0

    def test_messages_after_chat(self, client):
        chat = client.post(
            "/api/anime-chat",
            json={"question": "请推荐一些好看的动漫", "user_id": 7},
        )
        session_id = chat.json()["data"]["session_id"]

        response = client.get(f"/api/session/{session_id}/messages")
        body = response.json()

        assert response.status_code == 200
        assert body["data"]["session_id"] == session_id
        assert body["data"]["count"] == 2
        assert set(body["data"]["messages"][0].keys()) == {
            "message_id",
            "role",
            "content",
            "created_at",
        }

    def test_messages_unknown_session_is_404(self, client):
        response = client.get("/api/session/session_ghost/messages")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_sessions_missing_user_id(self, client):
        response = client.get("/api/sessions")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "MISSING_PARAMETER"

    def test_update_title_empty_rejected(self, client):
        session_id = client.post(
            "/api/session/create", json={"user_id": 7}
        ).json()["data"]["session_id"]

        response = client.put(f"/api/session/{session_id}/title", json={"title": "  "})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EMPTY_TITLE"

    def test_hard_delete_removes_session(self, client):
        session_id = client.post(
            "/api/session/create", json={"user_id": 7}
        ).json()["data"]["session_id"]

        response = client.delete(f"/api/session/{session_id}", params={"hard": True})

        assert response.status_code == 200
        assert client.get(f"/api/session/{session_id}/messages").status_code == 404
