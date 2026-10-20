"""
资讯数据访问层

负责 news / news_review_log 两张表的读写。
表结构见 init_news.sql，服务启动时也会幂等创建。
"""

import logging
from typing import Any

from app.db.mysql import get_mysql_client

logger = logging.getLogger(__name__)

# 允许的分类（前端筛选标签用）
CATEGORY_NAMES = ["动画", "漫画", "声优", "游戏", "活动"]

STATUS_PUBLISHED = "published"
STATUS_REJECTED = "rejected"


class NewsRepository:
    """资讯仓储"""

    # ==================== 建表 ====================

    @staticmethod
    def ensure_schema() -> None:
        """幂等创建资讯相关表结构"""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS news (
                id                BIGINT       NOT NULL AUTO_INCREMENT,
                title             VARCHAR(500) NOT NULL,
                summary           TEXT         NULL,
                content           LONGTEXT     NULL,
                cover_image       VARCHAR(1000) NULL,
                category          VARCHAR(64)  NULL,
                source            VARCHAR(128) NULL,
                author            VARCHAR(128) NULL,
                publish_time      DATETIME     NULL,
                tags              VARCHAR(500) NULL,
                view_count        INT          NOT NULL DEFAULT 0,
                source_url        VARCHAR(1000) NULL,
                source_uid        VARCHAR(255) NULL,
                language          VARCHAR(16)  NOT NULL DEFAULT 'zh',
                status            VARCHAR(16)  NOT NULL DEFAULT 'published',
                review_attempts   INT          NOT NULL DEFAULT 0,
                review_reason     VARCHAR(1000) NULL,
                related_anime_id  BIGINT       NULL,
                related_anime_title VARCHAR(500) NULL,
                content_enriched  TINYINT(1)   NOT NULL DEFAULT 0,
                created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uk_news_source_uid (source_uid),
                KEY idx_news_status_publish (status, publish_time),
                KEY idx_news_category (category),
                KEY idx_news_publish_time (publish_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS news_review_log (
                id          BIGINT       NOT NULL AUTO_INCREMENT,
                source_uid  VARCHAR(255) NOT NULL,
                attempt     INT          NOT NULL DEFAULT 1,
                passed      TINYINT(1)   NOT NULL DEFAULT 0,
                reason      VARCHAR(1000) NULL,
                agent       VARCHAR(64)  NULL,
                created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_review_source_uid (source_uid)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]

        try:
            client = get_mysql_client()
            with client.cursor(commit=True) as cur:
                for ddl in statements:
                    cur.execute(ddl)
                # 老库补列：正文补全功能上线后新增的标记位。
                # MySQL 的 ADD COLUMN 不支持 IF NOT EXISTS，先查 information_schema
                cur.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'news' "
                    "AND COLUMN_NAME = 'content_enriched'"
                )
                row = cur.fetchone()
                exists = (row or {}).get("c") if isinstance(row, dict) else (row[0] if row else 0)
                if not exists:
                    cur.execute(
                        "ALTER TABLE news ADD COLUMN content_enriched TINYINT(1) "
                        "NOT NULL DEFAULT 0"
                    )
                    logger.info("已为 news 表补充 content_enriched 列")
            logger.info("资讯表结构已就绪（news / news_review_log）")
        except Exception as exc:  # noqa: BLE001 - 建表失败不阻断启动
            logger.error("创建资讯表失败: %s", exc)

    # ==================== 列表 / 详情 ====================

    @staticmethod
    def count_published(category: str | None = None, keyword: str | None = None) -> int:
        """统计可发布资讯数量"""
        where = ["status = %s"]
        params: list[Any] = [STATUS_PUBLISHED]

        if category:
            where.append("category = %s")
            params.append(category)
        if keyword:
            where.append("(title LIKE %s OR summary LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        sql = f"SELECT COUNT(*) AS total FROM news WHERE {' AND '.join(where)}"

        try:
            row = get_mysql_client().execute_query(sql, tuple(params), fetch_one=True)
            return int(row["total"]) if row else 0
        except Exception as exc:  # noqa: BLE001
            logger.error("统计资讯数量失败: %s", exc)
            return 0

    @staticmethod
    def list_published(
        page_num: int,
        page_size: int,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[dict]:
        """
        分页查询可发布资讯（按发布时间倒序）

        Returns:
            列表项字段与前端 NewsItem 对齐
        """
        where = ["status = %s"]
        params: list[Any] = [STATUS_PUBLISHED]

        if category:
            where.append("category = %s")
            params.append(category)
        if keyword:
            where.append("(title LIKE %s OR summary LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        sql = f"""
            SELECT id, title, cover_image, summary, category, source,
                   author, publish_time, tags, view_count
              FROM news
             WHERE {' AND '.join(where)}
             ORDER BY publish_time DESC, id DESC
             LIMIT %s OFFSET %s
        """
        # 显式转 int，避免 LIMIT/OFFSET 被当作字符串导致语法错误
        params.extend([int(page_size), int((page_num - 1) * page_size)])

        try:
            rows = get_mysql_client().execute_query(sql, tuple(params)) or []
        except Exception as exc:  # noqa: BLE001
            logger.error("查询资讯列表失败: %s", exc)
            return []

        return [NewsRepository._to_list_item(row) for row in rows]

    @staticmethod
    def get_published_detail(news_id: int) -> dict | None:
        """
        查询单条已发布资讯详情

        Returns:
            详情字段与前端 NewsDetail 对齐；不存在返回 None
        """
        sql = """
            SELECT id, title, cover_image, summary, category, source, author,
                   publish_time, tags, view_count, content,
                   related_anime_id, related_anime_title
              FROM news
             WHERE id = %s AND status = %s
        """
        try:
            row = get_mysql_client().execute_query(
                sql, (news_id, STATUS_PUBLISHED), fetch_one=True
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("查询资讯详情失败: %s", exc)
            return None

        if not row:
            return None

        detail = NewsRepository._to_list_item(row)
        detail["content"] = row.get("content") or ""
        detail["relatedAnimeId"] = row.get("related_anime_id")
        detail["relatedAnimeTitle"] = row.get("related_anime_title")
        return detail

    @staticmethod
    def category_counts() -> dict[str, int]:
        """统计各分类下已发布资讯数量"""
        sql = """
            SELECT category, COUNT(*) AS total
              FROM news
             WHERE status = %s AND category IS NOT NULL AND category <> ''
             GROUP BY category
        """
        try:
            rows = get_mysql_client().execute_query(sql, (STATUS_PUBLISHED,)) or []
        except Exception as exc:  # noqa: BLE001
            logger.error("统计资讯分类失败: %s", exc)
            return {}

        return {row["category"]: int(row["total"]) for row in rows}

    # ==================== 写入 ====================

    @staticmethod
    def existing_source_uids(source_uids: list[str]) -> set[str]:
        """
        查询给定 source_uid 中已入库的部分

        用于判断本次抓取有多少是新内容：来源（尤其 RSS）每次返回的条目高度重合，
        已存在的条目会被跳过，因此需要据此放大抓取量。

        Args:
            source_uids: 待检查的来源唯一标识

        Returns:
            已存在的标识集合
        """
        if not source_uids:
            return set()

        placeholders = ",".join(["%s"] * len(source_uids))
        sql = f"SELECT source_uid FROM news WHERE source_uid IN ({placeholders})"

        try:
            rows = get_mysql_client().execute_query(sql, tuple(source_uids)) or []
            return {row["source_uid"] for row in rows}
        except Exception as exc:  # noqa: BLE001 - 查询失败不影响主流程
            logger.error("查询已存在资讯失败: %s", exc)
            return set()

    @staticmethod
    def truncated_source_uids(source_uids: list[str], min_chars: int) -> set[str]:
        """
        查询给定 source_uid 中「正文过短」的部分

        用于修复历史数据：正文补全功能上线之前入库的条目，正文只是 RSS 摘要
        （约 200~400 字），内容被截断。这类条目因为 source_uid 已存在会被
        去重逻辑跳过，永远无法更新，因此需要单独识别出来重跑流水线。

        Args:
            source_uids: 待检查的来源唯一标识
            min_chars: 正文字符数低于该值即视为残缺

        Returns:
            残缺条目的标识集合
        """
        if not source_uids:
            return set()

        placeholders = ",".join(["%s"] * len(source_uids))
        sql = (
            f"SELECT source_uid FROM news "
            f"WHERE source_uid IN ({placeholders}) "
            f"AND CHAR_LENGTH(IFNULL(content, '')) < %s "
            # 已回源补全过的条目不再重复处理（短文章本身就短，否则会每轮重跑）
            f"AND IFNULL(content_enriched, 0) = 0"
        )

        try:
            rows = get_mysql_client().execute_query(
                sql, tuple(source_uids) + (int(min_chars),)
            ) or []
            return {row["source_uid"] for row in rows}
        except Exception as exc:  # noqa: BLE001 - 查询失败不影响主流程
            logger.error("查询残缺资讯失败: %s", exc)
            return set()

    @staticmethod
    def short_content_items(min_chars: int, limit: int = 20) -> list[dict]:
        """
        查询正文过短的已发布资讯（用于修复历史数据）

        正文补全功能上线前入库的条目，正文只是 RSS 摘要（200~400 字），
        而且这些条目大多已经不在当前 feed 里，靠「重新抓取」碰不到它们，
        因此需要按库里的记录逐条回源补全。

        Args:
            min_chars: 正文字符数低于该值即视为残缺
            limit: 本次最多返回多少条

        Returns:
            [{source_uid, title, source, source_url, contentLength}, ...]
        """
        sql = (
            "SELECT source_uid, title, source, source_url, "
            "       CHAR_LENGTH(IFNULL(content, '')) AS contentLength "
            "FROM news "
            "WHERE CHAR_LENGTH(IFNULL(content, '')) < %s "
            "  AND IFNULL(content_enriched, 0) = 0 "
            "  AND source_url IS NOT NULL AND source_url <> '' "
            "ORDER BY id DESC LIMIT %s"
        )

        try:
            return get_mysql_client().execute_query(sql, (int(min_chars), int(limit))) or []
        except Exception as exc:  # noqa: BLE001
            logger.error("查询正文残缺资讯失败: %s", exc)
            return []

    @staticmethod
    def upsert(item: dict, status: str = STATUS_PUBLISHED) -> bool:
        """
        写入或更新一条资讯（按 source_uid 去重）

        Args:
            item: 归一化后的条目（含 stage / attempts / review_reason 等工作流字段）
            status: published / rejected

        Returns:
            是否写入成功
        """
        sql = """
            INSERT INTO news (
                title, summary, content, cover_image, category, source, author,
                publish_time, tags, source_url, source_uid, language, status,
                review_attempts, review_reason, related_anime_id, related_anime_title,
                content_enriched
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                summary = VALUES(summary),
                content = VALUES(content),
                cover_image = VALUES(cover_image),
                category = VALUES(category),
                source = VALUES(source),
                author = VALUES(author),
                publish_time = VALUES(publish_time),
                tags = VALUES(tags),
                source_url = VALUES(source_url),
                language = VALUES(language),
                status = VALUES(status),
                review_attempts = VALUES(review_attempts),
                review_reason = VALUES(review_reason),
                related_anime_id = VALUES(related_anime_id),
                related_anime_title = VALUES(related_anime_title),
                content_enriched = GREATEST(content_enriched, VALUES(content_enriched))
        """

        publish_time = item.get("publish_time") or None
        tags = item.get("tags") or []
        tags_text = ",".join(tags) if isinstance(tags, list) else str(tags)

        # 封面缺失时留空（前端对空封面有占位处理）
        cover_image = item.get("cover_image") or ""

        params = (
            (item.get("title") or "")[:500],
            item.get("summary") or None,
            item.get("content") or None,
            # 注意：先用 or "" 兜底再切片，None 不能直接切片
            cover_image[:1000] or None,
            (item.get("category") or "")[:64] or None,
            (item.get("source") or "")[:128] or None,
            (item.get("author") or "")[:128] or None,
            publish_time,
            (tags_text or "")[:500] or None,
            (item.get("source_url") or "")[:1000] or None,
            (item.get("source_uid") or "")[:255] or None,
            (item.get("language") or "zh")[:16],
            status,
            int(item.get("attempts") or 0),
            (item.get("review_reason") or "")[:1000] or None,
            item.get("related_anime_id"),
            (item.get("related_anime_title") or "")[:500] or None,
            1 if item.get("content_enriched") else 0,
        )

        try:
            affected = get_mysql_client().execute_update(sql, params)
            return affected > 0
        except Exception as exc:  # noqa: BLE001
            logger.error("写入资讯失败 uid=%s: %s", item.get("source_uid"), exc)
            return False

    @staticmethod
    def replace_review_logs(source_uid: str, logs: list[dict]) -> None:
        """
        重写某条资讯的审核轨迹

        Args:
            source_uid: 来源唯一标识
            logs: [{attempt, passed, reason, agent}, ...]
        """
        try:
            client = get_mysql_client()
            with client.cursor(commit=True) as cur:
                cur.execute(
                    "DELETE FROM news_review_log WHERE source_uid = %s", (source_uid,)
                )
                for entry in logs:
                    cur.execute(
                        """
                        INSERT INTO news_review_log
                            (source_uid, attempt, passed, reason, agent)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            source_uid[:255],
                            int(entry.get("attempt") or 1),
                            1 if entry.get("passed") else 0,
                            (entry.get("reason") or "")[:1000] or None,
                            (entry.get("agent") or "review")[:64],
                        ),
                    )
        except Exception as exc:  # noqa: BLE001 - 轨迹写入失败不影响主流程
            logger.error("写入审核轨迹失败 uid=%s: %s", source_uid, exc)

    # ==================== 关联动漫 ====================

    @staticmethod
    def find_related_anime(text: str) -> tuple[int | None, str | None]:
        """
        依据文本尝试匹配 anime 表中的动漫

        仅当确实命中时返回 ID，避免写入不存在的外键。
        匹配策略：取文本中长度 >= 3 的连续片段做 LIKE 匹配（取最长命中）。

        Returns:
            (anime_id, anime_title)，未命中返回 (None, None)
        """
        if not text:
            return None, None

        # 按常见分隔符切分，取出可能作为作品名的片段
        candidates = [
            seg.strip()
            for seg in text.replace("《", "|").replace("》", "|")
            .replace("「", "|").replace("」", "|")
            .replace("【", "|").replace("】", "|")
            .replace("：", "|").replace(":", "|")
            .split("|")
            if len(seg.strip()) >= 3
        ]
        # 片段过长时截断，避免 LIKE 过宽
        candidates = sorted({c[:50] for c in candidates}, key=len, reverse=True)[:5]

        for candidate in candidates:
            try:
                row = get_mysql_client().execute_query(
                    "SELECT id, title FROM anime WHERE title LIKE %s LIMIT 1",
                    (f"%{candidate}%",),
                    fetch_one=True,
                )
            except Exception:  # noqa: BLE001 - 关联失败不影响资讯入库
                return None, None

            if row:
                return int(row["id"]), row.get("title")

        return None, None

    # ==================== 字段映射 ====================

    @staticmethod
    def _to_list_item(row: dict) -> dict:
        """
        数据库行 → 前端 NewsItem 结构

        字段名使用驼峰，与 src/types/news.ts 严格对齐。
        """
        publish_time = row.get("publish_time")

        tags_raw = row.get("tags") or ""
        tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

        return {
            "id": row.get("id"),
            "title": row.get("title") or "",
            "coverImage": row.get("cover_image") or "",
            "summary": row.get("summary") or "",
            "category": row.get("category") or "",
            "source": row.get("source") or "",
            "author": row.get("author") or "",
            # 输出 ISO 形式，前端 formatDateTime 解析在 WebKit 下更可靠
            "publishTime": publish_time.strftime("%Y-%m-%dT%H:%M:%S")
            if hasattr(publish_time, "strftime")
            else (str(publish_time) if publish_time else ""),
            "tags": tags,
            "viewCount": int(row.get("view_count") or 0),
        }
