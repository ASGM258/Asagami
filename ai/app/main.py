"""
FastAPI 应用入口

装配顺序（lifespan）：
    1. MySQL 客户端（资讯与业务数据只读）
    2. RAG 知识库（本地 Chroma）
    3. PostgreSQL 同步池（会话元数据）+ AsyncPostgresSaver 异步池（检查点）
    4. Agent（绑定检查点）与业务服务

启动方式：
    uvicorn app.main:app --host 0.0.0.0 --port 5000
    或直接运行本文件：python -m app.main
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ==================== Windows 事件循环策略（必须在创建循环前设置） ====================
# psycopg 的异步连接池（AsyncPostgresSaver 依赖它）**不支持 ProactorEventLoop**，
# 而 Windows 上 asyncio 默认就是 ProactorEventLoop。症状是启动日志反复出现：
#     Psycopg cannot use the 'ProactorEventLoop' to run in async mode
# 最终 PostgreSQL 连接超时 → 会话与流式问答全部不可用。
#
# 注意：uvicorn 的 `--loop asyncio` 在 Windows 上走的仍是 ProactorEventLoop，
# 因此必须在这里直接设置**事件循环策略**，uvicorn 创建循环时才会拿到 Selector。
# 该设置在模块导入时执行，早于 lifespan 中创建连接池，因此生效。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.agent.checkpointer import (
    close_checkpointer_factory,
    init_checkpointer_factory,
)
from app.agent.graph import init_agent_factory
from app.api import (
    routes_chat,
    routes_health,
    routes_knowledge,
    routes_news,
    routes_sessions,
)
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.mysql import init_mysql_client
from app.db.postgres import close_postgres_store, init_postgres_store
from app.mcp.bilibili import resolve_command, shutdown_bilibili_service
from app.news.scheduler import shutdown_news_scheduler, start_news_scheduler
from app.news.service import init_news_service
from app.services.chat_service import ChatService
from app.services.session_service import SessionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时装配资源，关闭时释放连接池"""
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("动漫AI问答API服务启动: %s", settings.service_name)
    logger.info("=" * 60)

    # 1) MySQL 业务数据客户端（只读，供工具查询动漫数据）
    init_mysql_client(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
    )
    logger.info(
        "MySQL 业务数据客户端已就绪: %s:%s/%s",
        settings.mysql_host,
        settings.mysql_port,
        settings.mysql_database,
    )

    # 2) 资讯模块（表结构 + 工作流 + 定时任务）
    try:
        from app.news.service import NewsService

        NewsService.ensure_schema()
        news_service = init_news_service(settings)
        app.state.news_service = news_service
        logger.info("资讯模块已就绪（news / news_review_log）")

        start_news_scheduler(settings, lambda: news_service.run_workflow())
    except Exception as exc:  # noqa: BLE001 - 资讯不可用不影响问答功能
        logger.error("资讯模块初始化失败，资讯接口将不可用: %s", exc)
        app.state.news_service = None

    # 3) RAG 知识库（本地 Chroma，不依赖外部数据库）
    try:
        from app.rag.ingest import KnowledgeIngestService
        from app.rag.store import init_knowledge_store

        knowledge_store = init_knowledge_store(settings)
        knowledge_service = KnowledgeIngestService(settings, knowledge_store)
        app.state.knowledge_service = knowledge_service

        provider = knowledge_store.embeddings
        logger.info(
            "RAG 知识库已就绪: provider=%s(语义模型=%s), 现有块数=%d, 目录=%s",
            provider.name,
            provider.semantic,
            knowledge_store.count(),
            settings.chroma_persist_dir,
        )
        if not provider.semantic:
            logger.warning(
                "当前使用本地兜底 embedding，检索仅相当于词面匹配；"
                "请在 .env 配置 DASHSCOPE_API_KEY 以获得真正的语义检索"
            )
    except Exception as exc:  # noqa: BLE001 - 知识库不可用不影响问答
        logger.error("RAG 知识库初始化失败，知识库接口将不可用: %s", exc)
        app.state.knowledge_service = None

    # 2) PostgreSQL（会话元数据 + LangGraph 检查点）
    if settings.skip_db_init:
        logger.warning("已跳过数据库初始化（SKIP_DB_INIT=true），仅供测试使用")
        app.state.postgres_store = None
        app.state.session_service = None
        app.state.chat_service = None
    else:
        try:
            # 同步连接池：会话元数据表（chat_sessions）的读写
            store = init_postgres_store(
                settings.ai_database_url,
                min_size=settings.postgres_pool_min_size,
                max_size=settings.postgres_pool_max_size,
                connect_timeout=settings.postgres_connect_timeout,
            )

            # 异步检查点：AsyncPostgresSaver 自建异步连接池
            # （同步 PostgresSaver 的异步接口未实现，会让 astream/aget_state 直接报错）
            checkpointer_factory = init_checkpointer_factory(
                database_url=settings.ai_database_url,
                min_size=settings.postgres_pool_min_size,
                max_size=settings.postgres_pool_max_size,
                connect_timeout=settings.postgres_connect_timeout,
            )
            checkpointer = await checkpointer_factory.open()

            # 3) Agent 与业务服务
            agent_factory = init_agent_factory(settings)
            agent_factory.build(checkpointer)

            session_service = SessionService(store, agent_factory, settings)
            chat_service = ChatService(store, agent_factory, session_service)

            app.state.postgres_store = store
            app.state.session_service = session_service
            app.state.chat_service = chat_service
            logger.info("会话与检查点服务已就绪")
        except Exception as exc:  # noqa: BLE001 - 允许无数据库启动以便排查配置
            logger.error("PostgreSQL 初始化失败，会话相关接口将不可用: %s", exc)
            logger.error(
                "请检查 AI_DATABASE_URL 配置，并确认 PostgreSQL 已启动且库已创建"
            )
            app.state.postgres_store = None
            app.state.session_service = None
            app.state.chat_service = None

    logger.info("服务地址: http://%s:%s", settings.flask_host, settings.flask_port)
    logger.info("接口文档: http://%s:%s/api/docs", settings.flask_host, settings.flask_port)

    # B站 MCP：只在真正调用工具时才拉起子进程，这里仅报告可用性
    if settings.bilibili_mcp_enabled:
        mcp_command = resolve_command(settings)
        if mcp_command:
            logger.info("B站 MCP 服务: %s", " ".join(mcp_command))
        else:
            logger.warning(
                "未找到 bili-mcp，视频推荐工具不可用。安装方式见 ai/README.md 的 MCP 章节"
            )
    logger.info("=" * 60)

    yield

    shutdown_news_scheduler()
    # MCP 子进程（bili-mcp）随应用退出一起回收，避免留下孤儿进程
    shutdown_bilibili_service()
    await close_checkpointer_factory()
    close_postgres_store()
    logger.info("动漫AI问答API服务已关闭")


def create_app() -> FastAPI:
    """构造 FastAPI 应用"""
    settings = get_settings()

    app = FastAPI(
        title="动漫AI问答系统",
        description="基于 FastAPI + LangGraph 检查点的动漫AI问答服务",
        version=settings.service_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS：凭据用 JWT 头传递，不使用 Cookie，
    # 因此 allow_credentials=False —— 与 allow_origins=["*"] 搭配才合法
    # （浏览器禁止 Access-Control-Allow-Origin: * 与凭据同时生效）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=3600,
    )

    register_exception_handlers(app)

    app.include_router(routes_health.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_sessions.router)
    app.include_router(routes_news.router)
    app.include_router(routes_knowledge.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()

    # 事件循环策略已在模块顶部设置（Windows 用 SelectorEventLoop），
    # 这里无需再传 loop 参数。
    uvicorn.run(
        "app.main:app",
        host=_settings.flask_host,
        port=_settings.flask_port,
        reload=_settings.debug,
    )
