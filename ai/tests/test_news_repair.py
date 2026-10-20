"""
资讯「抓取触发 + 正文修复」测试

背景（真实故障）：
1. 前端「刷新」按钮只重新拉了一次列表，从未调用 `/news/refresh`，
   所以库里永远是最早那批数据；
2. 早于「正文补全」功能入库的资讯，正文只是 RSS 摘要（被截断），
   而且它们大多已经掉出当前 feed，靠重新抓取碰不到，需要按库驱动修复。

覆盖：
- 抓取任务状态查询与互斥
- 按库驱动的修复流程（回源 → 强制翻译 → 摘要 → 审核 → 覆盖写回）
- 修复的幂等标记（content_enriched），避免重复烧模型调用
- 中文标题的条目必须强制翻译
"""

import pytest

import app.news.nodes as N
from app.config import Settings
from app.news.fetchers import NewsFetcher, NewsItem, enrich_items
from app.news.graph import build_news_workflow
from app.news.repository import NewsRepository
from app.news.service import NewsService
from app.news.state import STAGE_APPROVED


class EmptyFetcher(NewsFetcher):
    """不返回任何条目的抓取源（避免测试触网）"""

    name = "empty"

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        return []


def make_settings(**overrides) -> Settings:
    defaults = dict(
        deepseek_api_key="t",
        llm_model="fake",
        aninews_enabled=False,
        news_fallback_rss="",
        news_enrich_min_chars=600,
        news_enrich_limit=20,
        news_enrich_delay=0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def make_service(settings: Settings | None = None) -> NewsService:
    return NewsService(settings or make_settings(), fetcher=EmptyFetcher())


SHORT_ROWS = [
    {
        "source_uid": "uid-a",
        "title": "中文标题 A",
        "source": "News - MyAnimeList",
        "source_url": "https://myanimelist.net/news/1",
        "contentLength": 200,
    },
    {
        "source_uid": "uid-b",
        "title": "中文标题 B",
        "source": "News - MyAnimeList",
        "source_url": "https://myanimelist.net/news/2",
        "contentLength": 180,
    },
]


@pytest.fixture
def patched(monkeypatch):
    """把修复流程的外部依赖全部替换掉（不触网、不调模型、不写库）"""
    calls = {"enrich": [], "translate": [], "upsert": []}

    def fake_enrich(items, settings):
        for item in items:
            # 模拟回源：uid-a 拿到全文；uid-b 没有源地址 → 补不到
            if item.source_uid == "uid-a" and item.source_url:
                item.content = "English full article " * 60
                item.content_enriched = True
        calls["enrich"].append([i.source_uid for i in items])
        return items

    def fake_translate(item, settings, force=False):
        calls["translate"].append({"uid": item.source_uid, "force": force})
        item.content = "中文正文" * 120
        item.summary = "中文摘要"
        return item

    def fake_summarize(item, settings):
        item.summary = item.summary or "中文摘要"
        item.attempts += 1
        return item

    def fake_review(item, settings):
        return True, "审核通过"

    def fake_upsert(item, status="published"):
        calls["upsert"].append({"uid": item.get("source_uid"), "status": status})
        return True

    monkeypatch.setattr("app.news.fetchers.enrich_items", fake_enrich)
    monkeypatch.setattr(N, "_translate_item", fake_translate)
    monkeypatch.setattr(N, "_summarize_item", fake_summarize)
    monkeypatch.setattr(N, "_review_item", fake_review)
    monkeypatch.setattr(NewsRepository, "upsert", staticmethod(fake_upsert))
    monkeypatch.setattr(
        NewsRepository, "find_related_anime", staticmethod(lambda text: (None, ""))
    )
    monkeypatch.setattr(
        NewsRepository, "replace_review_logs", staticmethod(lambda uid, logs: None)
    )
    return calls


# ==================== 1. 运行状态 ====================


class TestRunStatus:
    def test_initial_status(self):
        service = make_service()
        status = service.run_status()

        assert status["running"] is False
        assert status["lastRun"] is None
        assert "startedAt" in status and "finishedAt" in status

    def test_status_records_last_run(self, monkeypatch, patched):
        service = make_service()
        monkeypatch.setattr(
            service._workflow, "invoke", lambda state: {"items": {}, "log": []}
        )

        summary = service.run_workflow(limit=1)

        status = service.run_status()
        assert status["running"] is False
        assert status["finishedAt"] is not None
        assert status["lastRun"]["run_id"] == summary["run_id"]

    def test_concurrent_run_is_rejected(self, monkeypatch, patched):
        """抓取耗时较长，并发跑会重复调用模型、互相覆盖数据"""
        service = make_service()
        # 互斥是由锁保证的（_running 只是对外状态）
        service._run_lock.acquire()
        try:
            summary = service.run_workflow(limit=1)
        finally:
            service._run_lock.release()

        assert summary["run_id"] == ""
        assert summary["logs"] == ["已有任务在运行中"]

    def test_running_flag_reset_on_exception(self, monkeypatch, patched):
        service = make_service()

        def boom(state):
            raise RuntimeError("工作流崩了")

        monkeypatch.setattr(service._workflow, "invoke", boom)

        with pytest.raises(RuntimeError):
            service.run_workflow(limit=1)

        # 异常也要释放锁与状态，否则后续永远无法再抓取
        assert service.is_running() is False
        assert service._run_lock.locked() is False


# ==================== 2. 正文修复（按库驱动） ====================


class TestRepairTruncated:
    def test_repairs_short_rows(self, monkeypatch, patched):
        service = make_service()
        monkeypatch.setattr(
            NewsRepository,
            "short_content_items",
            staticmethod(lambda min_chars, limit: list(SHORT_ROWS)),
        )

        result = service.repair_truncated()

        assert result["checked"] == 2
        assert result["repaired"] == 1, "只有回源成功的 uid-a 应被修复"
        assert result["failed"] == 1
        assert result["items"][0]["source_uid"] == "uid-a"
        assert result["items"][0]["contentLength"] > 400, "译文应明显长于原来的摘要"

    def test_force_translate_for_chinese_titles(self, monkeypatch, patched):
        """库里标题是中文、正文是英文摘要，必须强制翻译，不能被"含中文就跳过"拦掉"""
        service = make_service()
        monkeypatch.setattr(
            NewsRepository,
            "short_content_items",
            staticmethod(lambda min_chars, limit: [SHORT_ROWS[0]]),
        )

        service.repair_truncated()

        translates = [c for c in patched["translate"] if c["uid"] == "uid-a"]
        assert translates and translates[0]["force"] is True

    def test_persists_as_published_when_review_passes(self, monkeypatch, patched):
        service = make_service()
        monkeypatch.setattr(
            NewsRepository,
            "short_content_items",
            staticmethod(lambda min_chars, limit: [SHORT_ROWS[0]]),
        )

        service.repair_truncated()

        assert patched["upsert"][0]["uid"] == "uid-a"
        assert patched["upsert"][0]["status"] == "published"

    def test_no_work_when_nothing_truncated(self, monkeypatch, patched):
        service = make_service()
        monkeypatch.setattr(
            NewsRepository,
            "short_content_items",
            staticmethod(lambda min_chars, limit: []),
        )

        result = service.repair_truncated()

        assert result == {"checked": 0, "repaired": 0, "failed": 0, "items": []}
        assert patched["translate"] == []

    def test_row_without_source_url_is_skipped(self, monkeypatch, patched):
        service = make_service()
        row = {**SHORT_ROWS[0], "source_url": ""}
        monkeypatch.setattr(
            NewsRepository,
            "short_content_items",
            staticmethod(lambda min_chars, limit: [row]),
        )

        result = service.repair_truncated()

        # 没有源地址就补不了正文，但不应抛异常
        assert result["repaired"] == 0
        assert result["failed"] == 1

    def test_repair_folds_into_run_summary(self, monkeypatch, patched):
        service = make_service()
        monkeypatch.setattr(
            service._workflow, "invoke", lambda state: {"items": {}, "log": []}
        )
        monkeypatch.setattr(
            NewsRepository,
            "short_content_items",
            staticmethod(lambda min_chars, limit: [SHORT_ROWS[0]]),
        )

        summary = service.run_workflow(limit=1, repair=True)

        assert summary["repaired"] == 1
        assert summary["repairChecked"] == 1
        assert any("正文修复" in line for line in summary["logs"])

    def test_repair_skipped_when_flag_false(self, monkeypatch, patched):
        service = make_service()
        monkeypatch.setattr(
            service._workflow, "invoke", lambda state: {"items": {}, "log": []}
        )

        def forbidden(min_chars, limit):
            raise AssertionError("repair=False 时不应查询残缺条目")

        monkeypatch.setattr(NewsRepository, "short_content_items", staticmethod(forbidden))

        summary = service.run_workflow(limit=1, repair=False)
        assert summary["repaired"] == 0


# ==================== 3. 幂等标记 ====================


class TestEnrichedFlag:
    def test_enrich_marks_item(self, monkeypatch):
        import app.news.fetchers as F

        class FakeResponse:
            content = b"<html><body><article>" + b"<p>full text here</p>" * 30 + b"</article></body></html>"
            encoding = "utf-8"

            def raise_for_status(self):
                return None

        monkeypatch.setattr(F.requests, "get", lambda url, **kw: FakeResponse())
        item = NewsItem(
            source_uid="uid",
            title="t",
            content="short",
            source_url="https://myanimelist.net/news/1",
        )

        enrich_items([item], make_settings())

        assert item.content_enriched is True

    def test_flag_survives_dict_roundtrip(self):
        item = NewsItem(source_uid="u", title="t", content="c", content_enriched=True)
        restored = NewsItem.from_dict(item.to_dict())

        assert restored.content_enriched is True

    def test_short_content_query_filters_enriched(self):
        """查询条件必须排除已补全的条目，否则短文章会被反复修复"""
        sql_calls: list[str] = []

        class FakeClient:
            def execute_query(self, sql, params=None):
                sql_calls.append(sql)
                return []

        import app.news.repository as R

        original = R.get_mysql_client
        R.get_mysql_client = lambda: FakeClient()
        try:
            NewsRepository.short_content_items(600, 10)
            NewsRepository.truncated_source_uids(["u1", "u2"], 600)
        finally:
            R.get_mysql_client = original

        # 两个查询都必须带「已补全跳过」条件，否则会每轮重复烧模型调用
        assert len(sql_calls) == 2
        for sql in sql_calls:
            assert "IFNULL(content_enriched, 0) = 0" in sql
