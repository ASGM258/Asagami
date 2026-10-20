# 动漫管理网站前端项目文档

## 📖 项目概述

这是一个基于 Vue 3 + TypeScript 构建的现代化动漫管理网站前端应用，提供动漫浏览、观看历史追踪、AI智能助手、角色探索等丰富功能。

### ✨ 核心特性

- **用户认证系统** - 完整的登录/注册流程，JWT Token 管理
- **动漫浏览** - 分页展示、年份筛选、搜索功能
- **当季新番** - 按星期分类展示最新动漫，轮播图推荐
- **观看历史** - 追踪用户的观看记录，支持状态标记
- **AI智能助手** - 基于 DeepSeek 模型的流式对话，会话管理
- **动漫资讯** - 资讯列表无限滚动、分类筛选、详情阅读（数据来自 Python 资讯服务）
- **角色探索** - 浏览动漫角色详情，点赞评论互动
- **响应式设计** - 适配桌面端、平板、手机等多种设备

---

## 🛠️ 技术栈

### 核心框架
- **Vue 3.5+** - 渐进式 JavaScript 框架，使用 Composition API
- **TypeScript ~6.0** - 类型安全的 JavaScript 超集
- **Vite 8.0+** - 下一代前端构建工具

### UI 组件库
- **Element Plus 2.14+** - 基于 Vue 3 的组件库
- **@element-plus/icons-vue** - Element Plus 图标库

### 状态管理
- **Pinia 3.0+** - Vue 官方推荐的状态管理库

### 路由管理
- **Vue Router 4.6+** - Vue 官方路由管理器

### HTTP 请求
- **Axios 1.17+** - 基于 Promise 的 HTTP 客户端

### 样式处理
- **SCSS/Sass 1.100+** - CSS 预处理器

---

## 📁 项目结构

```
d:\动漫管理网站\frontend\frontended
├── public/                    # 静态资源
│   ├── favicon.svg           # 网站图标
│   └── icons.svg             # SVG 图标集合
├── src/
│   ├── api/                  # API 接口层
│   │   ├── anime.ts          # 动漫相关接口（Java后端）
│   │   ├── auth.ts           # 认证相关接口（Java后端）
│   │   ├── chat.ts           # AI聊天相关接口（Python后端）
│   │   ├── comment.ts        # 评论相关接口（Java后端）
│   │   └── news.ts           # 资讯相关接口（Python后端）
│   ├── assets/               # 静态资源（图片等）
│   ├── components/           # 公共组件
│   │   ├── Layout.vue        # 主布局组件
│   │   └── HelloWorld.vue    # 示例组件
│   ├── composables/          # 组合式函数
│   ├── router/               # 路由配置
│   │   └── index.ts          # 路由定义与守卫
│   ├── stores/               # Pinia 状态管理
│   │   ├── auth.ts           # 认证状态管理
│   │   └── index.ts          # Store 入口
│   ├── types/                # TypeScript 类型定义
│   │   ├── auth.ts           # 认证相关类型
│   │   ├── anime.ts          # 动漫相关类型
│   │   └── env.d.ts          # 环境变量类型声明
│   ├── utils/                # 工具函数
│   │   └── request.ts        # Axios 封装与拦截器
│   ├── views/                # 页面视图组件
│   │   ├── LoginView.vue     # 登录页
│   │   ├── RegisterView.vue  # 注册页
│   │   ├── HomeView.vue      # 首页（动漫列表）
│   │   ├── AnimeDetailView.vue # 动漫详情页
│   │   ├── SeasonalAnimeView.vue # 当季新番页
│   │   ├── WatchHistoryView.vue # 观看历史页
│   │   ├── ChatView.vue      # AI聊天页
│   │   ├── CharacterView.vue # 角色列表页
│   │   ├── CharacterDetailView.vue # 角色详情页
│   │   └── ProfileView.vue   # 个人信息页
│   ├── App.vue               # 根组件
│   ├── main.ts               # 应用入口
│   └── style.css             # 全局样式
├── .env                      # 环境变量
├── .env.development          # 开发环境变量
├── .env.production           # 生产环境变量
├── package.json              # 项目依赖配置
├── tsconfig.json             # TypeScript 配置
├── vite.config.ts            # Vite 配置
└── README.md                 # 项目说明文档
```

---

## 🚀 快速开始

### 环境要求

- Node.js >= 18.x
- npm >= 9.x 或 pnpm >= 8.x

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:5173

### 生产构建

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

---

## 🔧 环境配置

### 环境变量文件

项目使用多环境变量配置：

- `.env` - 通用环境变量
- `.env.development` - 开发环境配置
- `.env.production` - 生产环境配置

### 关键配置项

```env
# Java后端API地址（主业务）
VITE_API_BASE_URL=http://localhost:8081/api

# Python后端API地址（AI功能）
VITE_PYTHON_API_URL=http://localhost:5000/api
```

---

## 🏗️ 架构设计

### 双后端架构

项目采用双后端架构设计：

1. **Java 后端 (8081端口)**
   - 负责用户认证、授权
   - 动漫数据管理
   - 观看历史记录
   - 角色信息管理
   - 评论系统

2. **Python 后端 (5000端口)**
   - AI 智能问答（基于 DeepSeek）
   - 会话管理
   - 流式响应处理
   - 动漫资讯（抓取 → 翻译 → 摘要 → 审核流水线）

### 前端架构层次

```
┌─────────────────────────────────────┐
│         Views (页面视图层)           │
├─────────────────────────────────────┤
│      Components (公共组件层)         │
├─────────────────────────────────────┤
│    Stores (状态管理层 - Pinia)       │
├─────────────────────────────────────┤
│       API (接口封装层 - Axios)       │
├─────────────────────────────────────┤
│     Utils (工具函数层)               │
└─────────────────────────────────────┘
```

---

## 📝 核心功能模块

### 1. 用户认证系统

**相关文件：**
- `src/views/LoginView.vue` - 登录页面
- `src/views/RegisterView.vue` - 注册页面
- `src/stores/auth.ts` - 认证状态管理
- `src/api/auth.ts` - 认证API接口

**功能特性：**
- 用户名/邮箱登录
- 新用户注册
- JWT Token 自动管理
- Token 过期自动跳转登录
- 用户信息持久化（localStorage）

**工作流程：**
1. 用户输入凭据提交表单
2. 调用后端 `/auth/login` 或 `/auth/register`
3. 获取 accessToken 和用户信息
4. 存储到 localStorage 和 Pinia Store
5. 路由守卫检查登录状态

### 2. 动漫浏览系统

**相关文件：**
- `src/views/HomeView.vue` - 动漫列表主页
- `src/api/anime.ts` - 动漫API接口

**功能特性：**
- 分页展示动漫列表（默认每页16个）
- 年份筛选（当前年份往前推20年）
- 关键词搜索（标题模糊匹配）
- 观看状态标记（未开始/观看中/已完成/已放弃）
- 评分显示
- 懒加载图片优化

**交互设计：**
- 点击卡片进入详情页
- 右上角爱心图标切换观看状态
- 右下角显示评分标签
- 鼠标悬停卡片放大效果

### 3. 当季新番系统

**相关文件：**
- `src/views/SeasonalAnimeView.vue` - 当季新番页面
- `src/api/anime.ts` - getBanners, getSeasonalAnime

**功能特性：**
- 顶部轮播图展示热门动漫
- 按星期分类展示（周一至周日 + 待定）
- 刷新按钮手动触发数据更新
- 轮播图左右布局（左侧图片，右侧信息）
- 自动播放轮播（5秒间隔）

**技术亮点：**
- 轮播图使用渐变遮罩提升可读性
- 星期标签高亮当前选中
- 刷新失败统一提示"5分钟后刷新"
- 响应式网格布局（7列→5列→4列→2列→1列）

### 4. 观看历史系统

**相关文件：**
- `src/views/WatchHistoryView.vue` - 观看历史页面
- `src/api/anime.ts` - getWatchHistoryList

**功能特性：**
- 展示用户观看过的动漫记录
- 年份筛选功能
- 搜索过滤
- 观看状态更新
- 与首页相同的UI风格

**数据流向：**
```
后端 → getWatchHistoryList API → 前端渲染 → 用户操作 → updateWatchStatus → 后端更新
```

### 5. AI智能助手系统

**相关文件：**
- `src/views/ChatView.vue` - AI聊天页面
- `src/api/chat.ts` - 聊天API接口
- Python后端（5000端口）

**功能特性：**
- 流式响应（SSE Server-Sent Events）
- 会话管理（创建、删除、重命名）
- 消息历史持久化
- 用户头像和昵称显示
- 打字指示器动画
- AI回复分段展示（段落格式）

**技术实现：**
```typescript
// 流式聊天核心逻辑
await streamChat(
  question,
  userId,
  sessionId,
  // onChunk - 实时接收内容片段
  (chunk) => {
    fullAnswer += chunk
    messages.value[aiMessageIndex].content = fullAnswer
    scrollToBottom()
  },
  // onEnd - 传输完成回调
  (sessionId, messageId) => {
    messages.value[aiMessageIndex].completed = true
  }
)
```

**会话命名规则：**
- 新会话自动生成：`新会话N`（N为当前用户会话数量+1）
- 支持手动重命名
- 支持删除会话（软删除/硬删除）

### 6. 资讯系统

**相关文件：**
- `src/views/NewsListView.vue` - 资讯列表页（无限滚动）
- `src/views/NewsDetailView.vue` - 资讯详情页
- `src/components/NewsCard.vue` - 资讯卡片
- `src/api/news.ts` - 资讯API接口
- Python后端（5000端口，`/api/news/*`）

**功能特性：**
- 无限滚动加载（IntersectionObserver，提前 200px 预加载）
- 分类筛选标签（分类与数量来自 `/news/categories`）
- 骨架屏与空状态、加载失败点击重试
- 详情页正文渲染、标签展示、分享（复制链接）

**接口说明：**

| 接口 | 方法 | 说明 |
|------|------|------|
| `/news/list` | GET | 分页列表，返回 `PageResponse<NewsItem>` |
| `/news/detail` | POST | 详情，请求体 `{newsId}` |
| `/news/categories` | GET | 分类列表（「全部」在第一位） |

**对接注意：**
- 资讯接口走 Python 服务，因此 `news.ts` 使用 `fetch` 而非 `utils/request.ts` 的 axios 实例
- 响应外壳 `{success, message, timestamp, data}` 在 `news.ts` 内部转换为 `{code, message, data, timestamp}`，视图层无需感知差异
- 列表字段名兼容 `list` 与 `records` 两种形式
- 后端不可用时列表页会展示内置示例数据并给出提示（见 `getFallbackNewsList`）

### 6. 角色探索系统

**相关文件：**
- `src/views/CharacterView.vue` - 角色列表页
- `src/views/CharacterDetailView.vue` - 角色详情页
- `src/api/anime.ts` - 角色相关API

**功能特性：**

#### 角色列表页
- 分页展示角色（默认每页12个）
- 中英文搜索支持
- 喜欢按钮（右上角心形图标）
- 显示受欢迎程度（格式化数字，如 1.5万）
- 响应式网格布局

#### 角色详情页
- 角色基本信息展示（头像、名称、生日、别名等）
- 角色简介
- 评论系统（发表、编辑、删除、回复）
- 点赞功能（评论和回复）
- 局部刷新机制（操作后仅刷新评论和点赞状态）

**评论系统设计：**
```
根评论
  ├─ 回复1
  ├─ 回复2
  └─ 回复3
```

**点赞状态同步：**
- 使用 `getUserCharacterCommentLikeStatus` 批量获取点赞状态
- 本地维护 `likedCommentIds` 和 `likedReplyIds` Set
- 操作后立即更新UI，无需全量刷新

### 7. 个人信息管理系统
**相关文件：**
- `src/views/ProfileView.vue` - 个人信息页面
- `src/api/auth.ts` - updateProfile, uploadAvatar

**功能特性：**
- 查看和修改昵称、邮箱
- 头像上传（支持 jpg/png/gif/webp/bmp，最大2MB）
- 密码修改（需验证当前密码）
- 表单验证（Element Plus Form Rules）
- 实时头像预览

**头像上传流程：**
1. 选择图片文件
2. 前端验证（MIME类型、扩展名、文件大小）
3. 生成预览URL（URL.createObjectURL）
4. 调用 `/upload/avatar` 上传
5. 获取 avatarUrl
6. 调用 `/auth/profile` 更新用户信息

---

## 🔐 安全机制

### Token 管理

**存储策略：**
- accessToken 存储在 localStorage
- 用户信息序列化后存储在 localStorage

**自动刷新机制：**
- 应用启动时从 localStorage 恢复 Token
- Pinia Store 初始化时调用 `initAuth()`

**过期处理：**
- 响应拦截器检测 code 1004/1005（Token无效/过期）
- 自动清除本地存储
- 跳转到登录页并携带 redirect 参数
- 显示友好提示："登录已过期，请重新登录"

### 路由守卫

```typescript
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('accessToken')
  
  if (to.meta.requiresAuth && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})
```

### API 请求拦截

**请求拦截器：**
- 自动添加 Authorization Header
- 格式：`Bearer ${token}`

**响应拦截器：**
- 统一处理业务错误码
- Token 过期自动跳转
- 错误消息提取

---

## 🎨 UI/UX 设计

### 设计风格

- **配色方案**：紫色渐变主题（#e0c3fc → #8ec5fc）
- **圆角设计**：卡片、按钮统一使用 8px 圆角
- **阴影效果**：轻微阴影提升层次感
- **动画过渡**：hover 效果、加载动画、打字指示器

### 响应式断点

```scss
// 桌面端（> 1200px）
grid-template-columns: repeat(4, 1fr);

// 平板（768px - 1200px）
grid-template-columns: repeat(3, 1fr);

// 小屏手机（480px - 768px）
grid-template-columns: repeat(2, 1fr);

// 超小屏（< 480px）
grid-template-columns: repeat(1, 1fr);
```

### 图片优化策略

**懒加载：**
```html
<img loading="lazy" @load="handleImageLoad" @error="handleImageError" />
```

**占位符：**
- 加载中显示灰色背景 + 图标
- 加载失败显示默认 SVG 占位图

**透明度渐变：**
```scss
.cover-image {
  opacity: 0;
  &.loaded {
    opacity: 1;
  }
}
```

---

## 📊 数据流设计

### 状态管理（Pinia）

**Auth Store 结构：**
```typescript
{
  token: string,              // JWT Token
  userInfo: UserInfo | null,  // 用户信息
  isLoggedIn: boolean,        // 登录状态
  
  // Actions
  login(),                    // 登录
  register(),                 // 注册
  fetchUserInfo(),            // 获取用户信息
  logout(),                   // 登出
  initAuth()                  // 初始化（从localStorage恢复）
}
```

### 组件通信

**Provide/Inject：**
- Layout 组件 provide `searchQuery`
- HomeView 和 WatchHistoryView inject 搜索关键词

**事件总线：**
```javascript
// 触发搜索
window.dispatchEvent(new CustomEvent('searchChange'))

// 监听搜索
window.addEventListener('searchChange', handler)
```

---

## 🧪 调试技巧

### 日志输出

开发阶段在各关键位置添加了 console.log：

```typescript
console.log('[HomeView] 开始获取动漫列表...')
console.log('[HomeView] API完整响应:', JSON.stringify(response, null, 2))
```

**注意：** 生产环境应移除所有 console 语句

### 常见问题排查

**1. Token 过期问题**
- 检查 localStorage 中的 accessToken
- 查看 Network 面板的 401 响应
- 确认后端返回的 code 是否为 1004/1005

**2. 图片加载失败**
- 检查图片 URL 是否有效
- 查看浏览器控制台的网络请求
- 确认 CORS 配置

**3. API 请求失败**
- 检查环境变量配置（VITE_API_BASE_URL）
- 确认后端服务是否启动（8081/5000端口）
- 查看 axios 拦截器的错误日志

---

## 🚦 部署指南

### 构建优化

Vite 默认配置已包含：
- Tree Shaking（摇树优化）
- Code Splitting（代码分割）
- Minification（代码压缩）

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /usr/share/nginx/html;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API 代理（如果需要）
    location /api/ {
        proxy_pass http://backend-server:8081/api/;
    }
}
```

### Docker 部署

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## 📈 性能优化

### 已实施的优化

1. **图片懒加载** - `loading="lazy"`
2. **路由懒加载** - Vue Router 动态导入
3. **代码分割** - Vite 自动分包
4. **防抖节流** - 搜索输入处理
5. **虚拟滚动** - 长列表优化（待实现）

### 待优化项

- [ ] 引入虚拟滚动处理大量数据
- [ ] Service Worker 离线缓存
- [ ] 图片 CDN 加速
- [ ] Gzip/Brotli 压缩
- [ ] 预加载关键资源

---

## 🐛 已知问题与限制

### 当前限制

1. **搜索功能** - 仅支持标题模糊匹配，不支持高级搜索
2. **图片上传** - 最大2MB，不支持批量上传
3. **AI助手** - 仅限动漫相关问题，其他话题会被拒绝
4. **评论系统** - 暂不支持图片/表情

### 待修复问题

- [ ] 某些情况下图片加载缓慢
- [ ] 移动端侧边栏收起功能
- [ ] 深色模式支持

---

## 📅 更新日志

### v1.0.0 (2026-07-09)

**新增功能：**
- ✅ 用户认证系统（登录/注册）
- ✅ 动漫浏览与筛选
- ✅ 当季新番展示
- ✅ 观看历史追踪
- ✅ AI智能助手（流式对话）
- ✅ 角色探索与评论
- ✅ 个人信息管理

**技术特性：**
- ✅ Vue 3 + TypeScript
- ✅ Pinia 状态管理
- ✅ Element Plus UI
- ✅ 双后端架构
- ✅ 响应式设计

---

## 👥 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发规范

1. **代码风格** - 遵循 ESLint + Prettier 配置
2. **提交信息** - 使用 Conventional Commits 规范
3. **分支管理** - feature/*, bugfix/*, hotfix/*
4. **测试覆盖** - 新功能需包含单元测试

---

## 📄 许可证

本项目仅供学习和个人使用。

---

## 🙏 致谢

- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Element Plus](https://element-plus.org/) - Vue 3 组件库
- [Vite](https://vitejs.dev/) - 下一代前端工具
- [DeepSeek](https://deepseek.com/) - AI 模型支持

---

**最后更新时间：** 2026-07-09
# Vue 3 + TypeScript + Vite

This template should help get you started developing with Vue 3 and TypeScript in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).
