"""
资讯接口的 HTTP 层测试

通过替换 app.news.service 中引用的仓储对象，把数据访问换成内存实现，
从而在无 MySQL 的环境下验证路由注册、响应外壳与前端契约字段。
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_news_service
from app.main import app
from app.news.service import NewsService

SAMPLE_ROWS = [
    {
        "id": 2,
        "title": "第二条资讯",
        "cover_image": "https://img/2.jpg",
        "summary": "摘要二",
        "category": "动画",
        "source": "AniNewsAPI",
        "author": "作者",
        "publish_time": "2026-10-08T12:58:00",
        "tags": "PV,动画化",
        "view_count": 10,
        "content": "<p>正文二</p>",
        "related_anime_id": None,
        "related_anime_title": None,
    },
    {
        "id": 1,
        "title": "第一条资讯",
        "cover_image": "",
        "summary": "摘要一",
        "category": "漫画",
        "source": "RSS",
        "author": "作者",
        "publish_time": "2026-10-07T08:00:00",
        "tags": "",
        "view_count": 0,
        "content": "正文一",
        "related_anime_id": 5,
        "related_anime_title": "某动漫",
    },
]


class FakeRepository:
    """内存版资讯仓储（接口与 NewsRepository 对齐）"""

    rows = SAMPLE_ROWS

    @classmethod
    def ensure_schema(cls) -> None:
        """内存实现无需建表（app 启动时会调用）"""

    @classmethod
    def count_published(cls, category=None, keyword=None):
        return len(cls._filter(category, keyword))

    @classmethod
    def _filter(cls, category=None, keyword=None):
        rows = cls.rows
        if category:
            rows = [r for r in rows if r["category"] == category]
        if keyword:
            rows = [
                r
                for r in rows
                if keyword in r["title"] or keyword in (r.get("summary") or "")
            ]
        return rows

    @classmethod
    def list_published(cls, page_num, page_size, category=None, keyword=None):
        rows = cls._filter(category, keyword)
        start = (page_num - 1) * page_size
        return [cls._to_list_item(r) for r in rows[start : start + page_size]]

    @classmethod
    def get_published_detail(cls, news_id):
        for row in cls.rows:
            if row["id"] == news_id:
                detail = cls._to_list_item(row)
                detail["content"] = row.get("content") or ""
                detail["relatedAnimeId"] = row.get("related_anime_id")
                detail["relatedAnimeTitle"] = row.get("related_anime_title")
                return detail
        return None

    @classmethod
    def category_counts(cls):
        counts: dict[str, int] = {}
        for row in cls.rows:
            category = row.get("category")
            if category:
                counts[category] = counts.get(category, 0) + 1
        return counts

    # 复用真实的字段映射，保证测试与实现一致
    @staticmethod
    def _to_list_item(row):
        from app.news.repository import NewsRepository

        return NewsRepository._to_list_item(row)


@pytest.fixture
def news_client(monkeypatch):
    """注入了内存仓储的测试客户端"""
    monkeypatch.setattr("app.news.service.NewsRepository", FakeRepository)

    settings = Settings(aninews_enabled=False, news_fallback_rss="", llm_model="fake")
    service = NewsService(settings)
    app.dependency_overrides[get_news_service] = lambda: service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class TestNewsListEndpoint:
    """GET /api/news/list"""

    def test_list_shape_matches_frontend_page_response(self, news_client):
        response = news_client.get("/api/news/list", params={"pageNum": 1, "pageSize": 10})

        assert response.status_code == 200
        body = response.json()

        # 统一外壳
        assert body["success"] is True
        assert body["message"] == "获取资讯列表成功"
        assert isinstance(body["timestamp"], float)

        # data 必须与前端 PageResponse<NewsItem> 一致
        data = body["data"]
        assert set(data.keys()) == {"total", "pages", "pageNum", "pageSize", "list"}
        assert data["total"] == 2
        assert data["pages"] == 1
        assert data["pageNum"] == 1
        assert data["pageSize"] == 10

    def test_list_item_fields_match_news_item(self, news_client):
        response = news_client.get("/api/news/list")
        item = response.json()["data"]["list"][0]

        assert set(item.keys()) == {
            "id",
            "title",
            "coverImage",
            "summary",
            "category",
            "source",
            "author",
            "publishTime",
            "tags",
            "viewCount",
        }
        assert isinstance(item["tags"], list)

    def test_pagination_splits_pages(self, news_client):
        response = news_client.get("/api/news/list", params={"pageNum": 2, "pageSize": 1})

        data = response.json()["data"]
        assert data["total"] == 2
        assert data["pages"] == 2
        assert len(data["list"]) == 1
        assert data["list"][0]["id"] == 1

    def test_category_filter(self, news_client):
        response = news_client.get("/api/news/list", params={"category": "漫画"})

        data = response.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["category"] == "漫画"

    def test_category_all_means_no_filter(self, news_client):
        response = news_client.get("/api/news/list", params={"category": "all"})
        assert response.json()["data"]["total"] == 2

    def test_keyword_search(self, news_client):
        response = news_client.get("/api/news/list", params={"keyword": "第一条"})

        data = response.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["title"] == "第一条资讯"

    def test_invalid_page_size_rejected(self, news_client):
        response = news_client.get("/api/news/list", params={"pageSize": 0})
        assert response.status_code == 400


class TestNewsDetailEndpoint:
    """POST /api/news/detail"""

    def test_detail_returns_content_and_related(self, news_client):
        response = news_client.post("/api/news/detail", json={"newsId": 1})

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == 1
        assert data["content"] == "正文一"
        assert data["relatedAnimeId"] == 5
        assert data["relatedAnimeTitle"] == "某动漫"

    def test_unknown_news_returns_404(self, news_client):
        response = news_client.post("/api/news/detail", json={"newsId": 9999})

        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "NEWS_NOT_FOUND"

    def test_missing_news_id_returns_400(self, news_client):
        response = news_client.post("/api/news/detail", json={})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "MISSING_PARAMETER"

    def test_zero_news_id_returns_400(self, news_client):
        response = news_client.post("/api/news/detail", json={"newsId": 0})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "MISSING_PARAMETER"


class TestNewsCategoriesEndpoint:
    """GET /api/news/categories"""

    def test_categories_include_all_first(self, news_client):
        response = news_client.get("/api/news/categories")

        assert response.status_code == 200
        categories = response.json()["data"]

        # 「全部」必须在第一位，前端据此渲染筛选标签
        assert categories[0]["key"] == ""
        assert categories[0]["name"] == "全部"

    def test_categories_shape_matches_frontend(self, news_client):
        categories = news_client.get("/api/news/categories").json()["data"]

        for item in categories:
            assert "key" in item
            assert "name" in item
            assert "count" in item

    def test_categories_counts_reflect_data(self, news_client):
        categories = news_client.get("/api/news/categories").json()["data"]
        by_key = {item["key"]: item["count"] for item in categories}

        assert by_key["动画"] == 1
        assert by_key["漫画"] == 1
        assert by_key[""] == 2


class TestNewsRefreshEndpoint:
    """POST /api/news/refresh"""

    def test_refresh_is_accepted(self, news_client):
        response = news_client.post("/api/news/refresh", params={"limit": 5})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["accepted"] is True

    def test_refresh_creates_tables_on_service_init(self, news_client, monkeypatch):
        """服务初始化时会建表（此处仅验证调用路径不抛错）"""
        called = {}

        def fake_ensure():
            called["done"] = True

        monkeypatch.setattr(
            "app.news.service.NewsRepository.ensure_schema", staticmethod(fake_ensure)
        )
        NewsService.ensure_schema()
        assert called.get("done") is True
