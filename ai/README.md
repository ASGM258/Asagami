# 动漫AI问答系统

一个基于 **FastAPI + LangGraph** 和 **DeepSeek API** 的智能动漫系统，提供流式问答、检查点会话持久化、**资讯智能体流水线**和数据翻译功能。

## 📋 项目简介

本项目是一个专为动漫爱好者设计的AI系统，能够：

- 智能回答用户的动漫相关问题
- 查询个人追番历史、观看统计等数据
- 提供动漫推荐和分析
- 管理多轮对话会话（基于 LangGraph 检查点）
- **自动抓取、翻译、摘要、审核动漫资讯**（LangGraph 智能体工作流）
- 翻译动漫名称、简介和角色信息

## 🚀 核心功能

### 1. 动漫AI问答
- ✅ 支持自然语言提问
- ✅ 流式输出响应（SSE，逐 token 呈现）
- ✅ 前置动漫相关性过滤
- ✅ 基于用户数据的个性化回答
- ✅ 多轮对话上下文由检查点自动恢复

### 2. 会话管理系统
- ✅ 创建和管理多个对话会话
- ✅ 对话状态持久化到 PostgreSQL（LangGraph 检查点）
- ✅ 更新会话标题
- ✅ 软删除 / 彻底删除会话

### 3. 资讯智能体工作流
- ✅ 抓取 agent：AniNewsAPI 为主源，不可用时自动降级到可配置 RSS 源
- ✅ 翻译 agent：英文资讯 → 中文
- ✅ 摘要 agent：生成摘要并**去除敏感信息**
- ✅ 审核 agent：判定可否发布，不通过自动回退摘要重做（最多 3 次）
- ✅ 超过 3 次未通过标记 `rejected` 并记录原因
- ✅ 数据落 MySQL，支持定时抓取与手动触发

### 4. RAG 知识库
- ✅ 上传 txt / md / pdf 知识文件（前端导航栏底部入口）
- ✅ Chroma 本地向量库，按文件指纹去重、重复上传覆盖而非追加
- ✅ Agent 自带 `search_knowledge_base` 工具，回答时引用文档并标注出处
- ✅ Embedding 可插拔：DashScope（推荐）/ 本地兜底（离线自测）

### 5. 数据翻译工具
- ✅ 动漫标题翻译（英文→中文）
- ✅ 动漫简介翻译
- ✅ 体裁标签翻译
- ✅ 角色名称/简介/昵称翻译

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **Web框架** | FastAPI + Uvicorn |
| **AI引擎** | LangChain 1.x + LangGraph 1.x |
| **对话持久化** | LangGraph 检查点（`AsyncPostgresSaver`） |
| **持久化数据库** | PostgreSQL 14+ |
| **业务数据源** | MySQL 8.0+（资讯表读写，动漫数据只读） |
| **向量库** | Chroma（本地持久化） |
| **Embedding** | 阿里云 DashScope text-embedding-v3（可插拔） |
| **大模型** | DeepSeek Chat |
| **资讯来源** | AniNewsAPI（主）+ 可配置 RSS（备用，支持多源） |
| **定时任务** | APScheduler |
| **跨域支持** | FastAPI CORSMiddleware |
| **流式传输** | Server-Sent Events (SSE) |

详细技术栈请查看 [技术架构说明](docs/技术架构说明.md)

## 📁 项目结构

```
ai/
├── app/                         # 应用主体
│   ├── main.py                  # FastAPI 入口与 lifespan 装配
│   ├── config.py                # 环境变量与 .env 加载
│   ├── dependencies.py          # 依赖注入
│   ├── api/                     # 路由层
│   │   ├── routes_chat.py       #   问答接口
│   │   ├── routes_sessions.py   #   会话接口
│   │   ├── routes_news.py       #   资讯接口
│   │   ├── routes_knowledge.py  #   知识库接口（RAG）
│   │   └── routes_health.py     #   健康检查与首页
│   ├── schemas/                 # Pydantic 请求/响应模型
│   ├── core/                    # 统一响应、异常、SSE 编码
│   ├── db/                      # 数据访问层
│   │   ├── postgres.py          #   PostgreSQL（元数据 + 连接池）
│   │   └── mysql.py             #   MySQL 只读业务查询
│   ├── services/                # 业务层
│   │   ├── chat_service.py      #   问答编排
│   │   └── session_service.py   #   会话与消息读取
│   ├── rag/                     # RAG 知识库
│   │   ├── embeddings.py        #   Embedding 提供方（DashScope/本地兜底）
│   │   ├── loaders.py           #   文档解析（txt/md/pdf）与分块
│   │   ├── store.py             #   Chroma 向量库读写与检索
│   │   ├── ingest.py            #   知识文件摄取编排
│   │   └── tools.py             #   Agent 知识库检索工具
│   ├── news/                    # 资讯智能体模块
│   │   ├── fetchers.py          #   抓取源适配（AniNewsAPI + RSS）与归一化
│   │   ├── nodes.py             #   四个 agent 节点（抓取/翻译/摘要/审核）
│   │   ├── graph.py             #   LangGraph 拓扑与审核重做路由
│   │   ├── state.py             #   工作流状态与条目归约器
│   │   ├── repository.py        #   资讯表读写与字段映射
│   │   ├── service.py           #   业务编排（运行工作流 + 查询接口）
│   │   ├── scheduler.py         #   定时抓取
│   │   └── llm.py               #   资讯各 agent 的模型工厂
│   ├── agent/                   # Agent 层
│   │   ├── graph.py             #   Agent 构建 + 消息ID中间件
│   │   ├── state.py             #   AgentState 定义
│   │   ├── checkpointer.py      #   PostgresSaver 装配
│   │   ├── prompts.py           #   系统提示词
│   │   ├── tools.py             #   7 个查询工具
│   │   └── filter.py            #   相关性前置过滤
│   └── utils/ids.py             # ID 与标题生成
├── tests/                       # pytest 测试（无需数据库）
├── translate/                   # 翻译脚本（独立模块）
│   ├── __init__.py
│   └── translate_anime_titles.py
├── docs/                        # 文档目录
│   ├── 技术架构说明.md
│   ├── 功能说明-动漫AI问答系统.md
│   ├── 功能说明-资讯系统.md
│   ├── 功能说明-会话管理系统.md
│   └── 功能说明-翻译工具.md
├── init_conversations.sql       # PostgreSQL 初始化脚本（会话 + 检查点）
├── init_news.sql                # MySQL 资讯表初始化脚本
├── requirements.txt             # Python依赖包
├── .env.example                 # 环境变量示例
└── start_server.bat             # Windows启动脚本
```

## ⚙️ 环境配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备数据库

**PostgreSQL**（会话元数据与对话状态）：

```bash
psql -U postgres -c "CREATE DATABASE anime_ai;"
```

表结构由服务启动时自动创建（`chat_sessions` 与 LangGraph 检查点表）；也可手工执行：

```bash
psql -U postgres -d anime_ai -f init_conversations.sql
```

**MySQL**（资讯表）：

```bash
mysql -u root -p backend_asagami < init_news.sql
```

资讯表同样会在服务启动时幂等创建。

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

主要配置项：

| 变量 | 说明 |
|------|------|
| `AI_DATABASE_URL` | PostgreSQL 连接串（**必填**） |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（**必填**） |
| `DB_HOST/PORT/USER/PASSWORD/NAME` | MySQL 业务库连接信息 |
| `FLASK_HOST/FLASK_PORT` | 监听地址与端口（沿用旧变量名） |
| `LLM_MODEL/LLM_TEMPERATURE/LLM_MAX_TOKENS` | 模型参数 |
| `ANINEWS_BASE_URL/ANINEWS_ENDPOINT` | AniNewsAPI 接入地址 |
| `NEWS_FALLBACK_RSS` | 备用 RSS 源（主源不可用时降级） |
| `NEWS_SCHEDULER_ENABLED/NEWS_SCHEDULER_CRON` | 资讯定时抓取 |
| `EMBEDDING_PROVIDER` | RAG 向量模型：`dashscope` / `local` |
| `DASHSCOPE_API_KEY` | 阿里云百炼密钥（RAG 必需，未配置会回退本地兜底） |
| `CHROMA_PERSIST_DIR/KNOWLEDGE_DIR` | 向量库与知识文件目录 |
| `RAG_CHUNK_SIZE/RAG_CHUNK_OVERLAP` | 文档分块参数 |
| `CORS_ORIGINS` | 允许跨域的来源 |
| `POSTGRES_POOL_MIN_SIZE/MAX_SIZE` | 连接池大小 |

## 🎯 快速开始

### 方式一：使用启动脚本（Windows）

```bash
start_server.bat
```

### 方式二：手动启动

```bash
# 推荐：使用启动器（Windows 上会自动处理事件循环兼容问题）
python run_server.py
```

> ⚠️ **Windows 上不要直接用 `uvicorn app.main:app` 启动**。
> psycopg 的异步连接池（`AsyncPostgresSaver` 依赖）**不支持 Windows 默认的
> ProactorEventLoop**，而 uvicorn 0.54 在 Windows 上硬编码使用它，会导致
> PostgreSQL 连不上 → 会话与流式问答整体不可用，日志表现为反复出现：
> `Psycopg cannot use the 'ProactorEventLoop' to run in async mode`。
> `run_server.py` 会强制 `SelectorEventLoop` 规避该问题。

服务启动后访问：

- 服务首页：http://localhost:5000
- 接口文档：http://localhost:5000/api/docs
- 健康检查：http://localhost:5000/api/health

## 📡 API接口

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/anime-chat` | POST | 动漫问答（非流式） |
| `/api/anime-chat-stream` | POST | 动漫问答（流式输出，推荐） |
| `/api/session/create` | POST | 创建新会话 |
| `/api/sessions` | GET | 获取会话列表 |
| `/api/session/{id}/messages` | GET | 获取会话消息 |
| `/api/session/{id}/title` | PUT | 更新会话标题 |
| `/api/session/{id}` | DELETE | 删除会话 |
| `/api/health` | GET | 健康检查 |
| `/api/news/list` | GET | 资讯列表（分页，供无限滚动） |
| `/api/news/detail` | POST | 资讯详情 |
| `/api/news/categories` | GET | 资讯分类 |
| `/api/news/refresh` | POST | 手动触发资讯抓取工作流 |
| `/api/knowledge/upload` | POST | 上传知识文件（multipart，txt/md/pdf） |
| `/api/knowledge/files` | GET | 已入库知识文件列表 |
| `/api/knowledge/files` | DELETE | 删除某个文件的知识 |
| `/api/knowledge/stats` | GET | 知识库统计 |

详细API文档请查看 [功能说明-动漫AI问答系统.md](docs/功能说明-动漫AI问答系统.md) 与 [功能说明-资讯系统.md](docs/功能说明-资讯系统.md)

### 请求示例

```json
POST /api/anime-chat-stream
{
  "question": "我的追番历史怎么样？",
  "user_id": 1,
  "session_id": "session_abc123"
}
```

### 响应示例（流式）

```
data: {"success": true, "chunk": "根据", "type": "content"}

data: {"success": true, "chunk": "您的记录", "type": "content"}

data: {"success": true, "chunk": "", "type": "end", "session_id": "session_abc123", "message_id": "msg_xyz789"}
```

## 🔧 翻译工具使用

`translate/` 是独立模块，自带 MySQL 连接配置，不依赖 `app` 包。

运行翻译脚本：

```bash
cd translate
python translate_anime_titles.py
```

按提示选择翻译模式：
1. 翻译动漫标题
2. 翻译动漫简介
3. 翻译动漫体裁
4. 翻译角色名称
5. 翻译角色简介
6. 翻译角色昵称

详细说明请查看 [功能说明-翻译工具.md](docs/功能说明-翻译工具.md)

## 🗄️ 数据库设计

### PostgreSQL（本服务所有）

| 表 | 内容 | 创建方式 |
|----|------|----------|
| `chat_sessions` | 会话元数据（标题、归属用户、软删除标记） | 启动时幂等创建 |
| `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` / `checkpoint_migrations` | LangGraph 检查点（对话状态与消息） | `PostgresSaver.setup()` 自动创建 |

### MySQL

| 表 | 归属 | 内容 |
|----|------|------|
| `news` | 本服务读写 | 动漫资讯（标题/摘要/正文/分类/状态/审核原因等） |
| `news_review_log` | 本服务读写 | 审核轨迹（每次判定与原因） |
| `anime` / `user_anime` / `anime_character` | Java 后端所有 | 本服务只读，供问答工具查询 |

## 🧪 测试

```bash
python -m pytest -q
```

测试使用 `InMemorySaver`、内存版会话存储与内存版资讯仓储，**无需任何数据库即可运行**。用例覆盖 SSE 编码、相关性过滤、ID 格式、会话与消息契约、检查点多轮记忆、HTTP 路由与错误码，以及资讯工作流的四节点流转、审核重做路由、敏感信息清洗与前端字段契约。

## 📰 资讯工作流

```
抓取 agent ──► 翻译 agent ──► 摘要 agent ──► 审核 agent
（AniNewsAPI/RSS）  （英文→中文）  （摘要+去敏感）   │
                                    ▲              │ 不通过且 <3 次
                                    └──────────────┘
                                                   │ 不通过且 ≥3 次
                                                   ▼
                                        status=rejected（记录原因）
```

手动触发：

```bash
curl -X POST "http://localhost:5000/api/news/refresh?limit=10"
```

开启定时抓取（`.env`）：

```
NEWS_SCHEDULER_ENABLED=True
NEWS_SCHEDULER_CRON=0 6 * * *
```

详见 [功能说明-资讯系统.md](docs/功能说明-资讯系统.md)。

## 📝 开发说明

### AI Agent工作流程

1. **问题接收** → 前端发送用户问题
2. **相关性检测** → 判断是否为动漫相关问题
3. **会话解析** → 校验或创建会话
4. **工具调用** → Agent 自动选择数据库查询工具
5. **数据分析** → 基于返回数据进行推理
6. **生成回答** → 组织语言并流式返回
7. **状态持久化** → 整轮对话写入 PostgreSQL 检查点

### 可用工具函数

- `get_user_anime_history`: 获取用户追番历史
- `get_user_watching_animes`: 获取用户正在观看的动漫
- `get_user_completed_animes`: 获取用户已完成的动漫及评分
- `get_user_favorite_genres`: 分析用户喜欢的类型
- `get_anime_info`: 查询动漫详细信息
- `search_anime_by_name`: 搜索动漫
- `get_user_watch_statistics`: 获取观看统计数据

## ⚠️ 注意事项

1. **API密钥安全**: 不要将 `.env` 文件提交到版本控制系统
2. **PostgreSQL 必需**: 未配置数据库时服务仍可启动，但会话相关接口不可用
3. **资讯需 MySQL**: 资讯表建在 MySQL，未配置时资讯接口返回 503
4. **AniNewsAPI 可用性**: 主源不可达时自动降级到 `NEWS_FALLBACK_RSS`
5. **跨域配置**: 生产环境建议指定具体域名而非使用 `*`
6. **速率限制**: DeepSeek API有调用频率限制，注意控制请求速度
7. **Nginx 代理**: 反向代理时必须 `proxy_buffering off`，否则 SSE 失去流式效果
8. **错误处理**: 所有API均返回统一格式的错误响应，错误码字符串不可随意改动

## 🐛 常见问题

### Q: 启动日志提示「PostgreSQL 初始化失败」？
A: 确认 PostgreSQL 已启动、`AI_DATABASE_URL` 正确、数据库已创建：

```bash
psql -U postgres -c "CREATE DATABASE anime_ai;"
```

### Q: 流式输出不工作？
A: 确保前端正确解析SSE格式；若经过 Nginx，检查是否关闭了缓冲（`proxy_buffering off`）。

### Q: 多轮对话没有上下文？
A: 检查请求是否传入了 `session_id`。会话记忆由 LangGraph 检查点按 `thread_id` 恢复，缺少 `session_id` 时每轮都是独立对话。

### Q: AI回答不准确？
A: 检查 MySQL 中是否有足够的用户数据，以及工具返回是否正常（查看日志）。

### Q: 翻译速度慢？
A: 翻译脚本默认每次请求间隔1秒，可根据API配额调整 `time.sleep()` 参数。

## 📄 许可证

本项目仅供学习和研究使用。

## 👥 贡献

欢迎提交Issue和Pull Request！

---

**最后更新**: 2026年10月
