"""
MCP stdio 客户端测试

用一个「假 MCP 服务端」（同样是 python 子进程，实现同样的 JSON-RPC）验证：
1. 握手（initialize + notifications/initialized）
2. tools/list / tools/call 的请求-响应配对
3. 服务端插入的通知不会打乱请求配对
4. 服务端返回 error、结果标记 isError 时的异常处理
5. 无响应时的超时、子进程退出后的自动重启
"""

import sys

import pytest

from app.mcp.stdio_client import McpError, McpStdioClient

# 假服务端：逐行 JSON-RPC，故意在响应前插入一条通知，模拟真实服务端的日志推送
FAKE_SERVER = r'''
import json, sys, time

TOOLS = [
    {
        "name": "echo",
        "description": "回显参数",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
    },
    {
        "name": "boom",
        "description": "返回 isError",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hang",
        "description": "永不响应",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

def send(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue

    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        # 先发一条通知（无 id），客户端必须忽略它
        send({"jsonrpc": "2.0", "method": "notifications/message",
              "params": {"level": "info", "data": "starting"}})
        send({"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake-mcp", "version": "0.0.1"},
        }})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        args = (msg.get("params") or {}).get("arguments") or {}
        if name == "echo":
            send({"jsonrpc": "2.0", "method": "notifications/progress",
                  "params": {"progress": 50}})
            send({"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": json.dumps(args, ensure_ascii=False)}],
            }})
        elif name == "boom":
            send({"jsonrpc": "2.0", "id": req_id, "result": {
                "isError": True,
                "content": [{"type": "text", "text": "工具炸了"}],
            }})
        elif name == "hang":
            time.sleep(30)
        else:
            send({"jsonrpc": "2.0", "id": req_id,
                  "error": {"code": -32602, "message": "未知工具"}})
'''


def make_client(timeout: float = 5.0) -> McpStdioClient:
    return McpStdioClient(
        [sys.executable, "-u", "-c", FAKE_SERVER],
        env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        timeout=timeout,
    )


@pytest.fixture
def client():
    c = make_client()
    c.start()
    try:
        yield c
    finally:
        c.close()


class TestHandshake:
    def test_start_completes_handshake(self, client):
        assert client.alive

    def test_start_is_idempotent(self, client):
        client.start()  # 已启动不应重启
        assert client.alive

    def test_close_terminates_process(self):
        c = make_client()
        c.start()
        process = c._process
        c.close()

        assert c.alive is False
        assert process is not None and process.poll() is not None

    def test_close_without_start_is_safe(self):
        c = make_client()
        c.close()


class TestListTools:
    def test_lists_tools_with_schema(self, client):
        tools = client.list_tools()

        names = [t.name for t in tools]
        assert names == ["echo", "boom", "hang"]

        echo = tools[0]
        assert echo.description == "回显参数"
        assert echo.input_schema["properties"]["text"]["type"] == "string"

    def test_caches_tools(self, client):
        first = client.list_tools()
        cached = client.list_tools()
        refreshed = client.list_tools(refresh=True)

        assert [t.name for t in first] == [t.name for t in cached]
        assert [t.name for t in refreshed] == [t.name for t in first]


class TestCallTool:
    def test_call_returns_text_result(self, client):
        text = client.call_tool("echo", {"text": "斩服少女"})
        assert "斩服少女" in text

    def test_notifications_do_not_break_pairing(self, client):
        """服务端插入的通知（无 id）不能打乱请求与响应的配对"""
        for index in range(3):
            text = client.call_tool("echo", {"n": index})
            assert f'"n": {index}' in text

    def test_is_error_raises(self, client):
        with pytest.raises(McpError) as exc_info:
            client.call_tool("boom")
        assert "工具炸了" in str(exc_info.value)

    def test_jsonrpc_error_raises(self, client):
        with pytest.raises(McpError) as exc_info:
            client.call_tool("no_such_tool")
        assert "未知工具" in str(exc_info.value)

    def test_timeout_raises(self):
        c = make_client(timeout=1.0)
        c.start()
        try:
            with pytest.raises(McpError) as exc_info:
                c.call_tool("hang")
            assert "超时" in str(exc_info.value)
        finally:
            c.close()


class TestResilience:
    def test_restarts_after_process_dies(self, client):
        process = client._process
        assert process is not None
        process.kill()
        process.wait(timeout=10)

        # 下一次调用应自动重启并重新握手
        text = client.call_tool("echo", {"after": "restart"})
        assert "restart" in text
        assert client._process is not process

    def test_start_raises_for_missing_binary(self):
        c = McpStdioClient(["definitely-not-a-real-binary-xyz", "--stdio"], timeout=5)
        with pytest.raises(McpError) as exc_info:
            c.start()
        assert "启动失败" in str(exc_info.value)

    def test_empty_command_rejected(self):
        with pytest.raises(McpError):
            McpStdioClient([], timeout=5)
