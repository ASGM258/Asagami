"""
最小 MCP stdio 客户端

为什么要自己写：接入 MCP 的官方做法是装 `langchain-mcp-adapters` / `mcp` SDK，
但它们会把 `langchain-core`、`starlette`、`pydantic` 等一并升级，
与本项目已固定的 LangGraph / uvicorn 组合冲突（实测 dry-run 会拉
`langchain-core-1.6.12`）。因此这里只实现本项目实际用到的三个方法：

    initialize → tools/list → tools/call

协议要点（MCP over stdio）：
- 传输是「每行一个 JSON-RPC 2.0 消息」，UTF-8 编码
- 必须先发 `initialize` 请求，再发 `notifications/initialized` 通知
- 服务端可能随时插入没有 `id` 的通知（日志、进度），需要跳过
- `tools/call` 的结果在 `result.content`（text 数组）或 `result.structuredContent`

实现上用**常驻子进程 + 读取线程 + 队列超时**：Windows 的管道无法用 select 设超时，
所以把 stdout 的读取放到后台线程，主线程按请求 id 从队列取结果并带超时。
"""

import json
import logging
import queue
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: 客户端声明的 MCP 协议版本（服务端会回自己的版本，取交集由服务端决定）
PROTOCOL_VERSION = "2024-11-05"

#: 单行 JSON 的读取上限保护（防止异常服务端把内存打爆）
_MAX_LINE_BYTES = 8 * 1024 * 1024


class McpError(RuntimeError):
    """MCP 调用失败"""


@dataclass
class McpToolSpec:
    """服务端声明的工具"""

    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)


class McpStdioClient:
    """
    常驻的 MCP stdio 客户端

    用法：
        client = McpStdioClient(["bili-mcp", "--stdio"], env={...})
        client.start()
        tools = client.list_tools()
        text = client.call_tool("search_bilibili_videos", {"keyword": "斩服少女"})
        client.close()

    子进程异常退出后，下一次调用会自动重启并重新握手。
    """

    def __init__(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not command:
            raise McpError("MCP 启动命令为空")

        self._command = list(command)
        self._env = dict(env or {})
        self._timeout = float(timeout)

        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._responses: queue.Queue = queue.Queue()
        self._stderr_tail: deque = deque(maxlen=40)
        self._reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._next_id = 0
        self._initialized = False
        self._tools: list[McpToolSpec] = []

    # ==================== 生命周期 ====================

    @property
    def alive(self) -> bool:
        """子进程是否仍在运行"""
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        """启动子进程并完成 MCP 握手"""
        with self._lock:
            self._start_locked()

    def _start_locked(self) -> None:
        if self.alive:
            return

        logger.info("启动 MCP 服务: %s", " ".join(self._command))
        try:
            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env or None,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise McpError(f"MCP 服务启动失败: {exc}") from exc

        self._responses = queue.Queue()
        self._initialized = False
        self._tools = []
        self._start_readers()
        self._handshake_locked()

    def _start_readers(self) -> None:
        process = self._process
        assert process is not None and process.stdout is not None

        def read_stdout() -> None:
            try:
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    if len(line) > _MAX_LINE_BYTES:
                        logger.warning("MCP 单行响应超长，已跳过: %d 字节", len(line))
                        continue
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        # 有些服务端会把调试输出混进 stdout
                        logger.debug("MCP 非 JSON 输出: %s", line[:200])
                        continue
                    self._responses.put(message)
            except (ValueError, OSError):  # 进程被关闭时读管道会抛错
                pass
            finally:
                self._responses.put({"__eof__": True})

        def read_stderr() -> None:
            if process.stderr is None:
                return
            try:
                for line in process.stderr:
                    line = line.rstrip()
                    if line:
                        self._stderr_tail.append(line)
                        logger.debug("MCP stderr: %s", line)
            except (ValueError, OSError):
                pass

        self._reader = threading.Thread(target=read_stdout, name="mcp-stdout", daemon=True)
        self._stderr_reader = threading.Thread(
            target=read_stderr, name="mcp-stderr", daemon=True
        )
        self._reader.start()
        self._stderr_reader.start()

    def close(self) -> None:
        """关闭子进程"""
        process, self._process = self._process, None
        self._initialized = False
        if process is None:
            return

        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.terminate()
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            try:
                process.kill()
            except OSError:
                pass
        logger.info("MCP 服务已关闭")

    def __enter__(self) -> "McpStdioClient":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ==================== JSON-RPC ====================

    def _write(self, payload: dict) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise McpError("MCP 进程未启动")
        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, ValueError, OSError) as exc:
            raise McpError(f"MCP 写入失败: {exc}") from exc

    def _read_response(self, request_id: int, timeout: float) -> dict:
        """从响应队列里取指定 id 的消息，跳过通知与其他请求"""
        deadline_errors: list[str] = []
        while True:
            try:
                message = self._responses.get(timeout=timeout)
            except queue.Empty:
                raise McpError(
                    f"MCP 响应超时（{timeout:.0f}s）: {self._stderr_summary()}"
                ) from None

            if message.get("__eof__"):
                raise McpError(f"MCP 进程已退出: {self._stderr_summary()}")
            if message.get("id") != request_id:
                # 服务端通知（无 id）或过期响应，丢弃
                continue

            if "error" in message:
                error = message["error"] or {}
                raise McpError(
                    f"MCP 返回错误 {error.get('code')}: {error.get('message')}"
                )
            return message.get("result") or {}

    def request(self, method: str, params: dict | None = None) -> dict:
        """发送请求并等待响应"""
        if not self.alive:
            with self._lock:
                self._start_locked()

        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
            if params is not None:
                payload["params"] = params
            self._write(payload)
            return self._read_response(request_id, self._timeout)

    def notify(self, method: str, params: dict | None = None) -> None:
        """发送通知（不需要响应）"""
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def _stderr_summary(self) -> str:
        if not self._stderr_tail:
            return "(无 stderr 输出)"
        return " | ".join(list(self._stderr_tail)[-3:])

    # ==================== MCP 方法 ====================

    def _handshake_locked(self) -> None:
        self._next_id += 1
        request_id = self._next_id
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "anime-chat", "version": "1.0"},
                },
            }
        )
        result = self._read_response(request_id, self._timeout)
        server = result.get("serverInfo") or {}
        logger.info(
            "MCP 握手完成: server=%s %s, protocol=%s",
            server.get("name"),
            server.get("version"),
            result.get("protocolVersion"),
        )

        self.notify("notifications/initialized")
        self._initialized = True

    def list_tools(self, refresh: bool = False) -> list[McpToolSpec]:
        """列出服务端工具（结果缓存）"""
        if self._tools and not refresh:
            return list(self._tools)

        result = self.request("tools/list")
        tools = []
        for raw in result.get("tools") or []:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            tools.append(
                McpToolSpec(
                    name=str(raw["name"]),
                    description=str(raw.get("description") or ""),
                    input_schema=raw.get("inputSchema") or {},
                )
            )
        self._tools = tools
        logger.info("MCP 服务提供 %d 个工具: %s", len(tools), [t.name for t in tools])
        return list(tools)

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        """
        调用工具并返回文本结果

        Args:
            name: 工具名
            arguments: 参数字典

        Returns:
            文本化结果；服务端标记为错误时抛出 McpError
        """
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})

        text = _result_text(result)
        if result.get("isError"):
            raise McpError(f"MCP 工具 {name} 执行失败: {text[:300]}")
        return text


def _result_text(result: dict) -> str:
    """
    把 tools/call 的结果转成文本

    优先用 `structuredContent`（结构化），否则拼接 `content` 里的文本块。
    """
    structured = result.get("structuredContent")
    if structured:
        return json.dumps(structured, ensure_ascii=False, default=str)

    blocks = result.get("content") or []
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif block.get("type") == "resource":
            resource = block.get("resource") or {}
            if isinstance(resource.get("text"), str):
                parts.append(resource["text"])
    return "\n".join(parts).strip()
