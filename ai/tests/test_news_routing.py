"""
资讯工作流路由回归测试：审核↔重做不得重复、不得多余循环

真实故障（`Send` 扇出导致）：
- 审核节点为每个条目各执行一次，其后的**路由函数也跟着执行多次**
- 路由函数读到的是「部分合并」的全局状态，于是已经 `approved` 的条目
  在另一次路由调用里又被看成 `summarized`，被拉回摘要重做
- 结果：本该 1 轮通过的条目被刷到 `attempts=3`，模型调用成倍增加

修复：改为线性编排（fetch→translate→summarize→review→条件边→finalize），
每个超步只做一次路由判断。

本测试用「按条目区分行为」的假模型，断言：
1. 一次通过的条目：attempts=1、审核轨迹 1 条、stage=approved
2. 始终不通过的条目：attempts=3、审核轨迹 3 条、stage=rejected
3. 翻译只跑一遍（无扇出放大）
4. 模型调用次数与条目要求完全匹配，没有多余轮次
"""

import json
import re
from typing import ClassVar

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import app.news.nodes as N
from app.config import Settings
from app.news.fetchers import NewsFetcher, NewsItem
from app.news.graph import build_news_workflow
from app.news.state import MAX_REVIEW_ATTEMPTS


class PerItemModel(BaseChatModel):
    """按条目区分行为的假模型：0 号永远审核不通过，其余一次通过"""

    calls: ClassVar[list] = []

    @property
    def _llm_type(self) -> str:
        return "per-item"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN201
        return self

    @staticmethod
    def _kind(prompt: str) -> str:
        if "动漫资讯译者" in prompt:
            return "translate"
        if "生成摘要" in prompt:
            return "summary"
        if "审核员" in prompt:
            return "review"
        return "unknown"

    @staticmethod
    def _index_of(prompt: str) -> int:
        """从 prompt 里认出是第几条（翻译阶段用英文昵称，之后用中文标题）"""
        match = re.search(r"正文(\d+)", prompt) or re.search(r"标题(\d+)", prompt)
        if match:
            return int(match.group(1))
        match = re.search(r"English body (\d+)", prompt)
        return int(match.group(1)) if match else -1

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        prompt = str(messages[-1].content)
        kind = self._kind(prompt)
        index = self._index_of(prompt)

        if kind == "translate":
            payload = {"title": f"标题{index}", "content": f"正文{index}", "category": "动画"}
        elif kind == "summary":
            payload = {"summary": f"摘要{index}", "title": f"标题{index}"}
        elif kind == "review":
            fail = index == 0  # 0 号永远不通过
            payload = {"passed": not fail, "reason": "永不通过" if fail else "通过"}
        else:
            payload = {}

        type(self).calls.append((kind, index))
        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(content=json.dumps(payload, ensure_ascii=False)))
            ]
        )


class FakeFetcher(NewsFetcher):
    name = "fake"

    def __init__(self, count: int) -> None:
        self._count = count

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        return [
            NewsItem(
                source_uid=f"uid{i}",
                title=f"Anime News {i}",
                content=f"English body {i}",
                source="fake",
            )
            for i in range(self._count)
        ]


@pytest.fixture
def run_two_items():
    """跑一次 2 条资讯的工作流（0 号永不通过，1 号一次通过）"""

    def _run() -> dict:
        PerItemModel.calls = []
        settings = Settings(
            deepseek_api_key="t",
            llm_model="fake",
            aninews_enabled=False,
            news_fallback_rss="",
            news_enrich_enabled=False,
        )
        for factory in (N.make_translate_node, N.make_summarize_node, N.make_review_node):
            factory.__globals__["get_llm"] = (
                lambda temperature=None, max_tokens=None: PerItemModel()
            )

        workflow = build_news_workflow(settings, FakeFetcher(2))
        return workflow.invoke(
            {"limit": 5, "run_id": "routing-test", "items": {}, "log": [], "repair": False}
        )

    return _run


def count(calls: list, kind: str, index: int | None = None) -> int:
    return sum(
        1 for k, i in calls if k == kind and (index is None or i == index)
    )


class TestNoRedundantLoop:
    def test_passing_item_is_not_reworked(self, run_two_items):
        """核心回归：一次通过的条目不能被拉回去重做"""
        state = run_two_items()
        item = state["items"]["uid1"]

        assert item["stage"] == "approved"
        assert item["attempts"] == 1, "一次通过的条目 attempts 应为 1"
        assert len(item["review_history"]) == 1

    def test_passing_item_reviewed_exactly_once(self, run_two_items):
        run_two_items()

        assert count(PerItemModel.calls, "review", 1) == 1
        assert count(PerItemModel.calls, "summary", 1) == 1

    def test_failing_item_loops_exactly_max_times(self, run_two_items):
        state = run_two_items()
        item = state["items"]["uid0"]

        assert item["stage"] == "rejected"
        assert item["attempts"] == MAX_REVIEW_ATTEMPTS
        assert len(item["review_history"]) == MAX_REVIEW_ATTEMPTS
        assert count(PerItemModel.calls, "summary", 0) == MAX_REVIEW_ATTEMPTS
        assert count(PerItemModel.calls, "review", 0) == MAX_REVIEW_ATTEMPTS

    def test_translate_runs_once_per_item(self, run_two_items):
        """翻译没有回退路径：每个条目只该被翻译一次（扇出会放大成多次）"""
        run_two_items()

        assert count(PerItemModel.calls, "translate", 0) == 1
        assert count(PerItemModel.calls, "translate", 1) == 1
        assert count(PerItemModel.calls, "translate") == 2

    def test_total_calls_match_expectation(self, run_two_items):
        """总调用数精确匹配：2 次翻译 + (3+1) 次摘要 + (3+1) 次审核 = 10"""
        run_two_items()

        expected = 2 + (MAX_REVIEW_ATTEMPTS + 1) * 2
        assert len(PerItemModel.calls) == expected
        assert count(PerItemModel.calls, "summary") == MAX_REVIEW_ATTEMPTS + 1
        assert count(PerItemModel.calls, "review") == MAX_REVIEW_ATTEMPTS + 1

    def test_every_item_reaches_terminal_state(self, run_two_items):
        state = run_two_items()

        for uid, item in state["items"].items():
            assert item["stage"] in ("approved", "rejected"), f"{uid} 卡在 {item['stage']}"
