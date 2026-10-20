"""
知识库检索工具（供 Agent 调用）

把 RAG 能力包装成 LangChain 工具，Agent 会在需要站内知识时自行调用。
"""

import json
import logging

from langchain.tools import tool

from app.rag.store import get_knowledge_store

logger = logging.getLogger(__name__)

# 默认返回条数
DEFAULT_TOP_K = 4

# 单条片段在工具结果里的最大长度，避免上下文过长
SNIPPET_MAX_LENGTH = 600


@tool
def search_knowledge_base(query: str) -> str:
    """
    检索站内知识库（用户上传的文档：角色设定、作品资料、访谈、考据、攻略等）

    **什么时候必须调用**：
    - 用户提到任何具体的角色名、作品名、人名、术语、专有设定 —— 一律先检索
    - 用户明确问「站内/知识库里有没有 X」时
    - 你对该专有名词没有把握、或不确定站内是否收录时

    **不要做的事**：在没有调用本工具的情况下回答「没有相关资料」「知识库中没有」。
    只有本工具返回「未找到」时，才可以断定站内没有。

    与数据库工具的区别：本工具检索的是「文档原文」，不是动漫/追番数据。

    Args:
        query: 检索关键词或问题（中文即可，通常是角色名/作品名/术语）

    Returns:
        JSON：命中时含片段内容、出处文件名与相似度；未命中时给出明确提示
    """
    try:
        store = get_knowledge_store()
    except RuntimeError:
        return json.dumps(
            {"error": "知识库尚未初始化"}, ensure_ascii=False
        )

    try:
        total = store.count()
    except Exception as exc:  # noqa: BLE001
        logger.error("[RAG] 读取知识库失败: %s", exc)
        return json.dumps({"error": f"知识库不可用: {exc}"}, ensure_ascii=False)

    if total == 0:
        return json.dumps(
            {
                "message": "知识库为空，尚无用户上传的文档",
                "hint": "可在左侧导航栏底部上传 txt / md / pdf 知识文件；"
                "此时请用通用知识回答，并说明站内没有资料",
                "found": False,
            },
            ensure_ascii=False,
        )

    hits = store.search(query, top_k=DEFAULT_TOP_K)
    if not hits:
        return json.dumps(
            {
                "message": f"站内知识库未收录与「{query}」相关的内容",
                "totalChunks": total,
                "found": False,
                "hint": "检索已完成且确实为空：可以用通用知识继续回答，"
                "但要明确告知用户「以下内容来自通用知识，不是站内资料」",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "query": query,
            "totalChunks": total,
            "found": True,
            "embeddingProvider": store.embeddings.name,
            "results": [
                {
                    "content": (
                        hit.content[:SNIPPET_MAX_LENGTH]
                        + ("..." if len(hit.content) > SNIPPET_MAX_LENGTH else "")
                    ),
                    "source": hit.source,
                    "chunkIndex": hit.chunk_index,
                    "score": hit.score,
                }
                for hit in hits
            ],
        },
        ensure_ascii=False,
    )


# 供 Agent 注册的工具列表
KNOWLEDGE_TOOLS = [search_knowledge_base]
