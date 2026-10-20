"""
服务启动器

为什么需要单独一个入口，而不直接 `uvicorn app.main:app`：

    Windows 上 psycopg 的**异步**连接池（AsyncPostgresSaver 依赖它）不支持
    ProactorEventLoop，而 uvicorn 0.54 在 Windows 上**硬编码**返回它：

        # uvicorn/loops/asyncio.py
        def asyncio_loop_factory(use_subprocess=False):
            if sys.platform == "win32" and not use_subprocess:
                return asyncio.ProactorEventLoop
            return asyncio.SelectorEventLoop

    症状：启动日志反复出现
        Psycopg cannot use the 'ProactorEventLoop' to run in async mode
    最终 PostgreSQL 连接超时 → 会话与流式问答全部不可用。

    注意：`--loop asyncio` 没用（走的还是这个工厂），
    在 app/main.py 里 set_event_loop_policy 也没用（uvicorn 不查策略）。
    因此这里直接**接管 uvicorn 的循环工厂**，强制 SelectorEventLoop。

启动：
    python run_server.py
    （或直接双击 start_server.bat）
"""

import asyncio
import os
import sys

if sys.platform == "win32":
    # 双保险：策略 + 直接接管 uvicorn 的循环工厂
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn.loops.asyncio as _uvicorn_asyncio
    import uvicorn.loops.auto as _uvicorn_auto

    def _selector_loop_factory(use_subprocess: bool = False):
        """始终返回 SelectorEventLoop（兼容 psycopg 异步池）"""
        return asyncio.SelectorEventLoop

    _uvicorn_asyncio.asyncio_loop_factory = _selector_loop_factory
    # auto 模块在导入时可能已绑定旧引用，这里一并替换
    _uvicorn_auto.asyncio_loop_factory = _selector_loop_factory

import uvicorn  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    settings = get_settings()

    host = os.getenv("FLASK_HOST", settings.flask_host)
    port = int(os.getenv("FLASK_PORT", settings.flask_port))

    # reload 模式会让 uvicorn 起子进程（use_subprocess=True，循环工厂失效），
    # 因此默认关闭，保证事件循环一定是 Selector。
    reload_enabled = os.getenv("SERVER_RELOAD", "false").lower() in ("1", "true", "yes")

    print("=" * 60)
    print("  动漫AI问答服务 (FastAPI)")
    print("=" * 60)
    print(f"  监听地址 : http://{host}:{port}")
    print(f"  接口文档 : http://{host}:{port}/api/docs")
    print(f"  热重载   : {'开（注意：此时改用 uvicorn 默认事件循环）' if reload_enabled else '关'}")
    print("=" * 60)

    if reload_enabled:
        # reload 必须用 import 字符串，uvicorn 会另起子进程
        uvicorn.run("app.main:app", host=host, port=port, reload=True)
    else:
        # 传已导入的 app 对象，uvicorn 不另起进程，事件循环沿用上面的工厂
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
