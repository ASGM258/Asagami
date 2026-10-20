"""
资讯服务

两个职责：
1. 运行资讯智能体工作流（抓取 → 翻译 → 摘要 → 审核），并把结果落库
2. 为前端提供列表 / 详情 / 分类查询，返回结构严格对齐前端契约
"""

import logging
import threading
from datetime import datetime
from typing import Any

from app.config import Settings
from app.news.fetchers import NewsFetcher, build_default_fetcher
from app.news.graph import build_news_workflow
from app.news.repository import (
    CATEGORY_NAMES,
    STATUS_PUBLISHED,
    STATUS_REJECTED,
    NewsRepository,
)
from app.news.state import STAGE_APPROVED, STAGE_REJECTED
from app.utils.ids import new_run_id

logger = logging.getLogger(__name__)


class NewsService:
    """资讯业务服务"""

    def __init__(self, settings: Settings, fetcher: NewsFetcher | None = None) -> None:
        self._settings = settings
        self._fetcher = fetcher or build_default_fetcher(settings)
        self._workflow = build_news_workflow(settings, self._fetcher)
        #: 工作流互斥：抓取耗时较长，不能叠加执行（重复调用模型、互相覆盖数据）
        self._run_lock = threading.Lock()
        self._running = False
        self._started_at: str | None = None
        self._finished_at: str | None = None
        self._last_summary: dict[str, Any] | None = None

    # ==================== 运行状态 ====================

    def is_running(self) -> bool:
        """是否有抓取任务正在执行"""
        return self._running

    def run_status(self) -> dict[str, Any]:
        """
        查询运行状态（供前端轮询）

        Returns:
            {running, startedAt, finishedAt, lastRun}
        """
        return {
            "running": self._running,
            "startedAt": self._started_at,
            "finishedAt": self._finished_at,
            "lastRun": self._last_summary,
        }

    # ==================== 启动初始化 ====================

    @staticmethod
    def ensure_schema() -> None:
        """幂等创建资讯表"""
        NewsRepository.ensure_schema()

    # ==================== 工作流运行 ====================

    def run_workflow(self, limit: int | None = None, repair: bool = False) -> dict[str, Any]:
        """
        执行一次抓取-翻译-摘要-审核工作流，并把结果写入 MySQL

        Args:
            limit: 本次抓取条数上限，缺省取配置值
            repair: 是否顺带修复已入库但正文残缺的条目

        Returns:
            运行摘要：{
                run_id, total, published, rejected, repaired,
                items: [{source_uid, title, status, attempts, reason}], logs
            }
        """
        # 互斥：同一时刻只允许一个工作流（并发跑会重复调用模型、互相覆盖）
        if not self._run_lock.acquire(blocking=False):
            logger.warning("已有资讯工作流在运行，本次请求被忽略")
            return {
                "run_id": "",
                "total": 0,
                "published": 0,
                "rejected": 0,
                "repaired": 0,
                "items": [],
                "logs": ["已有任务在运行中"],
            }

        run_id = new_run_id()
        effective_limit = int(limit or self._settings.news_fetch_limit)
        self._running = True
        self._started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._finished_at = None

        logger.info(
            "========== 资讯工作流开始 run_id=%s limit=%d repair=%s ==========",
            run_id,
            effective_limit,
            repair,
        )

        try:
            final_state = self._workflow.invoke(
                {
                    "run_id": run_id,
                    "limit": effective_limit,
                    "repair": bool(repair),
                    "items": {},
                    "log": [],
                }
            )
        finally:
            self._running = False
            self._run_lock.release()

        items: dict[str, dict] = final_state.get("items") or {}
        published: list[dict] = []
        rejected: list[dict] = []

        for item in items.values():
            stage = item.get("stage")
            if stage == STAGE_APPROVED:
                published.append(item)
            elif stage == STAGE_REJECTED:
                rejected.append(item)
            else:
                # 异常情况下未走到终态的条目，按未通过处理，避免半成品对外可见
                logger.warning(
                    "条目未达终态，按未通过处理: uid=%s stage=%s",
                    item.get("source_uid"),
                    stage,
                )
                item["review_reason"] = item.get("review_reason") or "工作流未完成审核"
                rejected.append(item)

        self._persist(published, STATUS_PUBLISHED)
        self._persist(rejected, STATUS_REJECTED)

        summary = {
            "run_id": run_id,
            "total": len(items),
            "published": len(published),
            "rejected": len(rejected),
            "repair": bool(repair),
            # 字段始终存在，前端不必区分 repair 开关（否则 lastRun 形状不稳定）
            "repaired": 0,
            "repairChecked": 0,
            "repairFailed": 0,
            "items": [
                {
                    "source_uid": item.get("source_uid"),
                    "title": item.get("title"),
                    "status": STATUS_PUBLISHED
                    if item.get("stage") == STAGE_APPROVED
                    else STATUS_REJECTED,
                    "attempts": int(item.get("attempts") or 0),
                    "reason": item.get("review_reason") or "",
                }
                for item in list(published) + list(rejected)
            ],
            "logs": final_state.get("log") or [],
        }

        # 修复历史数据：早期入库的正文只是 RSS 摘要，且大多已掉出当前 feed，
        # 靠「重新抓取」碰不到，必须按库里的记录逐条回源补全
        if repair:
            try:
                repair_result = self.repair_truncated()
                summary["repaired"] = repair_result["repaired"]
                summary["repairChecked"] = repair_result["checked"]
                summary["repairFailed"] = repair_result["failed"]
                summary["published"] += repair_result["repaired"]
                summary["logs"] = list(summary["logs"]) + [
                    f"[正文修复] 检查 {repair_result['checked']} 条，"
                    f"修复 {repair_result['repaired']} 条，失败 {repair_result['failed']} 条"
                ]
            except Exception as exc:  # noqa: BLE001 - 修复失败不影响本次抓取结果
                logger.exception("正文修复失败: %s", exc)
                summary["repaired"] = 0
                summary["logs"] = list(summary["logs"]) + [f"[正文修复] 失败: {exc}"]

        # 记录运行结果供前端轮询
        self._last_summary = summary
        self._finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(
            "========== 资讯工作流结束 run_id=%s 可发布=%d 拒绝=%d ==========",
            run_id,
            len(published),
            len(rejected),
        )
        return summary

    def repair_truncated(self, limit: int | None = None) -> dict[str, Any]:
        """
        修复正文残缺的历史资讯（按库驱动，不依赖 feed）

        早期入库的条目正文只是 RSS 摘要（被截断），而且大多已经掉出当前 feed，
        「重新抓取」碰不到它们。这里按库里的记录逐条回源：
            重新抓详情页 → 强制翻译 → 重新摘要 → 重新审核 → upsert 覆盖

        Args:
            limit: 本次最多修复多少条

        Returns:
            {checked, repaired, failed, items}
        """
        # 延迟导入：nodes 会引入 LLM 依赖，避免 service 顶层变重
        from app.news import nodes as N
        from app.news.fetchers import NewsItem, enrich_items

        min_chars = int(self._settings.news_enrich_min_chars)
        cap = int(limit or self._settings.news_enrich_limit)
        rows = NewsRepository.short_content_items(min_chars, cap)

        result: dict[str, Any] = {
            "checked": len(rows),
            "repaired": 0,
            "failed": 0,
            "items": [],
        }
        if not rows:
            logger.info("[正文修复] 没有需要修复的资讯（阈值 %d 字）", min_chars)
            return result

        logger.info("[正文修复] 待修复 %d 条（正文 < %d 字）", len(rows), min_chars)

        for row in rows:
            uid = str(row.get("source_uid") or "")
            title = str(row.get("title") or "")
            try:
                item = NewsItem(
                    source_uid=uid,
                    title=title,
                    content="",
                    summary="",
                    source=str(row.get("source") or ""),
                    source_url=str(row.get("source_url") or ""),
                )

                # 1) 回源补全正文（English 全文）
                enrich_items([item], self._settings)
                if not (item.content or "").strip():
                    logger.warning("[正文修复] 回源失败，跳过: uid=%s", uid)
                    result["failed"] += 1
                    continue

                # 2) 强制翻译（标题已是中文，不能按"含中文就跳过"处理）
                item = N._translate_item(item, self._settings, force=True)
                # 3) 重新摘要（含敏感信息清洗）
                item = N._summarize_item(item, self._settings)
                item.stage = N.STAGE_SUMMARIZED
                # 4) 重新审核
                passed, reason = N._review_item(item, self._settings)
                item.review_reason = reason
                item.review_feedback = reason
                item.review_history = list(item.review_history) + [
                    {"attempt": max(item.attempts, 1), "passed": bool(passed), "reason": reason}
                ]
                item.stage = STAGE_APPROVED if passed else STAGE_REJECTED

                # 5) 覆盖写回（upsert 的 ON DUPLICATE KEY UPDATE 会更新 content）
                # _persist 接收的是 dict，不是 NewsItem
                self._persist([item.to_dict()], STATUS_PUBLISHED if passed else STATUS_REJECTED)

                result["repaired"] += 1
                result["items"].append(
                    {
                        "source_uid": uid,
                        "title": item.title,
                        "contentLength": len(item.content or ""),
                        "passed": bool(passed),
                    }
                )
                logger.info(
                    "[正文修复] 完成: uid=%s %d -> %d 字, 审核=%s",
                    uid,
                    int(row.get("contentLength") or 0),
                    len(item.content or ""),
                    "通过" if passed else "未通过",
                )
            except Exception as exc:  # noqa: BLE001 - 单条失败不影响其余条目
                logger.exception("[正文修复] 处理失败 uid=%s: %s", uid, exc)
                result["failed"] += 1

        logger.info(
            "[正文修复] 结束: 检查 %d 条，修复 %d 条，失败 %d 条",
            result["checked"],
            result["repaired"],
            result["failed"],
        )
        return result

    def _persist(self, items: list[dict], status: str) -> None:
        """落库：写入资讯主表并记录审核轨迹"""
        for item in items:
            # 补充关联动漫（仅在 anime 表确实存在时建立关联）
            anime_id, anime_title = NewsRepository.find_related_anime(
                f"{item.get('title') or ''} {item.get('summary') or ''}"
            )
            item["related_anime_id"] = anime_id
            item["related_anime_title"] = anime_title

            NewsRepository.upsert(item, status=status)

            # 审核轨迹：写入真实的逐次判定记录
            # 注意：不能按最终状态统一回填 passed，否则会掩盖「先失败后通过」的真实过程
            logs = self._build_review_logs(item)
            NewsRepository.replace_review_logs(item.get("source_uid") or "", logs)

    @staticmethod
    def _build_review_logs(item: dict) -> list[dict]:
        """
        构造审核轨迹

        优先使用工作流记录的逐次判定（review_history）；
        缺失时退化为按 attempts 生成占位记录，仅最后一条标记最终结果。
        """
        history = item.get("review_history") or []
        if history:
            return [
                {
                    "attempt": int(entry.get("attempt") or index + 1),
                    "passed": bool(entry.get("passed")),
                    "reason": entry.get("reason") or "",
                    "agent": "review",
                }
                for index, entry in enumerate(history)
            ]

        attempts = max(int(item.get("attempts") or 1), 1)
        reason = item.get("review_reason") or ""
        return [
            {
                "attempt": index + 1,
                "passed": index == attempts - 1 and item.get("stage") == STAGE_APPROVED,
                "reason": reason if index == attempts - 1 else "",
                "agent": "review",
            }
            for index in range(attempts)
        ]

    # ==================== 前端查询接口 ====================

    def list_news(
        self,
        page_num: int = 1,
        page_size: int = 10,
        category: str | None = None,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        """
        分页查询资讯列表

        Returns:
            与前端 PageResponse<NewsItem> 对齐的字典：
            {total, pages, pageNum, pageSize, list}
        """
        page_num = max(int(page_num or 1), 1)
        page_size = max(int(page_size or 10), 1)

        # 分类为空或 'all' 视为不筛选
        normalized_category = None
        if category and category not in ("all", "全部"):
            normalized_category = category

        total = NewsRepository.count_published(normalized_category, keyword)
        pages = (total + page_size - 1) // page_size if page_size else 0

        items = NewsRepository.list_published(
            page_num, page_size, normalized_category, keyword
        )

        return {
            "total": total,
            "pages": pages,
            "pageNum": page_num,
            "pageSize": page_size,
            "list": items,
        }

    def get_detail(self, news_id: int) -> dict | None:
        """
        查询资讯详情

        Returns:
            与前端 NewsDetail 对齐的字典；不存在返回 None
        """
        return NewsRepository.get_published_detail(int(news_id))

    def list_categories(self) -> list[dict[str, Any]]:
        """
        查询分类列表（含各分类数量）

        返回顺序固定，「全部」始终在第一位，与前端筛选标签一致。
        """
        counts = NewsRepository.category_counts()
        total = sum(counts.values())

        categories: list[dict[str, Any]] = [
            {"key": "", "name": "全部", "count": total}
        ]
        for name in CATEGORY_NAMES:
            categories.append(
                {"key": name, "name": name, "count": counts.get(name, 0)}
            )

        # 数据库中出现过的、不在预置清单中的分类也一并返回
        for name, count in counts.items():
            if name not in CATEGORY_NAMES:
                categories.append({"key": name, "name": name, "count": count})

        return categories


# ==================== 进程级单例 ====================

_service: NewsService | None = None


def init_news_service(settings: Settings) -> NewsService:
    """初始化进程级资讯服务单例"""
    global _service
    if _service is None:
        _service = NewsService(settings)
    return _service


def get_news_service() -> NewsService:
    """获取进程级资讯服务单例"""
    if _service is None:
        raise RuntimeError("资讯服务尚未初始化")
    return _service
