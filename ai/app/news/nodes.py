"""
资讯智能体工作流的四个节点

    fetch     抓取 agent —— 从 AniNewsAPI（或备用 RSS）拉取并归一化
    translate 翻译 agent —— 英文资讯翻译为中文，不改写事实
    summarize 摘要 agent —— 生成摘要并去除敏感信息；带审核反馈时重做
    review    审核 agent —— 判定是否可发布，不通过则回退到摘要

审核不通过时由 review 节点把条目 stage 改回 `summarized` 并携带反馈，
再由条件边路由回 summarize 重做，最多 MAX_REVIEW_ATTEMPTS 次；
仍未通过则标记 rejected 并记录原因。
"""

import json
import logging
import re
from typing import Any

from app.config import Settings, get_settings
from app.news.fetchers import NewsItem, NewsFetcher, enrich_items
from app.news.llm import get_llm
from app.news.repository import NewsRepository
from app.news.state import (
    MAX_REVIEW_ATTEMPTS,
    STAGE_APPROVED,
    STAGE_FETCHED,
    STAGE_REJECTED,
    STAGE_SUMMARIZED,
    STAGE_TRANSLATED,
    item_updates,
)
from app.utils.ids import new_run_id

logger = logging.getLogger(__name__)

# 摘要长度上限（字符）
SUMMARY_MAX_LENGTH = 160
# 摘要 / 审核节点送入模型的正文字符上限（只需判断要点，可截断）
CONTENT_PROMPT_LIMIT = 2000
# 翻译节点送入模型的正文字符上限
# 必须足够大：翻译结果会作为正文入库，截断会导致译文残缺（审核会判定不通过）
TRANSLATE_PROMPT_LIMIT = 8000

# 允许的资讯分类（与 repository.CATEGORY_NAMES 保持一致，前端筛选标签用）
ALLOWED_CATEGORIES = ("动画", "漫画", "声优", "游戏", "活动")
# 无法判定时的默认分类
DEFAULT_CATEGORY = "动画"


def normalize_category(raw: Any) -> str | None:
    """
    归一化模型给出的分类

    只接受预置分类；无法判定时返回 None，由调用方按正文关键词兜底。
    """
    if not raw:
        return None
    text = str(raw).strip()
    for name in ALLOWED_CATEGORIES:
        if name in text:
            return name
    return None


def guess_category(text: str) -> str:
    """
    按关键词兜底猜测分类

    模型未给出分类时使用，保证前端筛选标签始终有值。
    """
    if not text:
        return DEFAULT_CATEGORY

    lowered = text.lower()
    # 顺序即优先级：声优/游戏/活动 特征词更具体，先判断
    rules = (
        ("声优", ("声优", "配音", "cast", "voice actor", "cv")),
        ("游戏", ("游戏", "手游", "主机", "game", "rpg", "switch", "ps5")),
        ("活动", ("活动", "展会", "演唱会", "event", "live", "concert", "展览")),
        ("漫画", ("漫画", "连载", "单行本", "manga", "轻小说", "小说")),
        ("动画", ("动画", "番剧", "新番", "anime", "tv", "剧场版", "电影", "pv")),
    )
    for name, keywords in rules:
        if any(keyword in lowered for keyword in keywords):
            return name
    return DEFAULT_CATEGORY

# ==================== 敏感信息清洗 ====================

# 兜底规则：即使模型未清洗干净，也用正则再扫一遍
SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "[邮箱已隐藏]"),
    (r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号已隐藏]"),
    (r"(?<!\d)\d{17}[\dXx](?!\d)", "[证件号已隐藏]"),
    (r"(?<!\d)\d{16,19}(?!\d)", "[卡号已隐藏]"),
    (r"(?i)\b(sk-[A-Za-z0-9]{8,})\b", "[密钥已隐藏]"),
    (r"https?://\S+", "[链接已移除]"),
]


def sanitize_text(text: str) -> str:
    """
    清洗敏感信息

    摘要 agent 的职责之一：去除邮箱、手机号、证件号、卡号、
    密钥与外部链接，避免资讯正文携带个人或敏感信息。

    Args:
        text: 原始文本

    Returns:
        清洗后的文本
    """
    if not text:
        return ""
    cleaned = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        cleaned = re.sub(pattern, replacement, cleaned)
    return cleaned


def truncate(text: str, limit: int) -> str:
    """按字符数截断并追加省略号"""
    if not text:
        return ""
    return text[:limit] + "..." if len(text) > limit else text


def truncate_at_sentence(text: str, limit: int) -> str:
    """
    在句子边界处截断

    直接按字符截断会把单词/句子劈开，导致译文末尾出现英文残缺，
    因此优先回退到最近的句末标点；找不到时才退回硬截断。

    Args:
        text: 原始文本
        limit: 字符上限

    Returns:
        截断后的文本
    """
    if not text or len(text) <= limit:
        return text or ""

    head = text[:limit]
    # 在窗口内寻找最后一个句末标点（中英文都考虑）
    boundary = max(head.rfind(mark) for mark in ("。", "！", "？", ".", "!", "?", "\n"))
    if boundary >= limit // 2:
        return head[: boundary + 1]
    return head


# ==================== 模型输出解析 ====================


def _strip_code_fence(text: str) -> str:
    """去掉模型偶尔包裹的 markdown 代码块"""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def parse_json_response(text: str) -> dict[str, Any]:
    """
    解析模型返回的 JSON

    容错处理：去除代码块包裹、截取首个花括号区间；
    解析失败时返回空字典，由调用方走兜底逻辑。
    """
    cleaned = _strip_code_fence(text)
    if not cleaned:
        return {}

    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(cleaned[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


# ==================== 1. 抓取 agent ====================


def make_fetch_node(fetcher: NewsFetcher):
    """构造抓取节点"""

    def fetch_node(state: dict[str, Any]) -> dict[str, Any]:
        wanted = int(state.get("limit") or 20)
        settings = get_settings()
        # 已入库条目会被丢弃，因此需要多抓一些才能凑够 wanted 条新内容。
        # RSS 源没有翻页能力，每次都返回同一批条目，这个放大尤其必要。
        over_fetch = max(1, int(settings.news_fetch_over_fetch))
        fetch_count = min(wanted * over_fetch, settings.news_fetch_limit)

        logger.info(
            "[抓取agent] 开始抓取资讯, 目标=%d 条, 实际抓取上限=%d 条(放大 %d 倍)",
            wanted, fetch_count, over_fetch,
        )

        try:
            items = fetcher.fetch(fetch_count)
        except Exception as exc:  # noqa: BLE001 - 抓取失败不应中断整个工作流
            logger.exception("[抓取agent] 抓取异常: %s", exc)
            items = []

        # 丢弃已入库的条目：内容不会变，重新走翻译+摘要+审核只会浪费模型调用，
        # 还有可能覆盖已发布的内容。
        existing = NewsRepository.existing_source_uids([i.source_uid for i in items])

        # 修复模式：正文补全功能上线前入库的条目，正文只是 RSS 摘要（被截断），
        # 但它们因 source_uid 已存在会被去重跳过，永远得不到更新。
        # 这里挑出这些条目重新送入流水线，由 upsert 的 ON DUPLICATE KEY UPDATE 覆盖。
        repair_uids: set[str] = set()
        if state.get("repair"):
            duplicates = [i.source_uid for i in items if i.source_uid in existing]
            repair_uids = NewsRepository.truncated_source_uids(
                duplicates, settings.news_enrich_min_chars
            )
            if repair_uids:
                logger.info(
                    "[抓取agent] 修复模式：%d 条正文残缺的已入库资讯将重新处理",
                    len(repair_uids),
                )

        fresh = [
            item
            for item in items
            if item.source_uid not in existing or item.source_uid in repair_uids
        ]
        skipped = len(items) - len(fresh)

        # 只处理目标条数
        fresh = fresh[:wanted]

        # 正文补全：RSS 源只给摘要（约百字~数百字且在词中间截断），
        # 必须回到详情页抓全文，否则入库的就是残缺内容。
        # 放在去重与截断之后，避免为已入库的旧条目白白发请求。
        try:
            fresh = enrich_items(fresh, settings)
        except Exception as exc:  # noqa: BLE001 - 补全失败不应中断工作流
            logger.exception("[抓取agent] 正文补全异常: %s", exc)

        logger.info(
            "[抓取agent] 抓取 %d 条，其中 %d 条是已入库的旧内容（跳过），%d 条新内容进入流水线",
            len(items), skipped, len(fresh),
        )

        mapped = {item.source_uid: item.to_dict() for item in fresh}

        return {
            "items": mapped,
            "log": [
                f"[抓取agent] 抓取 {len(items)} 条，跳过已入库 {skipped} 条，"
                f"{len(mapped)} 条新内容进入流水线"
            ],
        }

    return fetch_node


# ==================== 2. 翻译 agent ====================


def _translate_item(item: NewsItem, settings: Settings, force: bool = False) -> NewsItem:
    """
    翻译单条资讯并归类

    已是中文的内容跳过翻译，但仍会补齐分类（RSS 源通常不提供分类）。

    Args:
        item: 待处理条目
        settings: 配置
        force: 强制翻译。修复历史数据时必须为 True ——
               那些条目的标题已经是中文，正文却是英文摘要，
               按「含中文就跳过」的规则会漏翻。
    """
    body = item.content or item.summary
    if not body.strip():
        item.stage = STAGE_TRANSLATED
        return item

    already_chinese = bool(re.search(r"[\u4e00-\u9fff]", item.title + body))

    if already_chinese and not force:
        logger.info("[翻译agent] 内容已含中文，跳过翻译: %s", item.source_uid)
        if not item.category:
            item.category = guess_category(f"{item.title} {body}")
        item.stage = STAGE_TRANSLATED
        return item

    llm = get_llm(settings.llm_translate_temperature, max_tokens=settings.news_llm_max_tokens)

    # 输入上限：整篇正文都要翻，截太狠会译文残缺
    input_limit = int(settings.news_translate_input_limit or TRANSLATE_PROMPT_LIMIT)

    prompt = f"""你是专业的动漫资讯译者与编辑。请把下面的英文动漫资讯翻译成简体中文，并判断分类。

要求：
1. 忠实原意，不增删信息，不做主观评论
2. 动漫作品名、角色名、公司名、声优名保留原文或通用译名
3. 保持新闻语气，语句通顺
4. category 只能从以下五个值中选择一个：动画、漫画、声优、游戏、活动
5. 只输出 JSON，不要任何解释或代码块标记

输出格式：
{{"title": "翻译后的标题", "content": "翻译后的正文", "category": "分类"}}

英文标题：{item.title}

英文正文：
{truncate_at_sentence(body, input_limit)}"""

    try:
        response = llm.invoke(prompt)
        data = parse_json_response(getattr(response, "content", "") or "")
    except Exception as exc:  # noqa: BLE001 - 单条失败不影响其他条目
        logger.error("[翻译agent] 调用模型失败: %s", exc)
        data = {}

    translated_title = str(data.get("title") or "").strip()
    translated_content = str(data.get("content") or "").strip()

    if translated_title:
        item.title = translated_title
    if translated_content:
        item.content = translated_content
        item.summary = translated_content[:SUMMARY_MAX_LENGTH]

    # 分类：模型给出的优先，其次按关键词兜底，保证前端筛选项有值
    item.category = (
        normalize_category(data.get("category"))
        or item.category
        or guess_category(f"{item.title} {item.content or body}")
    )

    item.language = "zh"
    item.stage = STAGE_TRANSLATED
    return item


def make_translate_node(settings: Settings):
    """构造翻译节点"""

    def translate_node(state: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, dict] = {}
        count = 0

        for uid, raw in (state.get("items") or {}).items():
            if raw.get("stage") != STAGE_FETCHED:
                continue

            item = NewsItem.from_dict(raw)
            try:
                item = _translate_item(item, settings)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[翻译agent] 处理失败 uid=%s: %s", uid, exc)
                # 翻译失败仍推进阶段，保留原文，交由审核判断
                item.stage = STAGE_TRANSLATED

            updates[uid] = item.to_dict()
            count += 1

        logger.info("[翻译agent] 完成 %d 条翻译", count)

        result = item_updates(updates)
        result["log"] = [f"[翻译agent] 处理 {count} 条"]
        return result

    return translate_node


# ==================== 3. 摘要 agent ====================


def _summarize_item(item: NewsItem, settings: Settings) -> NewsItem:
    """
    生成摘要并去除敏感信息

    若条目带有审核反馈（review_feedback），说明上一轮审核未通过，
    本轮需按反馈重做摘要。
    """
    llm = get_llm(settings.llm_summary_temperature)
    feedback = item.review_feedback or ""

    feedback_block = ""
    if feedback:
        feedback_block = (
            "\n【重要】上一次审核未通过，原因如下，请针对性修正后重新生成：\n"
            f"{feedback}\n"
        )

    prompt = f"""你是动漫资讯编辑。请为下面的资讯生成摘要，并清理敏感信息。

要求：
1. 摘要长度不超过 {SUMMARY_MAX_LENGTH} 个汉字，概括核心事实（作品名、时间、阵容、事件）
2. 必须去除以下内容：邮箱、手机号、身份证号、银行卡号、API密钥、外部链接
3. 若出现上述敏感信息，用「[已隐藏]」替代
4. 不要编造原文没有的信息
5. 只输出 JSON，不要任何解释或代码块标记

输出格式：
{{"summary": "摘要内容", "title": "清理敏感信息后的标题"}}
{feedback_block}
标题：{item.title}

正文：
{truncate(item.content or item.summary, CONTENT_PROMPT_LIMIT)}"""

    try:
        response = llm.invoke(prompt)
        data = parse_json_response(getattr(response, "content", "") or "")
    except Exception as exc:  # noqa: BLE001
        logger.error("[摘要agent] 调用模型失败: %s", exc)
        data = {}

    summary = str(data.get("summary") or "").strip()
    title = str(data.get("title") or "").strip()

    if title:
        item.title = title
    # 模型未给出摘要时，用正文兜底
    item.summary = summary or truncate(sanitize_text(item.content), SUMMARY_MAX_LENGTH)
    # 正则兜底清洗，确保敏感信息不会漏网
    item.summary = sanitize_text(item.summary)
    item.title = sanitize_text(item.title)
    item.content = sanitize_text(item.content)

    # 记录本轮审核意见，供审核节点判断重做是否生效
    item.attempts += 1
    item.stage = STAGE_SUMMARIZED
    return item


def make_summarize_node(settings: Settings):
    """构造摘要节点"""

    def summarize_node(state: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, dict] = {}
        count = 0

        for uid, raw in (state.get("items") or {}).items():
            # 首次进入为 translated；审核回退后为 summarized（带反馈）
            if raw.get("stage") not in (STAGE_TRANSLATED, STAGE_SUMMARIZED):
                continue

            item = NewsItem.from_dict(raw)
            try:
                item = _summarize_item(item, settings)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[摘要agent] 处理失败 uid=%s: %s", uid, exc)
                item.attempts += 1
                item.stage = STAGE_SUMMARIZED

            updates[uid] = item.to_dict()
            count += 1

        logger.info("[摘要agent] 完成 %d 条摘要", count)

        result = item_updates(updates)
        result["log"] = [f"[摘要agent] 处理 {count} 条"]
        return result

    return summarize_node


# ==================== 4. 审核 agent ====================


REVIEW_PROMPT_TEMPLATE = """你是动漫资讯平台的审核员。请审核下面这条资讯是否可以发布。

审核标准：
1. 内容必须与动漫/漫画/番剧/ACG 相关（游戏、声优、活动、周边也算相关）
2. 中文表达完整通顺，标题与正文不为空、无翻译残缺或乱码
3. 不包含敏感信息（邮箱、手机号、身份证号、银行卡号、API密钥）与广告垃圾内容
4. 摘要能概括正文要点

只输出 JSON，不要任何解释或代码块标记：
{{"passed": true 或 false, "reason": "判定理由，不超过50字"}}

标题：{title}

摘要：{summary}

正文（截断）：
{content}"""


def _review_item(item: NewsItem, settings: Settings) -> tuple[bool, str]:
    """
    审核单条资讯

    Returns:
        (是否通过, 审核意见)
    """
    llm = get_llm(settings.llm_review_temperature)

    prompt = REVIEW_PROMPT_TEMPLATE.format(
        title=item.title or "(空)",
        summary=item.summary or "(空)",
        content=truncate(item.content, CONTENT_PROMPT_LIMIT) or "(空)",
    )

    try:
        response = llm.invoke(prompt)
        data = parse_json_response(getattr(response, "content", "") or "")
    except Exception as exc:  # noqa: BLE001 - 审核调用失败按不通过处理，进入重做
        logger.error("[审核agent] 调用模型失败: %s", exc)
        return False, f"审核服务异常：{exc}"

    # 模型未按格式返回时，默认不通过，避免有问题的内容直接发布
    if "passed" not in data:
        logger.warning(
            "[审核agent] 模型返回格式异常，按不通过处理: 原始返回=%r",
            (getattr(response, "content", "") or "")[:200],
        )
        return False, "审核结果格式异常，无法确认通过"

    passed = bool(data.get("passed"))
    reason = str(data.get("reason") or "").strip() or ("审核通过" if passed else "未说明原因")

    # 硬性兜底：本地再校验一次必填字段与敏感信息
    if passed:
        if not item.title.strip() or not item.summary.strip():
            logger.info("[审核agent] 兜底拦截：标题或摘要为空")
            return False, "标题或摘要为空"
        if has_residual_sensitive(item.summary) or has_residual_sensitive(item.title):
            logger.info(
                "[审核agent] 兜底拦截：仍存在敏感信息, title=%r summary=%r",
                item.title[:60], item.summary[:60],
            )
            return False, "仍存在未清理的敏感信息"

    return passed, reason


def has_residual_sensitive(text: str) -> bool:
    """检查文本中是否仍残留敏感信息模式"""
    if not text:
        return False
    for pattern, _ in SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def make_review_node(settings: Settings):
    """构造审核节点"""

    def review_node(state: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, dict] = {}
        passed_count = 0
        rework_count = 0
        rejected_count = 0

        for uid, raw in (state.get("items") or {}).items():
            if raw.get("stage") != STAGE_SUMMARIZED:
                continue

            item = NewsItem.from_dict(raw)
            try:
                passed, reason = _review_item(item, settings)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[审核agent] 审核异常 uid=%s: %s", uid, exc)
                passed, reason = False, f"审核异常：{exc}"

            item.review_reason = reason
            item.review_feedback = reason
            # 记录本次真实判定，落库时写入 news_review_log 供追溯
            item.review_history = list(item.review_history) + [
                {"attempt": max(item.attempts, 1), "passed": bool(passed), "reason": reason}
            ]

            if passed:
                item.stage = STAGE_APPROVED
                passed_count += 1
            elif item.attempts >= MAX_REVIEW_ATTEMPTS:
                # 超过允许的尝试次数，标记 rejected 并记录原因
                item.stage = STAGE_REJECTED
                rejected_count += 1
                logger.warning(
                    "[审核agent] 超过 %d 次未通过，标记 rejected: uid=%s, reason=%s",
                    MAX_REVIEW_ATTEMPTS,
                    uid,
                    reason,
                )
            else:
                # 回退到摘要节点重做（stage 置回 summarized 触发重做路由）
                item.stage = STAGE_SUMMARIZED
                rework_count += 1
                logger.info(
                    "[审核agent] 第 %d 次审核未通过，回退重做: uid=%s, reason=%s",
                    item.attempts,
                    uid,
                    reason,
                )

            updates[uid] = item.to_dict()

        logger.info(
            "[审核agent] 通过 %d 条，重做 %d 条，拒绝 %d 条",
            passed_count,
            rework_count,
            rejected_count,
        )

        result = item_updates(updates)
        result["log"] = [
            f"[审核agent] 通过 {passed_count} 条，重做 {rework_count} 条，拒绝 {rejected_count} 条"
        ]
        return result

    return review_node


# ==================== 终态汇总 ====================


def make_finalize_node():
    """
    构造汇总节点

    工作流真正落库由服务层负责（便于在同一事务中写入审核日志），
    此节点仅统计终态并输出日志。
    """

    def finalize_node(state: dict[str, Any]) -> dict[str, Any]:
        items = state.get("items") or {}
        approved = [v for v in items.values() if v.get("stage") == STAGE_APPROVED]
        rejected = [v for v in items.values() if v.get("stage") == STAGE_REJECTED]

        logger.info(
            "[工作流] 结束: 总计 %d 条，可发布 %d 条，拒绝 %d 条",
            len(items),
            len(approved),
            len(rejected),
        )

        return {
            "log": [
                f"[工作流] 结束: 总计 {len(items)} 条，可发布 {len(approved)} 条，拒绝 {len(rejected)} 条"
            ]
        }

    return finalize_node


def build_run_id() -> str:
    """生成运行标识"""
    return new_run_id()
