<div align="center">

# 浅上小站

**二次元资讯聚合 + AI 问答平台**

Vue 3 · Spring Boot · FastAPI · LangGraph · RAG · MCP

</div>

---

## 项目简介

一个面向二次元爱好者的站点，从零独立完成前后端与 AI 服务。包含两块核心能力：

- **资讯**：多 Agent 流水线自动完成动画资讯的抓取、翻译、摘要与审核发布，无人值守也能持续更新。
- **问答**：基于 LangGraph 的对话 Agent，可调用站内数据、知识库检索与第三方 MCP 工具，逐字流式输出。

## 功能特性

| 模块 | 能力 |
|------|------|
| 资讯 | 四节点 Agent 流水线（抓取 → 翻译 → 摘要 → 审核），审核不通过自动回退重做；RSS 摘要自动回源补全正文 |
| AI 问答 | ReAct 式工具调用；会话记忆持久化到 PostgreSQL 检查点；长对话自动摘要压缩 |
| RAG | 向量 + BM25 混合召回，RRF 融合后重排；支持 txt / md / pdf / docx 上传 |
| MCP | 接入 `bilibili-cognitive-server`，把 B 站视频检索做成 Agent 工具 |
| 站点 | 当季新番、动漫详情、角色图鉴、追番历史、收藏、评论 |

## 架构

```
┌────────────┐   HTTP/SSE   ┌──────────────────┐        ┌──────────────┐
│  Vue 3     │ ───────────► │  AI 服务 (FastAPI)│ ─────► │  DeepSeek    │
│  前端 :5173│              │  LangGraph Agent  │        │  DashScope   │
└─────┬──────┘              │  RAG · MCP        │        └──────────────┘
      │                     └────────┬─────────┘
      │                              │
      │  REST                        ├──► PostgreSQL（会话与检查点）
      ▼                              ├──► Chroma（知识库向量）
┌──────────────────┐                 ├──► MySQL（业务数据，只读）
│ 业务后端 (Java)   │ ◄───────────────┘
│ Spring Boot :8081│ ─────────────► MySQL
└──────────────────┘
```

## 目录结构

```text
.
├── frontend/
│   └── frontended/      # Vue 3 + Vite + Element Plus
├── backend/             # Spring Boot + MyBatis + MySQL（Java 业务后端）
├── ai/                  # FastAPI + LangGraph（AI 服务、RAG、MCP）
├── .gitignore           # 仓库级忽略规则
└── README.md
```

各模块的详细说明、API 与设计文档见模块内 README：

- 前端 → [`frontend/frontended/README.md`](frontend/frontended/README.md)
- 业务后端 → [`backend/README.md`](backend/README.md)
- AI 服务 → [`ai/README.md`](ai/README.md)、设计文档在 [`ai/docs/`](ai/docs/)

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3、Vite 8、TypeScript、Element Plus、Pinia、Vue Router |
| 业务后端 | Java 17、Spring Boot 4、MyBatis、PageHelper、JJWT、MySQL 8 |
| AI 服务 | Python 3.13、FastAPI、LangChain、LangGraph、Uvicorn |
| 存储 | MySQL（业务）、PostgreSQL（会话与检查点）、Chroma（向量库） |
| 模型 | DeepSeek（对话）、DashScope `text-embedding-v3`（向量）、`gte-rerank-v2`（重排） |
| 外部集成 | MCP（`bilibili-cognitive-server`）、Jikan / AniList |

## 快速开始

### 0. 前置依赖

JDK 17+、Maven 3.9+、Python 3.11+、Node 20+、MySQL 8、PostgreSQL 14+

### 1. 数据库

业务库（MySQL `backend_asagami`）存放动漫、角色、追番等数据，归 Java 后端所有；
AI 服务**只读**它，另外自己维护两张表：

```bash
# AI 服务用到的 PostgreSQL（会话元数据 + LangGraph 检查点）
psql -U postgres -d anime_ai -f ai/init_conversations.sql

# AI 服务用到的 MySQL 资讯表（已发布/审核未通过 + 审核轨迹）
mysql -u root -p backend_asagami < ai/init_news.sql
```

> 两张表也都会在服务启动时**幂等自动创建**，上面的脚本仅用于手动初始化或查阅表结构。
> LangGraph 的检查点表由 `AsyncPostgresSaver.setup()` 在启动时自动建立。
> 业务库的历史数据迁移脚本见 `backend/migrate_character_anilist.sql`。

### 2. 业务后端

```bash
cd backend
mvn spring-boot:run          # 默认 http://localhost:8081
```

### 3. AI 服务

```bash
cd ai
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python run_server.py         # 默认 http://localhost:5000，接口文档 /api/docs
```

> ⚠️ **Windows 上不要用 `uvicorn app.main:app` 启动**。uvicorn 在 Windows 上强制使用
> `ProactorEventLoop`，与 psycopg 异步连接池不兼容，必须走 `run_server.py`（或 `start_server.bat`）。

可选：安装 MCP 服务（B 站视频推荐工具）

```bash
cd ai && setup_bilibili_mcp.bat
```

### 4. 前端

```bash
cd frontend/frontended
npm install
npm run dev                  # 默认 http://localhost:5173
```

## 配置

各模块通过 `.env` 配置，仓库内只提交 `*.env.example` 模板，**真实密钥不入库**。

| 文件 | 关键项 |
|------|--------|
| `ai/.env` | `DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`、`AI_DATABASE_URL`（PostgreSQL）、`DB_*`（MySQL，只读） |
| `backend/.env` | `DB_*`、`SERVER_PORT`、JWT 相关 |
| `frontend/frontended/.env` | `VITE_API_BASE_URL`（Java）、`VITE_PYTHON_API_URL`（AI） |

> AI 服务需要 **两个** 密钥：DeepSeek 负责对话，DashScope 负责 embedding 与重排
> （DeepSeek 没有 embedding 接口）。缺 `DASHSCOPE_API_KEY` 时会降级为本地哈希向量，
> 检索质量明显下降，仅适合离线自测。

## 测试

```bash
cd ai
.venv\Scripts\python -m pytest -q      # 357 passed
```

覆盖：LangGraph 工作流与路由、SSE 流式净化、RAG 混合检索与重排、MCP 协议客户端、
上下文摘要、新闻抓取与补全等。

## 已知限制

- 主抓取源 AniNewsAPI 不可用时自动降级到 RSS；RSS 只给摘要，需回源补全正文
- 检索依赖外网（embedding + 重排均为 API），离线场景会降级为本地哈希向量
- 重排使用百炼 API 而非本地模型；本地 `bge-reranker-v2-m3` 需额外 2.6 GB 的 torch 运行时
- 资讯抓取任务的互斥基于进程内锁，多实例部署需换成分布式锁

## 说明

本项目用于学习与个人实践。第三方数据（动画资料、资讯原文、B 站视频信息）版权归原权利人所有。
