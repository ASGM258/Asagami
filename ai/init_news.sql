-- ============================================================
-- 动漫资讯模块 - MySQL 建表脚本
-- ============================================================
-- 说明：资讯数据归本 AI 服务（Python）写入，Java 后端如需读取
--       可直接查同一张表。
--
--   * news             —— 资讯主表（供前端列表/详情接口读取）
--   * news_review_log  —— 审核轨迹（每次审核的判定与原因）
--
-- 使用：
--   mysql -u root -p backend_asagami < init_news.sql
--   （表结构也会在服务启动时幂等创建）
-- ============================================================

-- ------------------------------------------------------------
-- 1. 资讯主表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news (
    id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '资讯ID',
    title             VARCHAR(500) NOT NULL                COMMENT '标题（中文）',
    summary           TEXT         NULL                    COMMENT '摘要（列表页展示）',
    content           LONGTEXT     NULL                    COMMENT '正文（纯文本或HTML）',
    cover_image       VARCHAR(1000) NULL                   COMMENT '封面图URL',
    category          VARCHAR(64)  NULL                    COMMENT '分类：动画/漫画/声优/游戏/活动',
    source            VARCHAR(128) NULL                    COMMENT '来源（如：AniNewsAPI / ANN）',
    author            VARCHAR(128) NULL                    COMMENT '发布者',
    publish_time      DATETIME     NULL                    COMMENT '发布时间',
    tags              VARCHAR(500) NULL                    COMMENT '标签，英文逗号分隔',
    view_count        INT          NOT NULL DEFAULT 0      COMMENT '阅读量',
    source_url        VARCHAR(1000) NULL                   COMMENT '原文链接',
    source_uid        VARCHAR(255) NULL                    COMMENT '来源内唯一标识，用于去重',
    language          VARCHAR(16)  NOT NULL DEFAULT 'zh'   COMMENT '内容语言',
    status            VARCHAR(16)  NOT NULL DEFAULT 'published'
                      COMMENT '状态：published-已发布 / rejected-审核未通过',
    review_attempts   INT          NOT NULL DEFAULT 0      COMMENT '审核尝试次数（含重做）',
    review_reason     VARCHAR(1000) NULL                   COMMENT '最近一次审核意见',
    related_anime_id  BIGINT       NULL                    COMMENT '关联动漫ID（可空）',
    related_anime_title VARCHAR(500) NULL                  COMMENT '关联动漫标题',
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                      ON UPDATE CURRENT_TIMESTAMP          COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_news_source_uid (source_uid),
    KEY idx_news_status_publish (status, publish_time),
    KEY idx_news_category (category),
    KEY idx_news_publish_time (publish_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='动漫资讯表';

-- ------------------------------------------------------------
-- 2. 审核轨迹表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_review_log (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    source_uid  VARCHAR(255) NOT NULL             COMMENT '关联资讯的来源唯一标识',
    attempt     INT          NOT NULL DEFAULT 1   COMMENT '第几次审核',
    passed      TINYINT(1)   NOT NULL DEFAULT 0   COMMENT '是否通过：1-通过, 0-不通过',
    reason      VARCHAR(1000) NULL                COMMENT '审核意见/不通过原因',
    agent       VARCHAR(64)  NULL                 COMMENT '执行审核的 agent 名称',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_review_source_uid (source_uid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资讯审核轨迹表';

-- ------------------------------------------------------------
-- 3. 字段与状态说明
-- ------------------------------------------------------------
-- status 取值：
--   published —— 审核通过，前端接口会返回
--   rejected  —— 连续 3 次审核未通过，前端不展示，但保留记录与原因便于排查
--
-- 去重策略：
--   source_uid 唯一索引。取来源条目的 guid/link，缺失时退化为
--   md5(标题 + 发布时间)，保证同一篇资讯重复抓取不会产生多条记录。
--
-- 阅读量：
--   view_count 目前不在详情接口自增（避免爬虫/刷新刷量），
--   如需统计可在详情接口显式累加。
