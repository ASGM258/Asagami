"""
资讯模块测试

覆盖：
1. 抓取源归一化（HTML 清洗、时间解析、去重标识）
2. 工作流四节点与审核重试路由（用脚本化假模型驱动，无需网络与数据库）
3. 审核超过 3 次标记 rejected 并记录原因
4. 敏感信息去除
5. 前端契约字段（驼峰、PageResponse 结构）
"""

import json
from typing import Any, ClassVar

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import Settings
from app.news import nodes as N
from app.news.fetchers import (
    NewsItem,
    NewsFetcher,
    build_source_uid,
    normalize_publish_time,
    strip_html,
)
from app.news.graph import build_news_workflow
from app.news.repository import NewsRepository
from app.news.state import MAX_REVIEW_ATTEMPTS

# 各节点提示词的识别标记
MARK_TRANSLATE = "请把下面的英文动漫资讯翻译"
MARK_SUMMARY = "请为下面的资讯生成摘要"
MARK_REVIEW = "动漫资讯平台的审核员"


class ScriptedLLM(BaseChatModel):
    """
    脚本化假模型

    按提示词内容判断当前是哪个 agent，并返回对应结构的 JSON，
    从而在完全离线的情况下驱动整条工作流。
    """

    # 审核通过所需的第几次审核（1 表示首次即通过）
    pass_on_attempt: int = 1
    calls: ClassVar[list[str]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted-llm"

    def _kind(self, prompt: str) -> str:
        if MARK_TRANSLATE in prompt:
            return "translate"
        if MARK_SUMMARY in prompt:
            return "summary"
        if MARK_REVIEW in prompt:
            return "review"
        return "unknown"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        prompt = messages[-1].content
        kind = self._kind(prompt)
        ScriptedLLM.calls.append(kind)

        if kind == "translate":
            payload = {"title": "中文标题", "content": "中文正文内容"}
        elif kind == "summary":
            version = ScriptedLLM.calls.count("summary")
            # 故意混入邮箱，验证敏感信息清洗
            payload = {
                "summary": f"第{version}版摘要，联系邮箱 leak@example.com",
                "title": "中文标题",
            }
        elif kind == "review":
            attempt = ScriptedLLM.calls.count("review")
            passed = attempt >= self.pass_on_attempt
            payload = {"passed": passed, "reason": f"第{attempt}次审核"}
        else:
            payload = {}

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=json.dumps(payload, ensure_ascii=False))
                )
            ]
        )


class FakeFetcher(NewsFetcher):
    """固定返回若干条英文资讯的假抓取源"""

    name = "fake"

    def __init__(self, count: int = 1) -> None:
        self._count = count

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        return [
            NewsItem(
                source_uid=f"uid{index}",
                title=f"Anime News {index}",
                content=f"English body {index}",
                source="fake",
            )
            for index in range(self._count)
        ]


@pytest.fixture
def news_settings() -> Settings:
    """资讯测试配置（关闭真实抓取源）"""
    return Settings(
        aninews_enabled=False,
        news_fallback_rss="",
        llm_model="fake-model",
        news_scheduler_enabled=False,
    )


@pytest.fixture(autouse=True)
def _reset_calls():
    """每个用例前清空假模型调用记录"""
    ScriptedLLM.calls = []
    yield
    ScriptedLLM.calls = []


def run_workflow(news_settings, fetcher, llm, limit: int = 5) -> dict:
    """注入假模型并运行工作流"""
    for factory in (
        N.make_translate_node,
        N.make_summarize_node,
        N.make_review_node,
    ):
        factory.__globals__["get_llm"] = lambda temperature=None, max_tokens=None: llm

    workflow = build_news_workflow(news_settings, fetcher)
    return workflow.invoke({"limit": limit, "run_id": "test", "items": {}, "log": []})


# ==================== 1. 抓取源归一化 ====================


class TestNormalization:
    """抓取源的文本与时间归一化"""

    def test_strip_html_removes_tags_and_entities(self):
        assert strip_html("<p>Hello&nbsp;<b>World</b></p>") == "Hello World"

    def test_strip_html_handles_none(self):
        assert strip_html(None) == ""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("2026-10-08T12:58:00", "2026-10-08 12:58:00"),
            ("2026-10-08 12:58:00", "2026-10-08 12:58:00"),
            ("2026-10-08", "2026-10-08 00:00:00"),
            ("Thu, 08 Oct 2026 12:58:00 +0000", "2026-10-08 12:58:00"),
        ],
    )
    def test_normalize_publish_time(self, raw, expected):
        assert normalize_publish_time(raw) == expected

    def test_normalize_publish_time_invalid_returns_empty(self):
        assert normalize_publish_time("not a date") == ""

    def test_build_source_uid_prefers_guid(self):
        assert build_source_uid("guid-1", "title", "2026-10-08 00:00:00") == "guid-1"

    def test_build_source_uid_falls_back_to_hash(self):
        first = build_source_uid(None, "title", "2026-10-08 00:00:00")
        second = build_source_uid(None, "title", "2026-10-08 00:00:00")
        third = build_source_uid(None, "other", "2026-10-08 00:00:00")

        assert first == second  # 稳定
        assert first != third  # 不同内容不同标识
        assert len(first) == 32


class TestAniNewsAPIParsing:
    """AniNewsAPI 响应结构容错"""

    def test_extract_list_from_nested_structures(self, news_settings):
        from app.news.fetchers import AniNewsAPIFetcher

        fetcher = AniNewsAPIFetcher(news_settings)

        assert fetcher._extract_list([{"a": 1}]) == [{"a": 1}]
        assert fetcher._extract_list({"data": [1, 2]}) == [1, 2]
        assert fetcher._extract_list({"news": [3]}) == [3]
        assert fetcher._extract_list({"data": {"items": [4]}}) == [4]
        assert fetcher._extract_list({"unknown": 1}) == []

    def test_normalize_maps_alias_fields(self, news_settings):
        from app.news.fetchers import AniNewsAPIFetcher

        fetcher = AniNewsAPIFetcher(news_settings)
        item = fetcher._normalize(
            {
                "headline": "<b>Big News</b>",
                "description": "short desc",
                "image_url": "https://img/x.jpg",
                "publishedAt": "2026-10-08T12:58:00",
                "link": "https://src/n1",
                "tags": ["PV", "Anime"],
            }
        )

        assert item is not None
        assert item.title == "Big News"
        assert item.cover_image == "https://img/x.jpg"
        assert item.publish_time == "2026-10-08 12:58:00"
        assert item.tags == ["PV", "Anime"]

    def test_normalize_returns_none_without_title(self, news_settings):
        from app.news.fetchers import AniNewsAPIFetcher

        fetcher = AniNewsAPIFetcher(news_settings)
        assert fetcher._normalize({"description": "no title"}) is None


# ==================== 2. 工作流与审核重试 ====================


class TestWorkflow:
    """四节点工作流与审核重试路由"""

    def test_first_review_pass_publishes(self, news_settings):
        llm = ScriptedLLM(pass_on_attempt=1)
        state = run_workflow(news_settings, FakeFetcher(1), llm)

        item = next(iter(state["items"].values()))
        assert item["stage"] == "approved"
        assert item["attempts"] == 1
        # 每个 agent 只应被调用一次
        assert ScriptedLLM.calls == ["translate", "summary", "review"]

    def test_review_failure_routes_back_to_summary(self, news_settings):
        """首次审核不通过 → 回退摘要重做 → 第二次通过"""
        llm = ScriptedLLM(pass_on_attempt=2)
        state = run_workflow(news_settings, FakeFetcher(1), llm)

        item = next(iter(state["items"].values()))
        assert item["stage"] == "approved"
        assert item["attempts"] == 2
        # 翻译只做一次，摘要与审核各两次
        assert ScriptedLLM.calls == ["translate", "summary", "review", "summary", "review"]

    def test_exceeding_max_attempts_marks_rejected(self, news_settings):
        """始终不通过 → 达到上限后标记 rejected 并记录原因"""
        llm = ScriptedLLM(pass_on_attempt=99)
        state = run_workflow(news_settings, FakeFetcher(1), llm)

        item = next(iter(state["items"].values()))
        assert item["stage"] == "rejected"
        assert item["attempts"] == MAX_REVIEW_ATTEMPTS
        assert item["review_reason"]  # 必须记录原因
        # 摘要与审核各执行 MAX_REVIEW_ATTEMPTS 次，翻译仅一次
        assert ScriptedLLM.calls.count("translate") == 1
        assert ScriptedLLM.calls.count("summary") == MAX_REVIEW_ATTEMPTS
        assert ScriptedLLM.calls.count("review") == MAX_REVIEW_ATTEMPTS

    def test_multiple_items_processed_independently(self, news_settings):
        """多条资讯各自独立流转，互不影响"""
        llm = ScriptedLLM(pass_on_attempt=1)
        state = run_workflow(news_settings, FakeFetcher(3), llm)

        assert len(state["items"]) == 3
        assert all(v["stage"] == "approved" for v in state["items"].values())
        assert ScriptedLLM.calls.count("translate") == 3

    def test_empty_fetch_ends_gracefully(self, news_settings):
        """抓取无结果时工作流正常结束"""
        llm = ScriptedLLM(pass_on_attempt=1)
        state = run_workflow(news_settings, FakeFetcher(0), llm)

        assert state["items"] == {}
        assert ScriptedLLM.calls == []

    def test_workflow_logs_collected(self, news_settings):
        """各阶段日志应汇总到最终状态"""
        llm = ScriptedLLM(pass_on_attempt=1)
        state = run_workflow(news_settings, FakeFetcher(1), llm)

        joined = "\n".join(state["log"])
        assert "抓取agent" in joined
        assert "翻译agent" in joined
        assert "摘要agent" in joined
        assert "审核agent" in joined


# ==================== 3. 敏感信息清洗 ====================


class TestSanitize:
    """摘要 agent 的敏感信息去除"""

    @pytest.mark.parametrize(
        "text,should_not_contain",
        [
            ("联系 leak@example.com 获取", "leak@example.com"),
            ("电话 13812345678", "13812345678"),
            ("证件 110101199001011234", "110101199001011234"),
            ("密钥 sk-abcdefgh12345678", "sk-abcdefgh12345678"),
            ("详见 https://example.com/a", "https://example.com/a"),
        ],
    )
    def test_sensitive_patterns_removed(self, text, should_not_contain):
        cleaned = N.sanitize_text(text)
        assert should_not_contain not in cleaned
        # 占位文案形如 [邮箱已隐藏] / [链接已移除]
        assert "已隐藏" in cleaned or "已移除" in cleaned

    def test_summary_sanitized_through_workflow(self, news_settings):
        """模型输出的摘要含邮箱时，落库前必须已清洗"""
        llm = ScriptedLLM(pass_on_attempt=1)
        state = run_workflow(news_settings, FakeFetcher(1), llm)

        item = next(iter(state["items"].values()))
        assert "leak@example.com" not in item["summary"]
        assert "[邮箱已隐藏]" in item["summary"]

    def test_residual_sensitive_detection(self):
        assert N.has_residual_sensitive("邮箱 a@b.com") is True
        assert N.has_residual_sensitive("正常文本") is False
        assert N.has_residual_sensitive("") is False


class TestJsonParsing:
    """模型输出解析容错"""

    def test_plain_json(self):
        assert N.parse_json_response('{"passed": true}') == {"passed": True}

    def test_code_fenced_json(self):
        raw = '```json\n{"passed": false, "reason": "x"}\n```'
        assert N.parse_json_response(raw)["passed"] is False

    def test_json_with_surrounding_text(self):
        raw = '好的，结果如下：{"summary": "内容"} 以上。'
        assert N.parse_json_response(raw)["summary"] == "内容"

    def test_invalid_returns_empty(self):
        assert N.parse_json_response("完全不是 JSON") == {}
        assert N.parse_json_response("") == {}


# ==================== 4. 前端契约字段 ====================


class TestCategoryClassification:
    """分类归一化与关键词兜底（保证前端筛选标签始终有值）"""

    def test_normalize_accepts_allowed_categories(self):
        for name in N.ALLOWED_CATEGORIES:
            assert N.normalize_category(name) == name

    def test_normalize_extracts_from_longer_text(self):
        assert N.normalize_category("分类：动画") == "动画"
        assert N.normalize_category("声优新闻") == "声优"

    def test_normalize_rejects_unknown(self):
        assert N.normalize_category("体育") is None
        assert N.normalize_category("") is None
        assert N.normalize_category(None) is None

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("动画官方网站公布追加声优阵容", "声优"),
            ("新作手游正式公开", "游戏"),
            ("线下活动展会情报", "活动"),
            ("漫画连载再开", "漫画"),
            ("TV动画第一弹PV公开", "动画"),
            ("完全无关的内容没有关键词", "动画"),  # 兜底为动画
        ],
    )
    def test_guess_category(self, text, expected):
        assert N.guess_category(text) == expected

    def test_guess_category_handles_empty(self):
        assert N.guess_category("") == N.DEFAULT_CATEGORY

    def test_workflow_assigns_category(self, news_settings):
        """RSS 源通常无分类，工作流应补齐"""
        llm = ScriptedLLM(pass_on_attempt=1)
        state = run_workflow(news_settings, FakeFetcher(1), llm)

        item = next(iter(state["items"].values()))
        assert item["category"]
        assert item["category"] in N.ALLOWED_CATEGORIES


class TestTruncation:
    """截断策略：翻译入参必须在句子边界截断，避免译文出现英文残缺"""

    def test_short_text_unchanged(self):
        assert N.truncate_at_sentence("短文本。", 100) == "短文本。"

    def test_truncates_at_sentence_boundary(self):
        text = "第一句话。第二句话。第三句话。"
        result = N.truncate_at_sentence(text, 12)

        # 不应把句子劈开
        assert result.endswith("。")
        assert len(result) <= 12

    def test_falls_back_to_hard_cut_without_boundary(self):
        text = "a" * 200
        result = N.truncate_at_sentence(text, 50)
        assert len(result) == 50

    def test_handles_none_and_empty(self):
        assert N.truncate_at_sentence("", 10) == ""
        assert N.truncate_at_sentence(None, 10) == ""

    def test_translate_limit_is_large_enough_for_articles(self):
        # 翻译结果会入库，上限必须显著大于摘要用的上限
        assert N.TRANSLATE_PROMPT_LIMIT >= N.CONTENT_PROMPT_LIMIT * 2


class TestFrontendContract:
    """数据库行 → 前端字段映射"""

    def test_row_maps_to_camel_case_item(self):
        from datetime import datetime

        row = {
            "id": 12,
            "title": "标题",
            "cover_image": "https://img/a.jpg",
            "summary": "摘要",
            "category": "动画",
            "source": "AniNewsAPI",
            "author": "作者",
            "publish_time": datetime(2026, 10, 8, 12, 58, 0),
            "tags": "PV,动画化",
            "view_count": 42,
        }

        item = NewsRepository._to_list_item(row)

        # 字段名必须与 src/types/news.ts 的 NewsItem 一致
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
        assert item["coverImage"] == "https://img/a.jpg"
        assert item["tags"] == ["PV", "动画化"]
        assert item["viewCount"] == 42
        # ISO 形式，前端 formatDateTime 解析可靠
        assert item["publishTime"] == "2026-10-08T12:58:00"

    def test_null_fields_become_safe_defaults(self):
        item = NewsRepository._to_list_item({"id": 1, "title": "T"})

        assert item["coverImage"] == ""
        assert item["summary"] == ""
        assert item["tags"] == []
        assert item["publishTime"] == ""
        assert item["viewCount"] == 0
