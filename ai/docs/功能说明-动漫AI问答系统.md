# 动漫AI问答系统功能说明

## 📖 概述

动漫AI问答系统是本项目的核心功能，基于 LangChain + LangGraph 与 DeepSeek 大语言模型实现智能对话能力。系统能够理解用户的自然语言问题，自动调用数据库查询工具获取相关数据，并生成准确、个性化的回答。

当前实现要点：

- **Web 框架**：FastAPI（原 Flask）
- **Agent 编排**：`langchain.agents.create_agent` + LangGraph
- **对话记忆**：LangGraph PostgreSQL 检查点，多轮上下文自动恢复
- **消息模型**：统一使用 LangChain 消息类（`HumanMessage` / `AIMessage` / `ToolMessage`）
- **业务数据**：MySQL 只读（`anime` / `user_anime` 归 Java 后端所有）

## ✨ 核心特性

### 1. 智能问答能力
- **自然语言理解**：支持用户用日常语言表达问题
- **上下文感知**：`user_id` 随状态注入，工具据此查询个人数据
- **多轮对话**：由检查点自动记忆，无需手工拼装历史
- **相关性过滤**：前置关键词过滤，自动识别并拒绝非动漫相关问题

### 2. 流式输出
- **实时响应**：采用 Server-Sent Events (SSE)
- **逐 token 呈现**：使用 `stream_mode="messages"`，文字逐字显示
- **契约不变**：事件字段与重构前完全一致

### 3. 数据安全
- **隐私保护**：不在回答中泄露敏感信息
- **数据隔离**：基于 `user_id` 的数据隔离
- **软删除机制**：会话删除可恢复

## 🔌 API接口详解

### 1. 动漫问答（非流式）

**接口地址**：`POST /api/anime-chat`

**请求参数**：

```json
{
  "question": "string, 必填 - 用户的问题",
  "user_id": "integer, 可选 - 用户ID",
  "session_id": "string, 可选 - 会话ID，继续已有对话时传入"
}
```

**响应格式**：

```json
{
  "success": true,
  "message": "问答成功",
  "timestamp": 1720540800.123,
  "data": {
    "answer": "AI的回答内容",
    "is_anime_related": true,
    "user_id": 1,
    "session_id": "session_a1b2c3d4e5f6g7h8",
    "message_id": "msg_1a2b3c4d5e6f7g8h"
  }
}
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| `answer` | AI 回答文本 |
| `is_anime_related` | 是否为动漫相关问题 |
| `user_id` | 生效的用户ID |
| `session_id` | 本轮的会话ID；未登录（无 `user_id`）时为 `null` |
| `message_id` | 本条 AI 回答的消息ID |

**非动漫相关问题的响应**：

```json
{
  "success": true,
  "message": "非动漫相关问题",
  "timestamp": 1720540800.123,
  "data": {
    "answer": "抱歉，我只能回答与动漫相关的问题哦！……",
    "is_anime_related": false,
    "user_id": 1,
    "session_id": null,
    "message_id": null
  }
}
```

**错误响应**：

```json
{
  "success": false,
  "error": {
    "message": "问题不能为空",
    "code": "EMPTY_QUESTION",
    "timestamp": 1720540800.123
  }
}
```

---

### 2. 动漫问答（流式输出）⭐推荐

**接口地址**：`POST /api/anime-chat-stream`

**请求参数**：同非流式。

**响应格式**：SSE 流（`text/event-stream`）

```
data: {"success": true, "chunk": "根据", "type": "content"}

data: {"success": true, "chunk": "您的记录", "type": "content"}

data: {"success": true, "chunk": "", "type": "end", "session_id": "session_a1b2c3d4e5f6g7h8", "message_id": "msg_1a2b3c4d5e6f7g8h"}
```

**事件类型**：

| `type` | 说明 |
|--------|------|
| `content` | 文本片段，前端累加渲染。**包含工具调用前的过渡语**（如「我来查询一下你的记录」） |
| `thinking` | 进度提示，`stage=thinking`（等待模型续写）/ `stage=reasoning`（模型在产出思维链）/ `stage=tool`（正在调用工具，带 `tool` 名称），不携带正文 |
| `retract` | 兼容保留，**当前不再发出**（过渡语已直接展示，无需撤回） |
| `end` | 传输完成，携带 `session_id` 与 `message_id` |
| `error` | 出错或非动漫问题 |

> `thinking` 事件示例：
>
> ```
> data: {"success": true, "chunk": "", "type": "thinking", "stage": "tool", "tool": "get_user_watching_animes"}
> ```
>
> 前端只需据此显示「正在查询你的追番记录…」这类中转圈提示，**不要**把 `chunk` 追加到回答里。

**非动漫相关问题的流式响应**：

```
data: {"success": false, "error": "非动漫相关问题", "chunk": "抱歉，我只能回答与动漫相关的问题哦！……", "type": "error", "is_anime_related": false}
```

> 前端据此判断 `is_anime_related === false`，走友好提示而非异常流程。

**异常时的流式响应**：

```
data: {"success": false, "error": "服务器内部错误: ...", "chunk": "抱歉，处理您的问题时出现了错误，请稍后重试。", "type": "error"}
```

**响应头**：

| 头 | 值 |
|----|----|
| `Content-Type` | `text/event-stream` |
| `Cache-Control` | `no-cache` |
| `X-Accel-Buffering` | `no` |
| `Connection` | `keep-alive` |

---

### 3. 健康检查

**接口地址**：`GET /api/health`

```json
{
  "status": "healthy",
  "service": "anime-ai-chat",
  "timestamp": 1720540800.123
}
```

---

### 4. API首页

**接口地址**：`GET /`

返回服务信息、全部接口清单与请求示例。

---

### 5. 接口文档

FastAPI 自动生成：

- Swagger UI：`GET /api/docs`
- ReDoc：`GET /api/redoc`
- OpenAPI JSON：`GET /api/openapi.json`

> 注意：文档挂载在 `/api/docs`，避免与仓库中的 `docs/` 文档目录混淆。

## 🧠 AI Agent工作机制

### 工作流程图

```
用户问题
    ↓
is_anime_related_question()  相关性前置过滤
    ↓ 通过
_resolve_session()
    ├─ 有 session_id → 校验存在性，user_id 取元数据表
    ├─ 有 user_id    → 创建会话（标题=问题前20字）
    └─ 都没有        → 瞬时线程，不落库
    ↓
构造 AgentState
    messages = [HumanMessage(content=问题)]
    user_id  = 生效用户ID
    ↓
create_agent 图执行（ReAct 循环）
    ├─ SummarizationMiddleware 判断历史是否过长 → 压缩为摘要
    ├─ 模型推理
    ├─ 需要数据 → 调用 @tool 查询 MySQL / 知识库
    └─ 迭代直至得出最终回答
    ↓
对话状态写入 PostgreSQL 检查点（thread_id = session_id）
    ↓
MessageIdMiddleware 为 AI 回答补写 message_id
    ↓
AnswerStreamFilter 净化：正文（含过渡语）放行，
                     工具原始数据与 reasoning 挡掉，工具调用转成提示事件
    ↓
产出 SSE 事件 / 返回 JSON
```

### ReAct模式说明

Agent 采用「推理—行动」循环：

1. **推理（Reason）**：分析用户问题，判断是否需要外部数据
2. **行动（Act）**：调用相应工具（如查询追番历史）
3. **观察（Observe）**：读取工具返回的 JSON 结果
4. **迭代**：必要时重复上述步骤
5. **产出**：组织语言生成最终回答

### 可用工具函数

| 工具 | 功能 | 数据来源 |
|------|------|----------|
| `get_user_anime_history` | 获取完整追番历史 | MySQL `user_anime` + `anime` |
| `get_user_watching_animes` | 获取正在观看的动漫 | MySQL |
| `get_user_completed_animes` | 获取已完成动漫及评分 | MySQL |
| `get_user_favorite_genres` | 分析偏好的动漫类型 | MySQL |
| `get_anime_info` | 查询动漫详细信息 | MySQL `anime` |
| `search_anime_by_name` | 按名称搜索动漫 | MySQL `anime` |
| `get_user_watch_statistics` | 获取观看统计数据 | MySQL `user_anime` |
| `recommend_bilibili_videos` | 搜索并推荐 B 站视频（返回可点击链接） | **MCP 服务** `bilibili-cognitive-server` |

> 工具 SQL 全部使用参数化查询，且均为单次查询（无 N+1）。

### 知识库清单注入（避免"我不知道"）

**问题**：用户问「绫弥一条」，模型不认识这个名字，直接回答"没有相关资料"；
用户提醒"RAG 里有"，它才去检索。

**根因**：模型不知道知识库里有什么。原来的 prompt 只说"当问题可能涉及站内已上传的
文档时先检索"，这要求模型自己判断相关性，但它手里没有清单，判断不了就只能放弃。

**做法**：`KnowledgeHintMiddleware`（`app/agent/knowledge.py`）在**每轮开头**
把当前知识库清单作为一条 SystemMessage 注入：

```
【站内知识库】当前已上传 2 个文件（3 个片段）：绫弥一条简介.txt、rag_test.txt
使用规则：
1. 用户问到任何具体角色名、作品名、人名、术语、设定时，必须先调用
   search_knowledge_base 检索，再基于检索结果回答。
2. 文件名里包含哪个关键词，就说明站内大概率有该资料 —— 尤其当用户提到的
   名字与某个文件名重合时，必须检索。
3. 未检索之前，不允许回答「没有相关资料」或「知识库中没有」；只有检索结果
   为空时才可以这么说，并明确告知「站内知识库未收录，以下内容来自通用知识」。
4. 引用站内资料时标明出处文件名。
```

有了文件名，「绫弥一条」与「绫弥一条简介.txt」对得上，模型自然会去搜。

三个实现细节：

| 关注点 | 做法 |
|--------|------|
| 不重复注入 | 只在**最后一条消息是 HumanMessage** 时注入；工具调用后的续写不再注入 |
| 不堆积 | 使用固定 message id（`knowledge-inventory-hint`），下一轮由 `add_messages` 原地替换 |
| 不泄漏 | 注入消息带 `lc_source="knowledge-hint"`，历史接口与流式过滤器都会挡掉 |

`KnowledgeStore.list_sources()` 带缓存（上传/删除时失效），避免每轮都扫全库元数据。

### MCP 集成：B 站视频推荐

`recommend_bilibili_videos` 不是本地函数，而是通过 **MCP（Model Context Protocol）**
调用独立的 `bilibili-cognitive-server` 进程拿数据。

**为什么用 MCP 而不是直接写 HTTP 请求**：B 站接口需要 wbi 签名、风控处理、
Cookie 管理与限流，这些都在 MCP 服务里实现好了；本项目只做集成，不重复造轮子。

**接入方式：本地 pip install + stdio**

该服务基于 FastMCP，`main()` 支持 stdio 与 SSE 两种传输。我们选 **stdio**：

| 维度 | stdio（采用） | SSE（未采用） |
|------|--------------|--------------|
| 生命周期 | 应用按需拉起子进程，退出时回收 | 需要常驻端口与服务管理 |
| 部署 | 无需开端口，无跨域/鉴权问题 | 需额外端口与健康检查 |
| 隔离 | 独立 venv，依赖不进入主环境 | 同左，但多一层网络 |

**关键决定：服务端装在独立 venv `ai/.venv-mcp`**。原因是它的依赖很重
（`fastmcp`、`faster-whisper`、`ctranslate2`、`onnxruntime`、`redis` 等），
直接装进主环境会升级 `langchain-core`/`starlette`，破坏现有 LangGraph 组合。
主环境侧因此**不新增任何第三方依赖** —— `app/mcp/stdio_client.py` 是一个
手写的最小 MCP 客户端（JSON-RPC over stdio，只实现 initialize / tools/list / tools/call）。

**安装**：

```bash
cd ai
setup_bilibili_mcp.bat        # 或手动：
python -m venv .venv-mcp
.venv-mcp\Scripts\pip install --no-deps bilibili-cognitive-server
.venv-mcp\Scripts\pip install fastmcp httpx pydantic pydantic-settings loguru redis protobuf
```

> 故意跳过 `faster-whisper`（ASR 语音转录，数百 MB）。视频推荐不需要它，
> 只有「字幕/转录」类工具会受影响。

**排序策略**（用户诉求：按播放量、点赞数等综合考虑）
搜索接口只返回播放量与弹幕数，点赞/收藏/投币要再查一次视频详情。因此：

1. 先按 `ps = limit×4`（上限 50）搜索候选池，按 bvid 去重
2. 只对播放量最高的前 `BILIBILI_DETAIL_LIMIT`（默认 10）条补详情，控制调用次数
3. 用加权分排序：

   ```
   score = 播放×1 + 点赞×10 + 收藏×8 + 投币×6 + 弹幕×3 + 评论×2
   ```

   点赞/收藏/投币是主动行为，权重高于纯播放
4. 返回 `https://www.bilibili.com/video/{bvid}` 链接与全部原始数值，
   让模型能解释推荐理由，而不是给一个黑箱分数

**system prompt 约束**：拿到结果后必须把标题、UP主、播放/点赞、时长和 **url 原样输出**，
方便用户点击跳转；不允许只给标题或改写链接。

### System Prompt设计

`app/agent/prompts.py` 中的 `SYSTEM_PROMPT` 约束了模型行为：

- 仅回答动漫相关问题
- 需要用户数据时必须调用工具，不得编造
- 回答风格：简洁分段、少用 emoji、专业友好
- 工具返回为空或出错时如实告知
- 不在回答中泄露敏感信息

### 上下文注入

`user_id` 通过 `AgentState` 注入并随检查点持久化，工具调用时由模型传入。相比旧版把 `用户ID为{user_id}，问题：{question}` 硬拼进用户消息正文，这样做的收益是：

- 用户消息保持原文，历史回显干净
- 多轮对话中 `user_id` 稳定可查

## 🧹 回答净化与上下文压缩

### 1. 展示策略：过渡语照常输出，只挡住工具原始数据与 reasoning

`stream_mode="messages"` 会把**图上所有节点**的消息块都吐出来，其中三类东西需要区别对待：

| 流出内容 | 处理 |
|----------|------|
| `ToolMessage`（工具返回的原始 JSON） | ❌ 绝不外发（内部数据） |
| 带 `tool_calls` 的 `AIMessage` 正文（「我来查询一下你的记录。」） | ✅ **照常输出**，这是正常对话内容 |
| reasoning（思维链） | ❌ 绝不进入正文，仅用于「正在思考」提示 |
| 其余 `AIMessage` 正文 | ✅ 逐块流式输出 |

过滤逻辑集中在 `app/services/stream_filter.py`：

| 组件 | 职责 |
|------|------|
| `AnswerStreamFilter` | 逐 chunk 产出 `content` / `thinking` / `tool` 事件 |
| `split_content()` | 把消息拆成 (可展示正文, reasoning) |
| `message_answer_text()` | 单条消息的可展示正文，供历史接口复用 |
| `final_answer_from_messages()` | 非流式路径按同一规则拼接全部正文 |

判定规则：

```
收到 ToolMessage          → 不外发内容，改发 thinking（工具执行完，等模型续写）
AIMessage 带 reasoning    → 不发正文，step 内首次出现时发 thinking(stage=reasoning)
AIMessage 有正文          → 立即发 content（不论是否带 tool_calls）
AIMessage 带 tool_calls   → 额外发 tool 事件（带工具名），前端转圈
```

**这里没有撤回、也没有缓冲**：过渡语发出去就留在气泡里，工具调用提示叠加在下面，模型续写的新正文继续往同一个气泡追加。多轮工具调用就转多次圈。

#### 内部维护调用必须单独挡掉

`stream_mode="messages"` 会把图上**所有**模型调用的产出都流出来，包括
`SummarizationMiddleware` 为压缩上下文而发起的**摘要调用**。它的输出是给模型看的
内部笔记（"用户问过什么 / 有什么未完成"），一旦漏到前端，用户就会看到一段
莫名其妙的"总结"直接拼在回答前面。

因此 `is_internal_chunk(metadata)` 会先过滤这类 chunk，判据（均来自 LangGraph 注入的 metadata）：

| 判据 | 说明 |
|------|------|
| `lc_source == "summarization"` | 摘要模型调用的来源标记 |
| `langgraph_node` 以 `ContextSummaryMiddleware` 开头 | 中间件作为节点出现，含它注入的 SystemMessage |

这是 `stream_mode="messages"` 的固有缺口 —— 只要开启上下文压缩就存在，
与展示策略无关（历史接口那边另有 `lc_source` 过滤兜底）。
回归测试见 `tests/test_summary_leak.py`。

### 2. reasoning 为什么不会混进正文

reasoning 只有两个合法来源，都不在 `content` 里：

| 来源 | 场景 |
|------|------|
| `additional_kwargs["reasoning_content"]` | DeepSeek-R1 / `ChatDeepSeek` 等推理模型 |
| `content` 块列表中 `type` 为 `reasoning` / `thinking` 的块 | LangChain v1 `content_blocks` |

本项目的 `ChatOpenAI`（chat-completions 模式）在 `_convert_delta_to_message_chunk` 里
**只取 `delta.content`**，`reasoning_content` 被整块丢弃 —— 既不进 `content`，也不进
`additional_kwargs`，实测确认。因此当前配置下 reasoning 天然不可见。

即便如此，过滤器仍做了结构化防御：只要能取到 reasoning，就只把它用作提示，
永远不会拼进 `content`。将来换成会暴露 reasoning 的 provider（或把模型切到
`deepseek-reasoner` 并改用 `ChatDeepSeek`）时，规则自动生效。

> 已知局限：如果某个模型把思维链**内联**进正文（例如输出 `<thought>…</thought>`），
> 那是模型行为而非 provider 契约，过滤器不做正则手术 —— 流式场景下跨 chunk 的
> 标签匹配极易失效，宁可不管也不做半吊子处理。

### 3. 流式与历史的一致性

过渡语是独立的一条 `AIMessage`，若历史接口原样返回，刷新会话就会变成两个气泡、
内容还对不上。因此：

- 流式：所有正文累加进**同一个**气泡
- 历史：`session_service._merge_consecutive_assistant()` 把相邻的 assistant 条目拼接
  （`ToolMessage` 已被跳过，因此工具前后的两条 AI 消息正好相邻）
- 非流式：`final_answer_from_messages()` 用同一规则拼接

三者由 `tests/test_stream_endpoint.py::test_history_matches_streamed_bubble` 守住，
`tests/test_stream_filter.py::test_matches_stream_render` 再从纯逻辑层校验一遍。

### 4. 上下文过长时的压缩策略

多轮对话会让检查点里的消息无限增长，最终撞上模型窗口。Agent 通过 `SummarizationMiddleware` 处理：

| 参数 | 默认 | 环境变量 | 含义 |
|------|------|----------|------|
| 开关 | 开启 | `CONTEXT_SUMMARIZATION_ENABLED` | 关闭后完全不压缩 |
| 触发消息数 | 30 | `CONTEXT_TRIGGER_MESSAGES` | 超过则触发 |
| 触发 token 数 | 24000 | `CONTEXT_TRIGGER_TOKENS` | 超过则触发 |
| 保留消息数 | 8 | `CONTEXT_KEEP_MESSAGES` | 最近 N 条原文保留 |

触发后由 `CONTEXT_SUMMARY_PROMPT`（中文，要求保留用户偏好、已确认事实、未完成事项）把较早的消息压成一条摘要消息，插回历史开头，近期原文不动。这样既守住窗口，又不丢关键上下文。

**摘要以 `SystemMessage` 存储，不进前端历史。** LangChain 默认把摘要包成 `HumanMessage`（正文带 `Here is a summary of the conversation to date:` 前缀），历史接口会把它当「用户发言」返回，前端就会冒出用户从没发过、还是英文的假消息。本项目用 `ContextSummaryMiddleware` 替换了消息构造：摘要以 system 角色入状态（对模型而言「背景设定」语义更准），历史接口只映射 Human / AI，因此天然不显示；另按 `lc_source="summarization"` 标记再做一道防御。

## 🔍 相关性检测算法

### 关键词匹配策略

`app/agent/filter.py` 采用轻量级前置过滤，**不消耗模型调用**：

| 类别 | 关键词示例 |
|------|-----------|
| 动漫本体 | 动漫、动画、番剧、新番、追番、anime、cartoon |
| 内容相关 | 角色、剧情、结局、推荐、评分、声优、制作公司 |
| 题材分类 | 类型、题材、漫画、轻小说、二次元、ACG |
| 行为相关 | 观看、追剧、完结、更新、集数、统计、排行 |

### 判断逻辑

```
包含任一关键词                → 通过
含数字且出现「我」/「用户」    → 通过（可能是查询个人数据）
包含问候语                    → 通过（交给模型判断）
长度 < 10 字符                → 通过（交给模型判断）
否则                          → 拒绝
```

### 示例

| 问题 | 结果 | 原因 |
|------|------|------|
| 请推荐一些好看的动漫 | ✅ 通过 | 命中「推荐」「动漫」 |
| 我的追番历史怎么样 | ✅ 通过 | 命中「追番」 |
| 我看了3部 | ✅ 通过 | 含数字 + 「我」 |
| 你好 | ✅ 通过 | 问候语 |
| 请帮我写一段快速排序的代码实现 | ❌ 拒绝 | 未命中且较长 |

## 📊 性能优化

### 1. 流式传输配置

```python
return StreamingResponse(stream, **sse.sse_response_kwargs())
# media_type=text/event-stream
# headers: Cache-Control=no-cache, X-Accel-Buffering=no
```

Nginx 反向代理时**必须** `proxy_buffering off`，否则 SSE 会被缓冲而失去流式效果。

### 2. Token配置

| 参数 | 默认 | 环境变量 |
|------|------|----------|
| temperature | 0.7 | `LLM_TEMPERATURE` |
| max_tokens | 1000 | `LLM_MAX_TOKENS` |
| model | deepseek-chat | `LLM_MODEL` |

### 3. 数据库查询优化

- 工具 SQL 使用 `LEFT JOIN` 一次取回所需字段
- 追踪记录按 `updated_at` 排序，配合索引
- 所有查询参数化，避免注入且利于执行计划复用

### 4. 事件循环不阻塞

数据库为同步 API，路由中统一经 `run_in_threadpool` 执行，避免阻塞 FastAPI 事件循环。

## ⚠️ 错误处理

### 统一错误码

| 错误码 | HTTP | 触发场景 |
|--------|------|----------|
| `MISSING_PARAMETER` | 400 | 缺少必填参数（含请求体校验失败） |
| `EMPTY_QUESTION` | 400 | 问题为空 |
| `EMPTY_TITLE` | 400 | 标题为空 |
| `SESSION_NOT_FOUND` | 404 | 会话不存在或已删除 |
| `SESSION_CREATE_FAILED` | 500 | 会话创建失败 |
| `SESSION_UPDATE_FAILED` | 404 | 标题更新失败 |
| `SESSION_DELETE_FAILED` | 500 | 会话删除失败 |
| `AI_SERVICE_ERROR` | 500 | AI 服务调用失败 |
| `INTERNAL_SERVER_ERROR` | 500 | 未预期异常 |

> 这些字符串被前端 `src/api/chat.ts` 的 `mapErrorCode()` 直接依赖，不可随意改动。

### 错误响应示例

```json
{
  "success": false,
  "error": {
    "message": "会话不存在或已被删除",
    "code": "SESSION_NOT_FOUND",
    "timestamp": 1720540800.123
  }
}
```

### 流式接口的异常处理

SSE 已开始输出后无法再改 HTTP 状态码，因此运行时异常在 `chat_service` 内被捕获并降级为 `error` 事件（HTTP 仍为 200）。

## 🧪 测试

```bash
.venv\Scripts\python -m pytest -q
```

测试用 `InMemorySaver` 替换检查点、内存存储替换元数据表，**无需 PostgreSQL** 即可验证全链路。

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/test_sse_and_filter.py` | SSE 事件字段、相关性过滤 |
| `tests/test_ids.py` | ID 格式、标题截断 |
| `tests/test_chat_contract.py` | 回答字段、流式帧序列、检查点记忆 |
| `tests/test_api_endpoints.py` | HTTP 路由、SSE 响应头、错误码 |
| `tests/test_stream_filter.py` | 回答净化：过渡语照常下发、`ToolMessage`/reasoning 不外泄、多轮工具提示、摘要以 SystemMessage 存储且不进历史、上下文摘要真实生效 |
| `tests/test_stream_endpoint.py` | 端到端流式：帧序列、只有一个 `end`、工具 JSON 不泄漏、历史与流式气泡一致 |
| `tests/test_summary_leak.py` | 上下文摘要不泄漏：流式正文 / 历史接口 / 非流式回答三处都不含内部笔记 |
| `tests/test_knowledge_hint.py` | 知识库清单注入：提示文本、每轮一次、固定 id 不堆积、不泄漏、清单缓存与失效 |
| `tests/test_mcp_client.py` | MCP 协议：握手、tools/list、tools/call、通知乱序、超时、子进程重启 |
| `tests/test_bilibili_mcp.py` | B站推荐：加权排序、去重、补详情上限、链接拼装、工具层错误兜底 |
| `tests/test_rag_store_migration.py` | 知识库集合按 embedding 空间隔离、旧集合自动迁移与失败保数据 |
| `tests/test_async_checkpointer.py` | 检查点必须支持异步（防回退到同步 `PostgresSaver`） |

### 典型测试场景

| 场景 | 输入 | 预期 |
|------|------|------|
| 动漫推荐 | "请推荐一些好看的动漫" | `is_anime_related=true`，正常回答 |
| 个人数据 | "我的追番历史怎么样" | 触发工具查询 |
| 非动漫问题 | "请帮我写一段快速排序的代码实现" | `is_anime_related=false`，固定话术 |
| 空问题 | `""` | 400 / `EMPTY_QUESTION` |
| 多轮对话 | 连续两轮同一 `session_id` | 历史消息数累加为 4 |

### 集成测试（需服务已启动）

```python
import requests

def test_anime_chat_api():
    response = requests.post(
        "http://localhost:5000/api/anime-chat",
        json={"question": "推荐一些动漫", "user_id": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "answer" in data["data"]
```

## 🔐 安全考虑

### 1. API密钥管理

```bash
DEEPSEEK_API_KEY=your_key_here   # 写入 ai/.env，已在 .gitignore 中排除
```

### 2. SQL注入防护

所有查询使用参数化占位符 `%s`，禁止字符串拼接。

### 3. 数据隐私

- 系统提示词要求不泄露完整 ID 等敏感信息
- 工具返回前剔除内部主键
- 继续会话时 `user_id` 取自元数据表，防止越权

### 4. CORS配置

由 `CORS_ORIGINS` 控制，默认 `*`。生产环境建议：

```
CORS_ORIGINS=https://yourdomain.com
```

### 5. 前端渲染与 XSS 防护

模型回答里会混入**用户输入、知识库文档片段、B站视频标题**等外部内容，
这些内容最终会以 HTML 形式渲染到气泡里（为了把 URL 变成可点击链接）。
因此前端不能直接把模型输出丢给 `v-html`。

渲染链路（`frontend/src/utils/rich-text.ts` → `toSafeHtml()`）分为三层：

| 顺序 | 处理 | 作用 |
|------|------|------|
| 1 | `escapeHtml()` | 先把 `& < > " '` 全部转义，断掉一切标签注入 |
| 2 | `linkify()` | 只由本模块插入 `<a>`，`href` 必须通过 `isSafeHttpUrl()`（仅 http/https） |
| 3 | `DOMPurify.sanitize()` | 兜底净化，只放行 `p` / `br` / `a`，并用 hook 强制 `target="_blank"` + `rel="noopener noreferrer nofollow"` |

第 1 步之后页面上不可能出现「非本模块生成的标签」，DOMPurify 是第二道防线，
而不是唯一防线。另有两个细节：

- **末尾标点不吞进链接**：`见 https://b23.tv/abc。` 的句号留在链接外
- **结果缓存**：流式时每 token 重渲染、`thinkingState` 变化会让整个列表重渲染，
  因此按内容做小容量缓存（50 条），避免反复净化

自检脚本：`npm run test:rich-text`（用 jsdom 造真 DOM，37 项断言，
覆盖转义、危险协议、DOMPurify 真实净化、排版与缓存）。

## 📈 监控与日志

### 关键日志点

| 位置 | 内容 |
|------|------|
| 启动 | MySQL / PostgreSQL / 检查点 / Agent 就绪状态 |
| `chat_service` | 会话解析、流式失败堆栈 |
| `graph` | Agent 构建（模型名、工具数量） |
| `session_service` | 会话创建 |

日志格式：

```
2026-10-08 11:18:20,123 [INFO] app.agent.graph: 动漫问答 Agent 已构建: model=deepseek-chat, tools=7
```

## 🚀 部署建议

### 开发环境

```bash
# 1. 创建数据库
psql -U postgres -c "CREATE DATABASE anime_ai;"
# 2. 配置环境变量
copy .env.example .env
# 3. 启动
start_server.bat
```

### 生产环境

```bash
# 多 worker
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers 4
```

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:5000;
    proxy_buffering off;          # SSE 必需
    proxy_read_timeout 300s;
    proxy_set_header Host $host;
}
```

## 📚 相关文档

- [技术架构说明](./技术架构说明.md)
- [功能说明-会话管理系统](./功能说明-会话管理系统.md)
- [功能说明-翻译工具](./功能说明-翻译工具.md)

---

**最后更新**：2026-10-08
