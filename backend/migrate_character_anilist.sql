-- ============================================================
-- 角色抓取数据源迁移：Jikan(MAL) → AniList
-- ============================================================
-- 背景：
--   原角色抓取使用 Jikan API（api.jikan.moe）读取 MyAnimeList 角色，
--   该服务已不可用。迁移到 AniList 后发现一个关键差异：
--
--     **AniList 的角色对象不提供 MAL ID**，只有 AniList 自己的角色ID
--     （通过 GraphQL 实测确认：Character 类型上不存在 idMal 字段）。
--
--   而 anime_character.mal_id 是 NOT NULL UNIQUE 列。若直接把 AniList ID
--   写进 mal_id，列名与实际含义不符，将来按 MAL ID 匹配必然出错。
--
-- 因此本次迁移：
--   1. 新增 anilist_id 列 —— 当前数据源的角色ID，新数据的唯一去重键
--   2. 把 mal_id 改为可空 —— AniList 数据没有 MAL ID，硬塞占位值毫无意义
--   3. 历史数据保留原样，mal_id 仍是真实 MAL 角色ID，anilist_id 为空
--
-- 使用（可重复执行）：
--   mysql -u root -p backend_asagami < migrate_character_anilist.sql
-- ============================================================

USE backend_asagami;

-- ------------------------------------------------------------
-- 1. 新增 anilist_id 列（幂等）
-- ------------------------------------------------------------
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = 'anime_character'
       AND COLUMN_NAME = 'anilist_id'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE anime_character ADD COLUMN anilist_id INT NULL COMMENT ''AniList角色ID（当前数据源）''',
    'SELECT ''anilist_id 已存在，跳过'' AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------
-- 2. 新增唯一索引（幂等）
--    MySQL 唯一索引允许多个 NULL，历史行不受影响
-- ------------------------------------------------------------
SET @idx_exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = 'anime_character'
       AND INDEX_NAME = 'uk_character_anilist_id'
);
SET @sql := IF(@idx_exists = 0,
    'ALTER TABLE anime_character ADD UNIQUE KEY uk_character_anilist_id (anilist_id)',
    'SELECT ''uk_character_anilist_id 已存在，跳过'' AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------
-- 3. mal_id 允许为空（幂等）
--    AniList 数据没有 MAL 角色ID，该列必须可空
-- ------------------------------------------------------------
SET @nullable := (
    SELECT IS_NULLABLE FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = 'anime_character'
       AND COLUMN_NAME = 'mal_id'
);
SET @sql := IF(@nullable = 'NO',
    'ALTER TABLE anime_character MODIFY COLUMN mal_id INT NULL COMMENT ''MAL角色ID（历史数据，AniList 数据源下为空）''',
    'SELECT ''mal_id 已可空，跳过'' AS msg');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------
-- 4. 执行结果
-- ------------------------------------------------------------
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_COMMENT
  FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE()
   AND TABLE_NAME = 'anime_character'
   AND COLUMN_NAME IN ('id', 'mal_id', 'anilist_id', 'name', 'name_jp', 'favorites')
 ORDER BY ORDINAL_POSITION;

-- 提示：如需清空重抓（历史 MAL 数据不会被 AniList 去重逻辑复用）
--   TRUNCATE TABLE anime_character;
