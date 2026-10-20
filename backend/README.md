# 动漫管理网站后端系统

## 📖 项目简介

这是一个基于 **Spring Boot 4.0** 构建的动漫管理网站后端系统，提供完整的动漫数据管理、用户互动、评论系统、爬虫数据采集等功能。系统采用现代化的技术栈，集成了 JWT 认证、Redis 缓存、阿里云 OSS 文件存储等企业级特性。

## 🌟 核心功能

- 🔐 **用户认证与授权** - JWT Token 单点登录，安全的用户注册/登录机制
- 📺 **动漫数据管理** - 动漫查询、详情展示、追番记录、观看历史
- 👤 **角色管理** - 角色信息查询、收藏功能、角色详情展示
- 💬 **评论系统** - 多级评论回复、点赞功能、评论管理
- 🕷️ **数据爬虫** - 当季新番、动漫详情、角色抓取三条链路均已迁移到 AniList GraphQL
- 📅 **当季新番** - 通过 AniList GraphQL 智能抓取当前季度新番（原 Jikan API 已不可用）
- 🖼️ **文件上传** - 阿里云 OSS 集成，支持头像、封面图片上传
- 🎠 **轮播图** - 随机展示热门动漫封面
- ⚡ **Redis 缓存** - 高性能数据缓存，提升系统响应速度
- 🔧 **后台管理** - 缓存清理等管理功能

## 🛠️ 技术栈

### 后端框架
- **Spring Boot 4.0.6** - 核心框架
- **Spring Security** - 安全框架
- **MyBatis 4.0.1** - ORM 框架
- **PageHelper 2.1.0** - 分页插件

### 数据存储
- **MySQL 8.x** - 关系型数据库
- **Redis** - 缓存数据库

### 认证与安全
- **JJWT 0.11.5** - JWT Token 生成与验证
- **Spring Validation** - 参数校验

### 第三方服务
- **阿里云 OSS** - 对象存储服务（文件上传）
- **AniList GraphQL** - 当季新番、动漫详情与角色数据源（免费、无需密钥）
  - 动漫侧支持按 MAL ID 查询，MAL ID 匹配逻辑完整保留
  - 角色侧 AniList 不提供 MAL ID，标识使用 `anime_character.anilist_id`

### 开发工具
- **Lombok** - 简化 Java 代码
- **Jackson** - JSON 序列化/反序列化
- **RestTemplate** - HTTP 客户端

## 📁 项目结构

```
backend/
├── src/main/java/com/anime/manager/
│   ├── common/              # 通用常量、结果封装、用户上下文
│   ├── config/              # 配置类（Redis、Security、OSS等）
│   ├── controller/          # REST API 控制器层
│   ├── dto/                 # 数据传输对象
│   ├── entity/              # 数据库实体类
│   ├── exception/           # 异常处理
│   ├── mapper/              # MyBatis Mapper 接口
│   ├── scheduler/           # 定时任务
│   ├── security/            # 安全相关（JWT拦截器）
│   ├── service/             # 业务逻辑层
│   ├── util/                # 工具类
│   └── vo/                  # 视图对象
├── src/main/resources/
│   ├── mapper/              # MyBatis XML 映射文件
│   ├── application.yaml     # 主配置文件
│   ├── application-dev.yaml # 开发环境配置
│   └── application-prod.yaml# 生产环境配置
└── pom.xml                  # Maven 依赖管理
```

## 🚀 快速开始

### 前置要求

- JDK 17+
- Maven 3.6+
- MySQL 8.0+
- Redis 6.0+

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **配置环境变量**
   
   在项目根目录创建 `.env` 文件或修改 `application.yaml`：
   ```properties
   # 数据库配置
   DB_URL=jdbc:mysql://localhost:3306/backend_asagami?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=Asia/Shanghai
   DB_USERNAME=root
   DB_PASSWORD=your_password
   
   # Redis 配置
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_PASSWORD=your_redis_password
   REDIS_DATABASE=0
   
   # JWT 配置
   JWT_SECRET=your_jwt_secret_key
   JWT_EXPIRATION=18000000
   
   # 阿里云 OSS 配置
   OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
   OSS_ACCESS_KEY_ID=your_access_key_id
   OSS_ACCESS_KEY_SECRET=your_access_key_secret
   OSS_BUCKET_NAME=your_bucket_name
   
   # 服务器端口
   SERVER_PORT=8081
   ```

3. **初始化数据库**
   
   执行 SQL 脚本创建数据库表结构（需自行准备 SQL 脚本）

4. **编译项目**
   ```bash
   mvn clean install
   ```

5. **启动应用**
   ```bash
   mvn spring-boot:run
   ```
   
   或在 IDE 中运行 `BackendApplication.java`

6. **访问 API**
   
   默认地址：`http://localhost:8081`

## 📚 API 文档

### 认证模块 `/api/auth`
- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `GET /profile` - 获取用户信息
- `PUT /profile` - 更新用户信息

### 动漫模块 `/api/anime`
- `GET /list` - 分页查询动漫列表
- `GET /detail` - 获取动漫详情
- `GET /seasonal` - 查询当季新番
- `GET /banners` - 获取轮播图
- `PUT /user/update` - 更新追番状态
- `GET /user/history` - 查询追番历史

### 角色模块 `/api/character`
- `GET /list` - 分页查询角色列表
- `POST /detail` - 获取角色详情
- `POST /favorite/update` - 更新喜欢状态

### 评论模块 `/api/comment`
- `POST /add` - 发表评论
- `PUT /update` - 更新评论
- `DELETE /delete/{commentId}` - 删除评论
- `GET /list/{animeId}` - 查询动漫评论
- `POST /reply/add` - 发表回复
- `DELETE /reply/delete/{replyId}` - 删除回复
- `POST /like` - 点赞/取消点赞
- `GET /like/status/{animeId}` - 查询点赞状态

### 角色评论模块 `/api/character/comment`
- `POST /add` - 发表角色评论
- `POST /reply/add` - 发表角色评论回复
- `POST /like` - 点赞角色评论
- `GET /like/status` - 查询角色评论点赞状态

### 文件上传模块 `/api/upload`
- `POST /image` - 上传图片
- `POST /avatar` - 上传头像
- `POST /cover` - 上传封面
- `DELETE /file` - 删除文件

### 爬虫模块 `/anime/scraper`
- `POST /fetch/{malId}` - 抓取单个动漫
- `POST /fetch/batch` - 批量抓取动漫

### 当季新番爬虫 `/api/anime/scraper/seasonal`
- `POST /fetch` - 抓取当季新番
- `POST /refresh` - 刷新当季新番
- `POST /smart-update` - 智能更新当季新番

### 管理模块 `/api/admin`
- `POST /cache/clear-all` - 清除所有缓存

## 🗄️ 数据库设计

### 核心表结构

- **user** - 用户表
- **anime** - 动漫主表
- **anime_name_mapping** - 动漫名称映射表（中文标题）
- **anime_schedule** - 动漫排期表（当季新番）
- **character** - 角色表
- **anime_comment** - 动漫评论表
- **comment_reply** - 评论回复表
- **character_comment** - 角色评论表
- **character_comment_reply** - 角色评论回复表
- **user_comment_like** - 用户评论点赞记录
- **character_comment_like** - 用户角色评论点赞记录
- **user_anime** - 用户追番记录表
- **watch_history** - 观看历史表
- **user_favorite_character** - 用户喜欢角色表

## ⚙️ 配置说明

### 多环境配置

项目支持开发环境和生产环境配置分离：

- `application-dev.yaml` - 开发环境
- `application-prod.yaml` - 生产环境

通过 `spring.profiles.active` 切换环境。

### Redis 缓存策略

系统使用 Redis 缓存以下数据：
- 动漫列表分页数据
- 动漫详情数据
- 角色列表分页数据
- 角色详情数据
- 轮播图数据
- 当季新番数据

缓存键遵循统一规范，支持按维度清除。

### 定时任务

系统包含以下定时任务：
- **当季新番智能更新** - 每天凌晨 00:00 自动执行

## 🔒 安全机制

- **JWT 认证** - 基于 Token 的身份验证
- **密码加密** - BCrypt 加密存储用户密码
- **CORS 配置** - 跨域请求控制
- **参数校验** - 使用 Jakarta Validation 进行输入验证
- **权限控制** - 读写分离，公开读操作，写操作需登录

## 📝 开发规范

- 使用 Lombok 简化代码
- 统一返回格式 `Result<T>`
- 异常统一处理 `GlobalExceptionHandler`
- 日志记录使用 SLF4J
- 遵循 RESTful API 设计规范

## 🧪 测试

运行单元测试：
```bash
mvn test
```

## 📦 部署

### 打包
```bash
mvn clean package -DskipTests
```

### 运行 JAR
```bash
java -jar target/backend-0.0.1-SNAPSHOT.jar
```

### Docker 部署（可选）
```dockerfile
FROM openjdk:17-jdk-slim
COPY target/backend-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 👥 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 发送邮件至项目维护者

---

**注意**: 本项目仅供学习交流使用，请勿用于商业用途。
