"""
暴露给 Agent 的 B 站工具

工具名与描述直接决定模型什么时候调用它，因此写清了：
- 什么时候用（用户想找视频看）
- 返回什么（带可点击链接，模型要原样给出）
- 参数含义（keyword 应为作品名）
"""

import json
import logging

from langchain_core.tools import tool

from app.config import get_settings
from app.mcp.bilibili import get_bilibili_service
from app.mcp.stdio_client import McpError

logger = logging.getLogger(__name__)

#: 工具返回给模型的最多条数上限
MAX_LIMIT = 10


def _error(message: str) -> str:
    """统一的失败返回：结构化 JSON，便于模型转述给用户"""
    return json.dumps(
        {"success": False, "error": message, "recommendations": []},
        ensure_ascii=False,
    )


@tool
def recommend_bilibili_videos(keyword: str, limit: int = 5) -> str:
    """
    在 B 站搜索并推荐相关视频，返回可直接点击的播放链接。

    适合的场景：
    - 用户想找某部动漫/某个主题的视频来看（如「推荐一些关于斩服少女的视频」）
    - 用户想看解说、MAD、剪辑、评测、名场面合集等
    - 结合用户追番记录做「下一步看什么」的推荐

    视频按综合热度排序（播放量、点赞、收藏、投币、弹幕、评论加权），
    每条都带标题、UP主、播放量、点赞数、时长和 https://www.bilibili.com/video/BVxxx 链接。

    Args:
        keyword: 搜索关键词，通常是动漫作品名或主题（如「斩服少女」「进击的巨人 解说」）
        limit: 返回条数，1-10，默认 5

    Returns:
        JSON 字符串：{"success": bool, "keyword": str, "recommendations": [...]}
        每条推荐包含 title / author / url / play / like / duration / score 等字段。
    """
    settings = get_settings()
    if not settings.bilibili_mcp_enabled:
        return _error("B站视频推荐功能当前已关闭")

    limit = max(1, min(int(limit or 5), MAX_LIMIT))

    try:
        result = get_bilibili_service().recommend(keyword, limit)
    except McpError as exc:
        logger.warning("B站推荐失败 keyword=%s: %s", keyword, exc)
        return _error(f"B站服务调用失败：{exc}")
    except Exception as exc:  # noqa: BLE001 - 工具不能把异常抛给图执行
        logger.exception("B站推荐异常 keyword=%s: %s", keyword, exc)
        return _error("B站服务异常，请稍后再试")

    recommendations = result.get("recommendations") or []
    if not recommendations:
        return _error(result.get("note") or "没有搜索到相关视频")

    return json.dumps(
        {
            "success": True,
            "keyword": result.get("keyword") or keyword,
            "total": result.get("total", len(recommendations)),
            "recommendations": recommendations,
            "note": result.get("note") or "",
            "usage_hint": (
                "请把每条推荐的标题、UP主、播放量/点赞数、时长和 url 一起告诉用户，"
                "url 必须原样输出，方便用户点击跳转到 B 站。"
            ),
        },
        ensure_ascii=False,
    )


#: 供 Agent 注册的 B 站工具集合
BILIBILI_TOOLS = [recommend_bilibili_videos]
