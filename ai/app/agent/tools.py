"""
LangChain 自定义工具

提供 Agent 可调用的动漫业务数据查询工具。

SQL 语句自重构前的 anime_tools.py 原样保留 —— anime / user_anime 等表
归 Java 后端所有，表结构未变；此处仅把数据访问入口改为 app.db.mysql。
"""

import json

from langchain.tools import tool

from app.db.mysql import execute_query

# 观看状态映射
WATCH_STATUS_MAP = {
    0: "未开始",
    1: "观看中",
    2: "已完成",
    3: "已放弃",
}


@tool
def get_user_anime_history(user_id: int) -> str:
    """
    获取用户的追番历史记录

    Args:
        user_id: 用户ID

    Returns:
        JSON格式的用户追番历史数据，包含动漫名称、观看状态、评分等信息
    """
    query = """
        SELECT 
            ua.id,
            ua.user_id,
            ua.anime_id,
            a.title as anime_title,
            ua.watch_status,
            ua.current_episode,
            ua.rating,
            ua.comment,
            ua.tags,
            ua.started_at,
            ua.finished_at,
            ua.created_at
        FROM user_anime ua
        LEFT JOIN anime a ON ua.anime_id = a.id
        WHERE ua.user_id = %s
        ORDER BY ua.updated_at DESC
    """

    result = execute_query(query, (user_id,))

    if not result:
        return json.dumps(
            {"error": "未找到该用户的追番记录", "user_id": user_id}, ensure_ascii=False
        )

    for item in result:
        item["watch_status_text"] = WATCH_STATUS_MAP.get(item["watch_status"], "未知")
        # 移除敏感字段
        item.pop("id", None)

    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_user_watching_animes(user_id: int) -> str:
    """
    获取用户正在观看的动漫列表

    Args:
        user_id: 用户ID

    Returns:
        JSON格式的当前观看中的动漫列表
    """
    query = """
        SELECT 
            ua.anime_id,
            a.title as anime_title,
            ua.current_episode,
            ua.started_at,
            ua.updated_at
        FROM user_anime ua
        LEFT JOIN anime a ON ua.anime_id = a.id
        WHERE ua.user_id = %s AND ua.watch_status = 1
        ORDER BY ua.updated_at DESC
    """

    result = execute_query(query, (user_id,))

    if not result:
        return json.dumps({"message": "当前没有正在观看的动漫"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_user_completed_animes(user_id: int) -> str:
    """
    获取用户已完成的动漫列表及评分

    Args:
        user_id: 用户ID

    Returns:
        JSON格式的已完成动漫列表，包含评分和评论
    """
    query = """
        SELECT 
            ua.anime_id,
            a.title as anime_title,
            ua.rating,
            ua.comment,
            ua.finished_at
        FROM user_anime ua
        LEFT JOIN anime a ON ua.anime_id = a.id
        WHERE ua.user_id = %s AND ua.watch_status = 2
        ORDER BY ua.rating DESC, ua.finished_at DESC
    """

    result = execute_query(query, (user_id,))

    if not result:
        return json.dumps({"message": "暂无已完成的动漫"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_user_favorite_genres(user_id: int) -> str:
    """
    分析用户喜欢的动漫类型（基于标签）

    Args:
        user_id: 用户ID

    Returns:
        JSON格式的用户偏好类型统计
    """
    query = """
        SELECT 
            ua.tags,
            a.title
        FROM user_anime ua
        LEFT JOIN anime a ON ua.anime_id = a.id
        WHERE ua.user_id = %s AND ua.tags IS NOT NULL AND ua.tags != ''
    """

    result = execute_query(query, (user_id,))

    if not result:
        return json.dumps({"message": "暂无标签数据"}, ensure_ascii=False)

    # 统计标签出现次数
    tag_count: dict[str, int] = {}
    for item in result:
        tags = item["tags"].split(",") if item["tags"] else []
        for tag in tags:
            tag = tag.strip()
            if tag:
                tag_count[tag] = tag_count.get(tag, 0) + 1

    sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)[:10]

    return json.dumps(
        {
            "top_genres": [{"tag": tag, "count": count} for tag, count in sorted_tags],
            "total_tagged_animes": len(result),
        },
        ensure_ascii=False,
    )


@tool
def get_anime_info(anime_id: int) -> str:
    """
    获取指定动漫的详细信息

    Args:
        anime_id: 动漫ID

    Returns:
        JSON格式的动漫详细信息
    """
    query = "SELECT * FROM anime WHERE id = %s"

    result = execute_query(query, (anime_id,), fetch_one=True)

    if not result:
        return json.dumps({"error": f"未找到ID为{anime_id}的动漫"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def search_anime_by_name(keyword: str) -> str:
    """
    根据关键词搜索动漫

    Args:
        keyword: 搜索关键词

    Returns:
        JSON格式的搜索结果列表
    """
    query = """
        SELECT id, title FROM anime 
        WHERE title LIKE %s 
        LIMIT 10
    """

    result = execute_query(query, (f"%{keyword}%",))

    if not result:
        return json.dumps({"message": f"未找到包含'{keyword}'的动漫"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


@tool
def get_user_watch_statistics(user_id: int) -> str:
    """
    获取用户的观看统计数据

    Args:
        user_id: 用户ID

    Returns:
        JSON格式的观看统计信息
    """
    query = """
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE WHEN watch_status = 0 THEN 1 ELSE 0 END) as not_started,
            SUM(CASE WHEN watch_status = 1 THEN 1 ELSE 0 END) as watching,
            SUM(CASE WHEN watch_status = 2 THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN watch_status = 3 THEN 1 ELSE 0 END) as dropped,
            AVG(rating) as avg_rating
        FROM user_anime
        WHERE user_id = %s
    """

    result = execute_query(query, (user_id,), fetch_one=True)

    if not result or result["total_count"] == 0:
        return json.dumps({"message": "该用户暂无观看记录"}, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False, default=str)


# 导出所有工具
ANIME_TOOLS = [
    get_user_anime_history,
    get_user_watching_animes,
    get_user_completed_animes,
    get_user_favorite_genres,
    get_anime_info,
    search_anime_by_name,
    get_user_watch_statistics,
]
