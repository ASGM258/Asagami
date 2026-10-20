"""
知识库使用策略（Agent 中间件）

**要解决的问题**：模型不会主动查知识库。
用户问「绫弥一条的评价」，模型不认识这个名字，直接答"没有相关资料"；
用户提醒"RAG 里有"，它才去检索。

**根因**：模型不知道知识库里有什么。system prompt 里那句
「当用户的问题可能涉及站内已上传的文档时，先调用 search_knowledge_base」
要求模型自己判断相关性，但它手里没有清单，判断不了就只能放弃。

**做法**：每轮开始时把当前知识库清单作为一条 SystemMessage 注入上下文，
并把规则改成「任何具体角色名／作品名／专有名词，必须先检索再回答；
未检索不得声称没有资料」。这样「绫弥一条」与文件名「绫弥一条简介.txt」
对得上，模型自然会去搜。

实现细节：
- 只在**每轮开头**注入（最后一条消息是 HumanMessage 时），工具循环中不重复注入
- 使用**固定 message id**，下一轮通过 `add_messages` 原地替换，不会越积越多
- 注入的 SystemMessage 带 `lc_source` 标记，历史接口与流式过滤器都会把它挡掉
"""

import logging

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage

from app.rag.store import get_knowledge_store

logger = logging.getLogger(__name__)

#: 注入消息的固定 id：同 id 会被 add_messages 原地替换，避免每轮堆一条
KNOWLEDGE_HINT_ID = "knowledge-inventory-hint"

#: 注入消息的来源标记（历史接口/流式过滤器据此识别并隐藏）
KNOWLEDGE_HINT_SOURCE = "knowledge-hint"

#: 清单里最多列出的文件名数量（防止知识库很大时把 prompt 撑爆）
MAX_LISTED_FILES = 20


def build_knowledge_hint(files: list[dict]) -> str | None:
    """
    生成「知识库清单 + 使用规则」提示

    Args:
        files: `KnowledgeStore.list_sources()` 的结果（[{source, chunks}]）

    Returns:
        提示文本；知识库为空时返回 None（不注入，避免噪音）
    """
    if not files:
        return None

    names = [str(item.get("source") or "").strip() for item in files]
    names = [name for name in names if name]
    if not names:
        return None

    total_chunks = sum(int(item.get("chunks") or 0) for item in files)
    listed = names[:MAX_LISTED_FILES]
    more = len(names) - len(listed)

    file_list = "、".join(listed) + (f" 等 {len(names)} 个文件" if more > 0 else "")

    return (
        "【站内知识库】当前已上传 "
        f"{len(names)} 个文件（{total_chunks} 个片段）：{file_list}\n"
        "使用规则：\n"
        "1. 用户问到任何**具体角色名、作品名、人名、术语、设定**时，"
        "必须先调用 search_knowledge_base 检索，再基于检索结果回答。\n"
        "2. 上面列出的文件名里包含哪个关键词，就说明站内大概率有该资料 —— "
        "尤其当用户提到的名字与某个文件名重合时，必须检索。\n"
        "3. **未检索之前，不允许回答「没有相关资料」或「知识库中没有」**；"
        "只有检索结果为空时才可以这么说，并明确告知"
        "「站内知识库未收录，以下内容来自通用知识」。\n"
        "4. 引用站内资料时标明出处文件名。"
    )


class KnowledgeHintMiddleware(AgentMiddleware):
    """
    每轮注入知识库清单

    在 `before_model` 阶段执行：最后一条消息是 HumanMessage 时，说明这是一轮
    的新起点（而不是工具调用后的续写），此时注入清单提示。
    """

    def __init__(self, store_provider=None) -> None:
        #: 便于测试注入假 store
        self._store_provider = store_provider or get_knowledge_store

    def before_model(self, state, runtime):  # noqa: ANN001 - 签名由框架约定
        messages = state.get("messages") or []
        if not messages:
            return None

        # 只在本轮开头注入：工具调用后的续写不重复注入
        if not isinstance(messages[-1], HumanMessage):
            return None

        try:
            files = self._store_provider().list_sources()
        except Exception as exc:  # noqa: BLE001 - 知识库不可用不应阻断对话
            logger.warning("[知识库提示] 读取文件清单失败，本轮不注入清单: %s", exc)
            return None

        hint = build_knowledge_hint(files)
        if hint is None:
            return None

        return {
            "messages": [
                SystemMessage(
                    content=hint,
                    id=KNOWLEDGE_HINT_ID,
                    additional_kwargs={"lc_source": KNOWLEDGE_HINT_SOURCE},
                )
            ]
        }
