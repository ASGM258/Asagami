# 功能模块索引

## 📚 文档目录

本文档索引列出了动漫管理网站前端项目的所有功能模块说明文档。

---

## ✅ 已完成文档

### 1. [用户认证系统](./01-用户认证系统.md)

**核心功能：**
- 用户注册
- 用户登录
- JWT Token 管理
- Token 过期处理
- 路由守卫
- 用户信息管理

**相关文件：**
- `src/views/LoginView.vue`
- `src/views/RegisterView.vue`
- `src/stores/auth.ts`
- `src/api/auth.ts`
- `src/router/index.ts` (路由守卫)

---

### 2. [动漫浏览系统](./02-动漫浏览系统.md)

**核心功能：**
- 动漫列表展示（分页）
- 年份筛选
- 关键词搜索
- 观看状态标记
- 图片懒加载优化
- 响应式网格布局

**相关文件：**
- `src/views/HomeView.vue`
- `src/api/anime.ts` (getAnimeList, updateWatchStatus)
- `src/components/Layout.vue` (搜索框)

---

### 3. [当季新番系统](./03-当季新番系统.md)

**核心功能：**
- 轮播图推荐
- 按星期分类浏览
- 数据刷新功能
- 动漫卡片列表
- 响应式布局

**相关文件：**
- `src/views/SeasonalAnimeView.vue`
- `src/api/anime.ts` (getBanners, getSeasonalAnime, refreshSeasonalAnime)

---

### 4. [喜欢的角色功能](./04-喜欢的角色功能.md)

**页面路径：** `/favorite-characters`

**核心功能：**
- 展示用户喜欢的角色列表
- 名称搜索（支持中英文）
- 分页浏览
- 点击跳转角色详情
- 取消喜欢操作
- 图片懒加载优化

**相关文件：**
- `src/views/FavoriteCharactersView.vue`
- `src/api/anime.ts` (getFavoriteCharacterList)
- `src/router/index.ts`
- `src/components/Layout.vue` (菜单入口)

**特点：**
- 参考观看历史页面的实现方式
- 与角色列表页相同的UI风格
- Redis 缓存优化（30分钟）
- 联表查询 + PageHelper 分页

---

## 📝 待补充文档

### 5. 观看历史系统

**页面路径：** `/watch-history`

**核心功能：**
- 展示用户观看过的动漫记录
- 年份筛选
- 搜索过滤
- 观看状态更新
- 与首页相同的UI风格

**相关文件：**
- `src/views/WatchHistoryView.vue`
- `src/api/anime.ts` (getWatchHistoryList)

**特点：**
- 复用首页的组件结构和样式
- 数据源不同（观看历史 vs 全部动漫）
- 支持相同的交互操作

---

### 6. AI智能助手系统

**页面路径：** `/chat`

**核心功能：**
- 流式对话（SSE）
- 会话管理（创建、删除、重命名）
- 消息历史持久化
- 用户头像和昵称显示
- 打字指示器动画
- AI回复分段展示

**技术亮点：**
- Server-Sent Events (SSE) 实现流式响应
- Python后端（5000端口）处理AI请求
- 基于 DeepSeek 模型
- 会话自增命名规则

**相关文件：**
- `src/views/ChatView.vue`
- `src/api/chat.ts`
- Python后端（独立服务）

**API 接口：**
```typescript
// 创建会话
POST http://localhost:5000/api/session/create

// 获取会话列表
GET http://localhost:5000/api/sessions?user_id={userId}

// 获取会话消息
GET http://localhost:5000/api/session/{sessionId}/messages

// 流式聊天
POST http://localhost:5000/api/anime-chat-stream
```

---

### 7. 角色探索系统

#### 6.1 角色列表页

**页面路径：** `/characters`

**核心功能：**
- 分页展示角色
- 中英文搜索
- 喜欢按钮
- 受欢迎程度显示
- 响应式网格布局

**相关文件：**
- `src/views/CharacterView.vue`
- `src/api/anime.ts` (getCharacterList, updateCharacterFavorite)

#### 6.2 角色详情页

**页面路径：** `/characters/:id`

**核心功能：**
- 角色基本信息展示
- 角色简介
- 评论系统（发表、编辑、删除、回复）
- 点赞功能（评论和回复）
- 局部刷新机制

**评论系统设计：**
```
根评论
  ├─ 回复1
  ├─ 回复2
  └─ 回复3
```

**相关文件：**
- `src/views/CharacterDetailView.vue`
- `src/api/anime.ts` (角色相关API)

**点赞状态同步：**
- 批量获取点赞状态
- 本地维护 Set 集合
- 操作后立即更新UI

---

### 8. 个人信息管理系统

**页面路径：** `/profile`

**核心功能：**
- 查看和修改昵称、邮箱
- 头像上传（支持多种格式，最大2MB）
- 密码修改
- 表单验证
- 实时头像预览

**相关文件：**
- `src/views/ProfileView.vue`
- `src/api/auth.ts` (updateProfile, uploadAvatar)

**头像上传流程：**
1. 选择图片文件
2. 前端验证（MIME类型、扩展名、文件大小）
3. 生成预览URL
4. 调用上传API
5. 获取 avatarUrl
6. 更新用户信息

---

### 9. 动漫详情系统

**页面路径：** `/anime/:id`

**注意：** 当前代码库中未找到 `AnimeDetailView.vue` 文件，可能尚未实现或文件名不同。

**预期功能：**
- 动漫详细信息展示
- 播放链接
- 集数列表
- 评论系统
- 相关推荐

---

## 🔗 模块关系图

```
┌─────────────────────────────────────┐
│         用户认证系统                 │
│  (登录/注册/Token管理)              │
└──────────┬──────────────────────────┘
           │ 提供用户身份
           ↓
┌─────────────────────────────────────┐
│         主布局 Layout                │
│  (Header + Aside + Main + Footer)  │
└──┬────┬────┬────┬────┬────┬─────────┘
   │    │    │    │    │    │
   ↓    ↓    ↓    ↓    ↓    ↓
 ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐
 │首页│ │新番│ │AI  │ │角色│ │历史│ │个人│
 │    │ │    │ │助手│ │    │ │    │ │信息│
 └──┘ └──┘ └──┘ └──┘ └──┘ └──┘
   │    │         │    │
   ↓    ↓         ↓    ↓
 ┌────────┐  ┌────────┐
 │动漫详情│  │角色详情│
 └────────┘  └────────┘
```

---

## 📊 技术栈总览

### 前端框架
- Vue 3.5+ (Composition API)
- TypeScript ~6.0
- Vite 8.0+

### UI 组件
- Element Plus 2.14+
- @element-plus/icons-vue

### 状态管理
- Pinia 3.0+

### 路由
- Vue Router 4.6+

### HTTP 客户端
- Axios 1.17+

### 样式
- SCSS/Sass 1.100+

### 后端服务
- Java Spring Boot (8081端口) - 主业务
- Python Flask/FastAPI (5000端口) - AI功能

---

## 🎯 核心设计模式

### 1. 组合式 API (Composition API)

所有组件使用 `<script setup>` 语法：

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'

const data = ref([])

onMounted(() => {
  fetchData()
})
</script>
```

### 2. 状态管理 (Pinia)

```typescript
export const useAuthStore = defineStore('auth', () => {
  const token = ref('')
  const userInfo = ref(null)
  
  const login = async (data) => { ... }
  const logout = () => { ... }
  
  return { token, userInfo, login, logout }
})
```

### 3. 路由守卫

```typescript
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})
```

### 4. API 封装

```typescript
// api/anime.ts
export const getAnimeList = (params) => {
  return api.get('/anime/list', { params })
}
```

### 5. 请求拦截器

```typescript
// utils/request.ts
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})
```

---

## 🔐 安全机制

### 1. Token 管理
- localStorage 存储
- 自动添加到请求头
- 过期自动跳转登录

### 2. 路由保护
- meta.requiresAuth 标记
- 全局前置守卫
- redirect 参数保存目标路径

### 3. XSS 防护
- Element Plus 自动转义
- v-html 谨慎使用（仅AI回复格式化）

### 4. CSRF 防护
- Token 存储在 localStorage（非 Cookie）
- 每个请求携带 Authorization Header

---

## 📈 性能优化策略

### 已实施
1. **图片懒加载** - `loading="lazy"`
2. **代码分割** - Vite 自动处理
3. **Tree Shaking** - 移除未使用代码
4. **防抖节流** - 搜索输入
5. **虚拟滚动** - （部分场景）

### 待优化
1. **Service Worker** - 离线缓存
2. **图片 CDN** - 加速加载
3. **Gzip/Brotli** - 压缩传输
4. **预加载** - 关键资源
5. **无限滚动** - 替代分页

---

## 🧪 测试建议

### 单元测试
- Pinia Store 逻辑
- 工具函数（格式化、验证等）
- API 封装

### 集成测试
- 登录流程
- 路由跳转
- 状态同步

### E2E 测试
- 完整用户旅程
- 跨页面交互
- 异常场景

---

## 📚 学习资源

### Vue 3
- [Vue 3 官方文档](https://cn.vuejs.org/)
- [Composition API](https://cn.vuejs.org/guide/extras/composition-api-faq.html)

### Element Plus
- [Element Plus 文档](https://element-plus.org/zh-CN/)
- [组件示例](https://element-plus.org/zh-CN/component/button.html)

### TypeScript
- [TypeScript  handbook](https://www.typescriptlang.org/docs/)
- [Vue + TypeScript](https://cn.vuejs.org/guide/typescript/overview.html)

### Vite
- [Vite 官方文档](https://vitejs.dev/)
- [配置指南](https://vitejs.dev/config/)

---

## 🤝 贡献指南

### 添加新功能
1. 创建功能分支 `feature/xxx`
2. 实现功能代码
3. 编写功能文档（在 docs 目录下）
4. 提交 PR

### 文档规范
- 使用 Markdown 格式
- 包含功能概述、API 接口、UI 设计、测试场景
- 提供代码示例和数据流图
- 标注注意事项和优化建议

---

## 📅 更新日志

### 2026-07-09
- ✅ 完成用户认证系统文档
- ✅ 完成动漫浏览系统文档
- ✅ 完成当季新番系统文档
- 📝 创建功能模块索引

### 待完成
- [ ] 观看历史系统文档
- [ ] AI智能助手系统文档
- [ ] 角色探索系统文档
- [ ] 个人信息管理系统文档
- [ ] 动漫详情系统文档

---

**最后更新时间：** 2026-07-09
