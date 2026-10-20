-- ============================================================
-- 动漫AI问答系统 - PostgreSQL 初始化脚本
-- ============================================================
-- 说明：会话元数据与对话状态现在全部存放在 PostgreSQL。
--
--   * chat_sessions  —— 会话元数据（本脚本创建）
--                       标题、归属用户、软删除标记
--   * checkpoints / checkpoint_blobs / checkpoint_writes /
--     checkpoint_migrations
--                    —— LangGraph 检查点表，保存完整对话状态与消息，
--                       由 PostgresSaver.setup() 在服务启动时自动创建，
--                       无需手工执行。
--
-- 使用步骤：
--   1) 创建数据库（表结构由程序自动创建）
--        psql -U postgres -c "CREATE DATABASE anime_ai;"
--   2) 执行本脚本创建会话元数据表（也可省略，程序启动时会幂等创建）
--        psql -U postgres -d anime_ai -f init_conversations.sql
--   3) 在 ai/.env 中配置
--        AI_DATABASE_URL=postgresql://postgres:密码@localhost:5432/anime_ai
-- ============================================================

-- ------------------------------------------------------------
-- 1. 会话元数据表
--    session_id 同时作为 LangGraph 的 thread_id，两者一一对应
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(64)  PRIMARY KEY,
    user_id    BIGINT       NOT NULL,
    title      VARCHAR(255) NOT NULL DEFAULT '新会话',
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted SMALLINT     NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------
-- 2. 索引
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id    ON chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions (created_at);

-- ------------------------------------------------------------
-- 3. 字段说明
-- ------------------------------------------------------------
COMMENT ON TABLE  chat_sessions            IS '聊天会话元数据表';
COMMENT ON COLUMN chat_sessions.session_id IS '会话唯一标识，同时作为 LangGraph thread_id';
COMMENT ON COLUMN chat_sessions.user_id    IS '归属用户ID';
COMMENT ON COLUMN chat_sessions.title      IS '会话标题，可取首个问题的前20个字符';
COMMENT ON COLUMN chat_sessions.created_at IS '创建时间';
COMMENT ON COLUMN chat_sessions.updated_at IS '最后活跃时间，每轮对话后刷新';
COMMENT ON COLUMN chat_sessions.is_deleted IS '软删除标记: 0-正常, 1-已删除';

-- ------------------------------------------------------------
-- 4. 迁移自旧版 MySQL 的说明
-- ------------------------------------------------------------
-- 旧版使用 MySQL 的 chat_sessions / chat_messages 两张表，
-- 新版改为：
--   * 会话元数据  -> 本表的 chat_sessions
--   * 消息与对话状态 -> LangGraph 检查点表（自动创建）
-- 旧表数据不迁移，可按需手工保留备份。
