"""
资讯智能体工作流（LangGraph）

工作流拓扑：

    fetch ──► translate ──► summarize ──► review ──┬──► finalize ──► END
                              ▲                   │
                              └───────────────────┘  审核未通过且未达上限 → 重做

**为什么不用 `Send` 扇出**：
早先的实现用 `Send` 让每个条目独立流入下一节点。但 `Send` 会让**下游节点与
其后续路由函数各执行一次**（N 个条目 = N 次路由），而路由函数读到的是
「部分合并」的全局状态，于是会出现：

- 已经 `approved` 的条目在另一次路由调用里又被看成 `summarized`，被拉回重做
- `attempts` 被重复累加，直接冲到上限，本该 1 轮通过的条目也走满 3 轮

因此改成**线性编排**：每个节点内部遍历所有条目、只处理自己负责的阶段，
轮次之间用一条条件边决定「继续重做」还是「进入汇总」。节点本来就是逐条
串行调模型，去掉扇出不会损失任何并行度，却消除了重复与循环。
"""

import logging

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.news.fetchers import NewsFetcher
from app.news.nodes import (
    make_fetch_node,
    make_finalize_node,
    make_review_node,
    make_summarize_node,
    make_translate_node,
)
from app.news.state import (
    MAX_REVIEW_ATTEMPTS,
    STAGE_SUMMARIZED,
    NewsWorkflowState,
    is_terminal,
)

logger = logging.getLogger(__name__)

# 节点名
NODE_FETCH = "fetch"
NODE_TRANSLATE = "translate"
NODE_SUMMARIZE = "summarize"
NODE_REVIEW = "review"
NODE_FINALIZE = "finalize"


# ==================== 路由 ====================


def route_after_review(state: NewsWorkflowState, runtime=None):
    """
    审核结果路由

    只做一次判断（整张图每个超步只调用一次，避免逐条重复路由）：
    - 还有条目处于 `summarized` 且未达重做上限 → 回到摘要重做
    - 否则 → 进入汇总

    审核节点已把「未通过且达上限」的条目置为 `rejected`，
    因此这里不会无限循环。
    """
    for item in (state.get("items") or {}).values():
        stage = item.get("stage")
        if is_terminal(stage):
            continue
        if stage != STAGE_SUMMARIZED:
            continue
        if int(item.get("attempts") or 0) < MAX_REVIEW_ATTEMPTS:
            return NODE_SUMMARIZE
        # 理论上 review 已置 rejected；这里兜底，避免卡在 summarized 出不去
        return NODE_FINALIZE

    return NODE_FINALIZE


# ==================== 图构建 ====================


def build_news_workflow(settings: Settings, fetcher: NewsFetcher):
    """
    构建资讯智能体工作流

    Args:
        settings: 配置
        fetcher: 抓取源（主源 + 备用源的组合）

    Returns:
        编译后的 LangGraph 图
    """
    graph = StateGraph(NewsWorkflowState)

    graph.add_node(NODE_FETCH, make_fetch_node(fetcher))
    graph.add_node(NODE_TRANSLATE, make_translate_node(settings))
    graph.add_node(NODE_SUMMARIZE, make_summarize_node(settings))
    graph.add_node(NODE_REVIEW, make_review_node(settings))
    graph.add_node(NODE_FINALIZE, make_finalize_node())

    graph.add_edge(START, NODE_FETCH)

    # 线性编排：每个节点自行遍历条目、只处理自己负责的阶段
    graph.add_edge(NODE_FETCH, NODE_TRANSLATE)
    graph.add_edge(NODE_TRANSLATE, NODE_SUMMARIZE)
    graph.add_edge(NODE_SUMMARIZE, NODE_REVIEW)

    # 审核后：未通过的条目回退重做，其余进入汇总
    graph.add_conditional_edges(
        NODE_REVIEW, route_after_review, [NODE_SUMMARIZE, NODE_FINALIZE]
    )

    graph.add_edge(NODE_FINALIZE, END)

    compiled = graph.compile()
    logger.info(
        "资讯智能体工作流已构建: 线性编排 节点=%s",
        [NODE_FETCH, NODE_TRANSLATE, NODE_SUMMARIZE, NODE_REVIEW, NODE_FINALIZE],
    )
    return compiled
