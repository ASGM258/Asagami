"""
资讯工作流状态定义

采用「字典 + 归约器」结构承载多条资讯：

    items: {source_uid: NewsItem字典}

每个节点只返回自己改动的那些条目，由 `merge_items` 归约器合并，
因此 translate / summarize / review 节点可以按条目独立推进，
审核不通过时仅把该条目回退重做，不影响其他条目。
"""

from typing import Annotated, Any, TypedDict


def merge_items(
    left: dict[str, dict] | None, right: dict[str, dict] | None
) -> dict[str, dict]:
    """
    条目字典归约器

    Args:
        left: 已有条目
        right: 本次更新（按 source_uid 覆盖或新增）

    Returns:
        合并后的完整条目字典
    """
    merged: dict[str, dict] = dict(left or {})
    if right:
        for key, value in right.items():
            merged[key] = value
    return merged


def append_str(left: list[str] | None, right: list[str] | None) -> list[str]:
    """字符串列表归约器（用于运行日志）"""
    return list(left or []) + list(right or [])


class NewsWorkflowState(TypedDict, total=False):
    """资讯智能体工作流状态"""

    # 本轮运行的资讯条目：{source_uid: NewsItem.to_dict()}
    items: Annotated[dict[str, dict], merge_items]

    # 本次运行标识（日志用）
    run_id: str

    # 抓取条数上限
    limit: int

    # 是否修复已有条目：为 True 时，已入库但正文残缺（早于正文补全功能）
    # 的条目会重新走一遍流水线，由 upsert 覆盖为完整正文
    repair: bool

    # 各阶段运行日志
    log: Annotated[list[str], append_str]


# ==================== 条目状态常量 ====================

STAGE_FETCHED = "fetched"
STAGE_TRANSLATED = "translated"
STAGE_SUMMARIZED = "summarized"
STAGE_APPROVED = "approved"
STAGE_REJECTED = "rejected"

# 审核未通过时允许的重做次数上限（含首次摘要，共 3 次尝试）
MAX_REVIEW_ATTEMPTS = 3


def item_updates(items: dict[str, dict]) -> dict[str, Any]:
    """把条目字典包装为节点返回值"""
    return {"items": items}


def pending(items: dict[str, dict], stage: str) -> dict[str, dict]:
    """筛选处于指定阶段的条目"""
    return {k: v for k, v in items.items() if v.get("stage") == stage}


def is_terminal(stage: str | None) -> bool:
    """判断条目是否已到终态"""
    return stage in (STAGE_APPROVED, STAGE_REJECTED)
