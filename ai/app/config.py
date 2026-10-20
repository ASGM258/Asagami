"""
全局配置模块

所有可变配置集中于此，通过环境变量或 ai/.env 文件注入。
环境变量名与 Java 后端保持独立，避免相互污染。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ai/ 目录（.env 与本文件所在包的上级目录）
AI_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """AI 服务配置"""

    model_config = SettingsConfigDict(
        env_file=str(AI_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ==================== 服务 ====================
    service_name: str = "anime-ai-chat"
    service_version: str = "2.0.0"
    flask_host: str = "0.0.0.0"  # 兼容旧变量名，含义为监听地址
    flask_port: int = 5000  # 兼容旧变量名，含义为监听端口
    debug: bool = True

    # 允许跨域的来源
    cors_origins: str = "*"

    # ==================== DeepSeek / LLM ====================
    # ⚠️ 密钥只能来自环境变量 / .env（已 gitignore），绝不写默认值
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1000

    # ==================== PostgreSQL（会话元数据 + LangGraph 检查点） ====================
    # 形如 postgresql://user:password@host:5432/dbname
    ai_database_url: str = "postgresql://postgres:123456@localhost:5432/anime_ai"
    # 建立连接池的等待超时（秒），本机数据库通常毫秒级完成
    postgres_connect_timeout: int = 10
    # 跳过数据库初始化（仅测试使用）
    skip_db_init: bool = False
    # 连接池大小
    postgres_pool_min_size: int = 1
    postgres_pool_max_size: int = 10

    # ==================== MySQL（Java 后端所有的业务数据，只读） ====================
    # 同时兼容旧变量名 DB_* 与译名 MYSQL_*
    mysql_host: str = Field(
        "localhost", validation_alias=AliasChoices("DB_HOST", "MYSQL_HOST")
    )
    mysql_port: int = Field(
        3306, validation_alias=AliasChoices("DB_PORT", "MYSQL_PORT")
    )
    mysql_user: str = Field(
        "root", validation_alias=AliasChoices("DB_USER", "MYSQL_USER")
    )
    mysql_password: str = Field(
        "123456", validation_alias=AliasChoices("DB_PASSWORD", "MYSQL_PASSWORD")
    )
    mysql_database: str = Field(
        "backend_asagami", validation_alias=AliasChoices("DB_NAME", "MYSQL_DATABASE")
    )

    # ==================== 会话 ====================
    session_id_prefix: str = "session_"
    message_id_prefix: str = "msg_"
    id_length: int = 16
    default_session_title: str = "新会话"
    title_max_length: int = 20

    # ==================== 资讯抓取 ====================
    # AniNewsAPI 接入地址（可替换为自建代理）
    aninews_base_url: str = "https://aninews.vercel.app"
    aninews_endpoint: str = "/api/news"
    aninews_enabled: bool = True
    # 备用 RSS 源：AniNewsAPI 不可用时自动降级
    # 支持逗号分隔的**多个**地址：单个源条目有限（MyAnimeList news RSS 约 10 条），
    # 只配一个源会出现「抓完就没有新内容」。
    # 注意 Anime News Network 与 Crunchyroll 会返回 403，勿加。
    news_fallback_rss: str = (
        "https://myanimelist.net/rss/news.xml,"
        "https://animecorner.me/feed/"
    )
    # 抓取超时（秒）与单次抓取条数上限
    news_fetch_timeout: int = 20
    news_fetch_limit: int = 20
    # 抓取放大倍数：已入库的条目会被跳过，故按目标条数放大抓取量，
    # 才能在来源（尤其 RSS）重复返回同一批条目时仍拿到新内容
    news_fetch_over_fetch: int = 3

    # ==================== 资讯正文补全 ====================
    # RSS 源只给摘要（MyAnimeList 约 500 字、Anime Corner 约 100 字，
    # 且都在词中间被硬截断），因此需要回到详情页抓全文。
    news_enrich_enabled: bool = True
    # 单次运行最多补全多少条（每条一次 HTTP 请求）
    news_enrich_limit: int = 20
    # 单条补全的超时（秒）与请求间隔（秒，避免被站点限流）
    news_enrich_timeout: int = 15
    news_enrich_delay: float = 0.3
    # 正文短于该字符数视为残缺，需要补全
    news_enrich_min_chars: int = 600
    # 定时任务：是否启用与执行周期（cron 表达式，默认每天 6 点）
    news_scheduler_enabled: bool = False
    news_scheduler_cron: str = "0 6 * * *"

    # ==================== 资讯各 agent 温度 ====================
    # 翻译偏稳定、摘要允许一定创造性、审核需要最稳定
    llm_translate_temperature: float = 0.3
    llm_summary_temperature: float = 0.5
    llm_review_temperature: float = 0.0
    # 翻译节点的输出上限：整篇正文要一起输出，1000 tokens 会把译文截断
    news_llm_max_tokens: int = 4000
    # 翻译节点的输入上限（字符）：超过则按句子边界截断，避免超出模型窗口
    news_translate_input_limit: int = 12000

    # ==================== MCP：B站认知服务 ====================
    # 通过 stdio 拉起 bilibili-cognitive-server（装在独立 venv，不污染主环境）
    # 安装：python -m venv .venv-mcp 后在该 venv 内 pip install bilibili-cognitive-server
    bilibili_mcp_enabled: bool = True
    # 留空则自动探测 ai/.venv-mcp/Scripts/bili-mcp.exe 或 PATH 中的 bili-mcp
    bilibili_mcp_command: str = ""
    bilibili_mcp_timeout: float = 30.0
    # 为排序补取多少个视频的点赞/收藏等详情（每个一次 MCP 调用）
    bilibili_detail_limit: int = 10
    # B站 Cookie：搜索接口匿名可用；「我的信息」「字幕」等工具需要登录态
    bili_sessdata: str = ""
    bili_bili_jct: str = ""
    bili_buvid3: str = ""

    # ==================== 上下文压缩 ====================
    # 会话过长时自动摘要旧消息，避免超出模型上下文窗口
    context_summarization_enabled: bool = True
    # 触发阈值：消息数 或 估算 token 数（任一满足即触发；设为 0 关闭该项）
    context_trigger_messages: int = 30
    context_trigger_tokens: int = 24000
    # 压缩后完整保留的最近消息条数
    context_keep_messages: int = 8

    # ==================== RAG 知识库 ====================
    # Embedding 提供方：dashscope（阿里云百炼，需 key）| local（本地兜底，仅自测）
    embedding_provider: str = "dashscope"
    embedding_model: str = "text-embedding-v3"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 向量库与原始文件目录（默认落在 ai/ 下，随应用一起备份）
    chroma_persist_dir: str = str(AI_ROOT / "chroma_db")
    knowledge_dir: str = str(AI_ROOT / "knowledge")
    # 分块参数（字符数）
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 80
    # 单次上传大小上限（MB）
    rag_max_file_size_mb: int = 10

    # ==================== RAG 混合检索 ====================
    # 向量检索对专有名词（角色名/作品名）天生弱，因此并一路 BM25 关键词检索，
    # 两路结果用 RRF 融合（只看名次，不需要对齐分数尺度）
    rag_bm25_enabled: bool = True
    # 两路各自的融合权重（等权即标准 RRF）
    rag_bm25_weight: float = 1.0
    rag_vector_weight: float = 1.0
    # RRF 平滑常数，越小越突出头部名次
    rag_rrf_k: int = 60
    # 每路先取多少个候选、融合后留多少个送去重排
    rag_candidate_pool: int = 20
    # 实测 gte-rerank-v2 一次最多 8 条走一个批次（约 320ms），
    # 超过 8 条内部拆批、耗时跳到 1.2s 左右，因此默认 8
    rag_pre_rerank_k: int = 8

    # ==================== RAG 重排（百炼 text-rerank） ====================
    rag_rerank_enabled: bool = True
    # 注意：gte-rerank 在新账号上会 403，必须用 v2
    rag_rerank_model: str = "gte-rerank-v2"
    rag_rerank_timeout: int = 15

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的 CORS 配置解析为列表"""
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
