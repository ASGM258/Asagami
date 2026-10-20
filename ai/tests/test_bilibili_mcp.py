"""
B 站推荐服务与工具测试

不依赖真实 MCP 子进程与网络：把 `BilibiliMcpService._call` 换成脚本化返回，
验证排序策略、去重、补详情、链接拼装与工具层的错误兜底。
"""

import json

import pytest

from app.config import Settings
from app.mcp import bilibili as B
from app.mcp.bilibili import (
    VIDEO_URL_TEMPLATE,
    BilibiliMcpService,
    normalize_video,
    resolve_command,
    score_of,
)
from app.mcp.stdio_client import McpError


def make_settings(**overrides) -> Settings:
    defaults = dict(deepseek_api_key="t", llm_model="fake")
    defaults.update(overrides)
    return Settings(**defaults)


def search_item(bvid: str, title: str, play: int, danmaku: int = 0) -> dict:
    return {
        "bvid": bvid,
        "aid": 1,
        "title": title,
        "author": "某UP",
        "mid": 1,
        "description": "简介",
        "pic": "",
        "duration": 300,
        "play": play,
        "danmaku": danmaku,
        "pubdate": "2024-01-01T00:00:00",
    }


def detail_item(bvid: str, view: int, like: int, favorite: int, coin: int) -> dict:
    return {
        "bvid": bvid,
        "title": "标题",
        "owner_name": "某UP",
        "duration": 300,
        "stat": {
            "view": view,
            "danmaku": 10,
            "reply": 5,
            "favorite": favorite,
            "coin": coin,
            "share": 1,
            "like": like,
        },
    }


class ScriptedService(BilibiliMcpService):
    """把 MCP 调用替换为脚本化数据"""

    def __init__(self, settings, search_items, details) -> None:
        super().__init__(settings)
        self._search_items = search_items
        self._details = details
        self.calls: list[tuple[str, dict]] = []

    def _call(self, tool: str, arguments: dict):
        self.calls.append((tool, arguments))
        if tool == "search_bilibili_videos":
            return {"items": self._search_items}
        if tool == "get_bilibili_video_info":
            return self._details.get(arguments.get("bvid"), {})
        return {}


# ==================== 评分与归一化 ====================


class TestScoring:
    def test_like_outweighs_play(self):
        """1 个点赞应当明显重于 1 次播放"""
        assert B.SCORE_WEIGHTS["like"] > B.SCORE_WEIGHTS["view"]

        a = score_of({"stat": {"view": 1000, "like": 0}})
        b = score_of({"stat": {"view": 0, "like": 1000}})
        assert b > a

    def test_search_item_uses_play_field(self):
        """搜索结果没有 stat，播放量字段叫 play"""
        with_play = score_of({"play": 1000, "danmaku": 0})
        assert with_play >= 1000

    def test_detail_item_uses_stat_view(self):
        assert score_of({"stat": {"view": 1000}}) >= 1000

    def test_empty_video_scores_zero(self):
        assert score_of({}) == 0.0


class TestNormalize:
    def test_builds_clickable_url(self):
        item = normalize_video(search_item("BV1xx411c7mD", "标题", 100))
        assert item.url == VIDEO_URL_TEMPLATE.format(bvid="BV1xx411c7mD")
        assert item.url.startswith("https://www.bilibili.com/video/BV")

    def test_reads_search_fields(self):
        item = normalize_video(search_item("BV1", "标题", 1234, danmaku=56))
        assert item.play == 1234
        assert item.danmaku == 56
        assert item.author == "某UP"

    def test_reads_detail_stat_fields(self):
        raw = {**search_item("BV1", "标题", 0), **detail_item("BV1", 500, 30, 20, 10)}
        item = normalize_video(raw)
        assert (item.play, item.like, item.favorite, item.coin) == (500, 30, 20, 10)

    def test_missing_bvid_yields_empty_url(self):
        assert normalize_video({"title": "标题"}).url == ""


# ==================== 启动命令解析 ====================


class TestResolveCommand:
    def test_explicit_command_wins(self, tmp_path=None):
        settings = make_settings(bilibili_mcp_command="bili-mcp")
        # PATH 里通常没有它：要么解析成功，要么返回空（两者都不应抛异常）
        command = resolve_command(settings)
        assert command == [] or command[-1] == "--stdio"

    def test_missing_explicit_command_returns_empty(self):
        settings = make_settings(bilibili_mcp_command="no-such-binary-xyz")
        assert resolve_command(settings) == []

    def test_appends_stdio_flag(self):
        from app.mcp.bilibili import _ai_root

        settings = make_settings()
        command = resolve_command(settings)
        if command:  # 未安装 MCP 服务时为空，跳过
            assert command[-1] == "--stdio"
            assert _ai_root().name == "ai"


# ==================== 推荐流程 ====================


class TestRecommend:
    def _service(self, search_items, details=None, **overrides) -> ScriptedService:
        settings = make_settings(bilibili_detail_limit=2, **overrides)
        return ScriptedService(settings, search_items, details or {})

    def test_ranks_by_combined_score(self):
        """播放更高但点赞少的视频，可能输给点赞多的视频"""
        items = [
            search_item("BV_high_play", "高播放低互动", 100000),
            search_item("BV_high_like", "低播放高互动", 50000),
        ]
        details = {
            "BV_high_play": detail_item("BV_high_play", 100000, 100, 10, 10),
            "BV_high_like": detail_item("BV_high_like", 50000, 9000, 500, 400),
        }
        result = self._service(items, details).recommend("斩服少女", limit=2)

        assert [v["bvid"] for v in result["recommendations"]] == [
            "BV_high_like",
            "BV_high_play",
        ]

    def test_dedupes_bvid(self):
        items = [
            search_item("BV1", "标题一", 100),
            search_item("BV1", "标题一重复", 100),
            search_item("BV2", "标题二", 200),
        ]
        result = self._service(items).recommend("x", limit=5)

        assert len(result["recommendations"]) == 2

    def test_returns_urls(self):
        result = self._service([search_item("BV1", "标题", 100)]).recommend("x", limit=5)

        assert result["recommendations"][0]["url"].endswith("BV1")

    def test_limit_is_clamped(self):
        items = [search_item(f"BV{i}", f"标题{i}", i) for i in range(20)]
        service = self._service(items)

        assert len(service.recommend("x", limit=99)["recommendations"]) <= 10
        assert len(service.recommend("x", limit=0)["recommendations"]) == 1

    def test_enriches_only_top_candidates(self):
        """只对头部候选补详情，避免 N+1 次 MCP 调用"""
        items = [search_item(f"BV{i}", f"标题{i}", 1000 - i) for i in range(10)]
        service = self._service(items)

        service.recommend("x", limit=3)

        detail_calls = [c for c in service.calls if c[0] == "get_bilibili_video_info"]
        assert len(detail_calls) == 2, "bilibili_detail_limit=2，应只补 2 条"

    def test_detail_failure_is_tolerated(self):
        items = [search_item("BV1", "标题", 100)]
        settings = make_settings(bilibili_detail_limit=1)
        service = ScriptedService(settings, items, {})

        def boom(tool, arguments):
            if tool == "get_bilibili_video_info":
                raise McpError("详情挂了")
            return {"items": items}

        service._call = boom  # type: ignore[method-assign]
        result = service.recommend("x", limit=1)

        assert len(result["recommendations"]) == 1, "补详情失败不应丢条目"
        assert result["note"], "应给出降级说明"

    def test_empty_result(self):
        result = self._service([]).recommend("不存在的番", limit=5)

        assert result["recommendations"] == []
        assert result["note"]

    def test_empty_keyword_raises(self):
        with pytest.raises(McpError):
            self._service([]).recommend("   ", limit=5)


# ==================== 工具层 ====================


class TestTool:
    def test_disabled_returns_error_json(self, monkeypatch):
        from app.mcp import tools as T

        monkeypatch.setattr(
            T, "get_settings", lambda: make_settings(bilibili_mcp_enabled=False)
        )
        payload = json.loads(T.recommend_bilibili_videos.invoke({"keyword": "斩服少女"}))

        assert payload["success"] is False
        assert "关闭" in payload["error"]

    def test_mcp_error_returns_error_json(self, monkeypatch):
        from app.mcp import tools as T

        class Failing:
            def recommend(self, keyword, limit):
                raise McpError("连不上")

        monkeypatch.setattr(T, "get_settings", lambda: make_settings())
        monkeypatch.setattr(T, "get_bilibili_service", lambda: Failing())

        payload = json.loads(T.recommend_bilibili_videos.invoke({"keyword": "x"}))
        assert payload["success"] is False
        assert "连不上" in payload["error"]

    def test_success_payload_has_links(self, monkeypatch):
        from app.mcp import tools as T

        class Ok:
            def recommend(self, keyword, limit):
                return {
                    "keyword": keyword,
                    "total": 1,
                    "detail_enriched": 1,
                    "note": "",
                    "recommendations": [
                        {
                            "bvid": "BV1",
                            "title": "标题",
                            "author": "UP",
                            "url": "https://www.bilibili.com/video/BV1",
                            "play": 100,
                            "like": 10,
                        }
                    ],
                }

        monkeypatch.setattr(T, "get_settings", lambda: make_settings())
        monkeypatch.setattr(T, "get_bilibili_service", lambda: Ok())

        payload = json.loads(T.recommend_bilibili_videos.invoke({"keyword": "斩服少女"}))

        assert payload["success"] is True
        assert payload["recommendations"][0]["url"].startswith("https://www.bilibili.com")
        assert "url" in payload["usage_hint"]

    def test_limit_is_clamped_before_call(self, monkeypatch):
        from app.mcp import tools as T

        seen = {}

        class Ok:
            def recommend(self, keyword, limit):
                seen["limit"] = limit
                return {"keyword": keyword, "total": 0, "recommendations": [], "note": "无"}

        monkeypatch.setattr(T, "get_settings", lambda: make_settings())
        monkeypatch.setattr(T, "get_bilibili_service", lambda: Ok())

        T.recommend_bilibili_videos.invoke({"keyword": "x", "limit": 99})
        assert seen["limit"] == T.MAX_LIMIT

    def test_tool_registered_in_agent(self):
        from app.agent.graph import AGENT_TOOLS

        names = [t.name for t in AGENT_TOOLS]
        assert "recommend_bilibili_videos" in names
