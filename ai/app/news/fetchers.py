"""
资讯抓取源适配

设计目标：把不同来源的原始条目归一化为统一的 NewsItem 结构。

- AniNewsAPI（主源，JSON）：字段名可通过配置映射，兼容多种常见结构
- RSS（备用源）：解析 RSS/Atom，在 AniNewsAPI 不可用时自动降级

每个来源只需实现 `NewsFetcher.fetch()`，工作流不感知来源差异。
"""

import hashlib
import html
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

from app.config import Settings
from app.news.extractor import extract_article_text, host_of, supports_site

logger = logging.getLogger(__name__)

# 请求头：部分站点会拒绝默认 UA
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AnimeNewsBot/1.0)",
    "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*",
}

# HTML 标签清洗
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class NewsItem:
    """归一化后的资讯条目（工作流内流转的数据单元）"""

    source_uid: str
    title: str
    summary: str = ""
    content: str = ""
    cover_image: str = ""
    category: str = ""
    source: str = ""
    author: str = ""
    publish_time: str = ""
    tags: list[str] = field(default_factory=list)
    source_url: str = ""
    language: str = "en"
    #: 正文是否已回源补全（False 表示仍是 RSS 摘要，需要修复）
    content_enriched: bool = False

    # 工作流状态：fetched -> translated -> summarized -> approved / rejected
    stage: str = "fetched"
    attempts: int = 0
    review_reason: str = ""
    review_feedback: str = ""
    # 每次审核的真实判定序列：[{attempt, passed, reason}]，用于审核轨迹留痕
    review_history: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转为普通字典（便于放入 LangGraph 状态）"""
        return {
            "source_uid": self.source_uid,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "cover_image": self.cover_image,
            "category": self.category,
            "source": self.source,
            "author": self.author,
            "publish_time": self.publish_time,
            "tags": list(self.tags),
            "source_url": self.source_url,
            "language": self.language,
            "content_enriched": self.content_enriched,
            "stage": self.stage,
            "attempts": self.attempts,
            "review_reason": self.review_reason,
            "review_feedback": self.review_feedback,
            "review_history": list(self.review_history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NewsItem":
        """从字典还原"""
        return cls(
            source_uid=data.get("source_uid", ""),
            title=data.get("title", ""),
            summary=data.get("summary", "") or "",
            content=data.get("content", "") or "",
            cover_image=data.get("cover_image", "") or "",
            category=data.get("category", "") or "",
            source=data.get("source", "") or "",
            author=data.get("author", "") or "",
            publish_time=data.get("publish_time", "") or "",
            tags=list(data.get("tags") or []),
            source_url=data.get("source_url", "") or "",
            language=data.get("language", "en"),
            content_enriched=bool(data.get("content_enriched")),
            stage=data.get("stage", "fetched"),
            attempts=int(data.get("attempts") or 0),
            review_reason=data.get("review_reason", "") or "",
            review_feedback=data.get("review_feedback", "") or "",
            review_history=list(data.get("review_history") or []),
        )


# ==================== 文本清洗工具 ====================


def strip_html(text: str | None) -> str:
    """去除 HTML 标签并解码实体"""
    if not text:
        return ""
    cleaned = _TAG_RE.sub(" ", str(text))
    cleaned = html.unescape(cleaned)
    return _WS_RE.sub(" ", cleaned).strip()


def normalize_publish_time(value: Any) -> str:
    """
    归一化发布时间为 'YYYY-MM-DD HH:MM:SS'

    支持 datetime、时间戳、ISO 字符串与 RFC822（RSS 常见）等格式。
    """
    if not value:
        return ""

    # 已是 datetime
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    # 时间戳（秒或毫秒）
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return ""

    text = str(value).strip()
    if not text:
        return ""

    # ISO 8601
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        pass

    # RFC822 等常见格式
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    return ""


def build_source_uid(guid: str | None, title: str, publish_time: str, url: str = "") -> str:
    """
    构造来源唯一标识（用于入库去重）

    优先使用来源提供的 guid/link，缺失时退化为
    标题 + 发布时间的 md5，保证同一篇资讯不会重复入库。
    """
    if guid:
        return str(guid).strip()[:255]

    basis = f"{url}|{title}|{publish_time}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()


# ==================== 抓取源抽象 ====================


class NewsFetcher(ABC):
    """抓取源抽象基类"""

    name: str = "base"

    @abstractmethod
    def fetch(self, limit: int = 20) -> list[NewsItem]:
        """
        抓取资讯列表

        Args:
            limit: 最多返回条数

        Returns:
            归一化后的资讯条目列表（失败返回空列表）
        """
        raise NotImplementedError


# ==================== AniNewsAPI ====================


class AniNewsAPIFetcher(NewsFetcher):
    """
    AniNewsAPI 抓取源

    AniNewsAPI 返回的 JSON 结构可能随版本变化，因此：
    - 使用 `_pick_list` 兼容「顶层数组 / data 数组 / items|news|results 嵌套」等结构
    - 使用字段映射表兼容不同字段名（如 link/url、image/thumbnail/cover）
    """

    name = "AniNewsAPI"

    # 列表可能的键名
    LIST_KEYS = ("data", "items", "news", "results", "articles")
    # 字段映射：目标字段 -> 候选来源字段
    FIELD_ALIASES = {
        "title": ("title", "headline", "name"),
        "summary": ("summary", "description", "excerpt", "snippet"),
        "content": ("content", "body", "article", "full_text", "text"),
        "cover_image": ("image", "imageUrl", "image_url", "thumbnail", "cover", "coverImage"),
        "category": ("category", "genre", "tag", "type"),
        "author": ("author", "creator", "byline", "provider"),
        "publish_time": ("publishedAt", "published_at", "pubDate", "date", "published", "time"),
        "source_url": ("link", "url", "source_url", "sourceUrl", "permalink"),
        "guid": ("id", "guid", "uuid", "slug"),
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        """调用 AniNewsAPI 抓取并归一化"""
        base = self._settings.aninews_base_url.rstrip("/")
        endpoint = self._settings.aninews_endpoint.lstrip("/")
        url = f"{base}/{endpoint}" if base and endpoint else base

        if not url:
            logger.warning("未配置 AniNewsAPI 地址，跳过抓取")
            return []

        try:
            response = requests.get(
                url,
                params={"limit": limit},
                headers=DEFAULT_HEADERS,
                timeout=self._settings.news_fetch_timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning("AniNewsAPI 请求失败: %s", exc)
            return []
        except ValueError as exc:
            logger.warning("AniNewsAPI 返回内容不是合法 JSON: %s", exc)
            return []

        entries = self._extract_list(payload)
        if not entries:
            logger.warning("AniNewsAPI 返回结构无法识别出列表，原始键: %s",
                           list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
            return []

        items: list[NewsItem] = []
        for entry in entries[:limit]:
            if not isinstance(entry, dict):
                continue
            item = self._normalize(entry)
            if item and item.title:
                items.append(item)

        logger.info("AniNewsAPI 抓取到 %d 条资讯", len(items))
        return items

    def _extract_list(self, payload: Any) -> list[Any]:
        """从可能的多种结构中提取条目列表"""
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        for key in self.LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            # 再嵌一层，如 {"data": {"items": [...]}}
            if isinstance(value, dict):
                for nested in self.LIST_KEYS:
                    if isinstance(value.get(nested), list):
                        return value[nested]

        return []

    def _pick(self, entry: dict, target: str) -> Any:
        """按候选字段名从原始条目中取值"""
        for alias in self.FIELD_ALIASES.get(target, ()):  # 顺序即优先级
            if entry.get(alias) not in (None, "", []):
                return entry[alias]
        return None

    def _normalize(self, entry: dict) -> NewsItem | None:
        """把原始条目映射为 NewsItem"""
        title = strip_html(self._pick(entry, "title"))
        if not title:
            return None

        content = strip_html(self._pick(entry, "content"))
        summary = strip_html(self._pick(entry, "summary"))
        # 没有摘要时用正文前 150 字兜底
        if not summary and content:
            summary = content[:150]

        publish_time = normalize_publish_time(self._pick(entry, "publish_time"))
        source_url = str(self._pick(entry, "source_url") or "")

        # 标签：可能是数组或逗号分隔字符串
        raw_tags = entry.get("tags") or entry.get("tag") or []
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [strip_html(t) for t in raw_tags if t]
        else:
            tags = []

        # 分类：可能是对象或数组
        category_raw = self._pick(entry, "category")
        if isinstance(category_raw, list) and category_raw:
            category_raw = category_raw[0]
        if isinstance(category_raw, dict):
            category_raw = category_raw.get("name") or category_raw.get("title")
        category = strip_html(category_raw) if category_raw else ""

        return NewsItem(
            source_uid=build_source_uid(
                str(self._pick(entry, "guid") or ""), title, publish_time, source_url
            ),
            title=title,
            summary=summary,
            content=content,
            cover_image=str(self._pick(entry, "cover_image") or ""),
            category=category,
            source=self.name,
            author=strip_html(self._pick(entry, "author")) or self.name,
            publish_time=publish_time,
            tags=tags,
            source_url=source_url,
            language="en",
        )


# ==================== RSS 备用源 ====================


class RSSFetcher(NewsFetcher):
    """
    RSS/Atom 备用抓取源

    支持**多个** feed：单个新闻源的条目数量有限（MyAnimeList 的 news RSS 通常
    只返回最近约 10 条），只配一个源会导致抓完就没有新内容。因此这里接受
    逗号分隔的多个地址，聚合后按 source_uid 去重。

    在 AniNewsAPI 不可用时（网络受限或服务不可达）自动降级使用。
    """

    name = "RSS"

    def __init__(self, settings: Settings, feed_urls: list[str] | None = None) -> None:
        self._settings = settings
        if feed_urls is None:
            # 支持逗号分隔的多源配置
            raw = settings.news_fallback_rss or ""
            feed_urls = [u.strip() for u in raw.split(",") if u.strip()]
        self._feed_urls = feed_urls

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        """
        依次解析各个 RSS 源并聚合去重

        注意：必须把**所有源都取完再按 limit 截断**。若在拿到 limit 条后就 break，
        第一个源就会把额度占满（例如 MyAnimeList 一次返回 10 条），
        后面的源永远不会被请求，多源配置形同虚设。
        """
        if not self._feed_urls:
            logger.warning("未配置备用 RSS 源，跳过抓取")
            return []

        merged: dict[str, NewsItem] = {}
        for feed_url in self._feed_urls:
            # 每个源内部多取一些，聚合后再统一截断
            for item in self._fetch_one(feed_url, limit):
                merged.setdefault(item.source_uid, item)

        items = list(merged.values())[:limit]
        logger.info(
            "RSS 多源聚合抓取到 %d 条资讯（源数 %d，去重前 %d 条）",
            len(items), len(self._feed_urls), len(merged),
        )
        return items

    def _fetch_one(self, feed_url: str, limit: int) -> list[NewsItem]:
        """解析单个 RSS 源"""
        try:
            response = requests.get(
                feed_url,
                headers=DEFAULT_HEADERS,
                timeout=self._settings.news_fetch_timeout,
            )
            response.raise_for_status()
            # feedparser 可直接解析响应内容，避免二次编码问题
            parsed = feedparser.parse(response.content)
        except requests.RequestException as exc:
            logger.warning("RSS 抓取失败: url=%s, error=%s", feed_url, exc)
            return []

        if getattr(parsed, "bozo", 0) and not parsed.entries:
            logger.warning(
                "RSS 解析异常且无条目: url=%s, error=%s",
                feed_url, getattr(parsed, "bozo_exception", ""),
            )
            return []

        source_name = strip_html(parsed.feed.get("title")) or self.name
        items: list[NewsItem] = []

        for entry in parsed.entries[:limit]:
            title = strip_html(entry.get("title"))
            if not title:
                continue

            # 正文优先取 content，其次 summary/description
            raw_content = ""
            if entry.get("content"):
                raw_content = entry["content"][0].get("value", "")
            raw_content = raw_content or entry.get("summary") or entry.get("description") or ""
            content = strip_html(raw_content)

            summary = strip_html(entry.get("summary") or entry.get("description"))
            if not summary and content:
                summary = content[:150]

            publish_time = normalize_publish_time(
                entry.get("published") or entry.get("updated") or entry.get("created")
            )
            source_url = entry.get("link") or ""

            # 封面图：RSS 常见 media_content / media_thumbnail / enclosures
            cover = ""
            for key in ("media_content", "media_thumbnail"):
                media = entry.get(key)
                if isinstance(media, list) and media and isinstance(media[0], dict):
                    cover = media[0].get("url", "")
                    if cover:
                        break
            if not cover:
                for link in entry.get("links", []) or []:
                    if isinstance(link, dict) and str(link.get("type", "")).startswith("image"):
                        cover = link.get("href", "")
                        break

            tags = [strip_html(t.get("term")) for t in entry.get("tags", []) or [] if t.get("term")]

            items.append(
                NewsItem(
                    source_uid=build_source_uid(
                        entry.get("id") or entry.get("guid"), title, publish_time, source_url
                    ),
                    title=title,
                    summary=summary,
                    content=content,
                    cover_image=cover,
                    category=strip_html(entry.get("category")) if entry.get("category") else "",
                    source=source_name,
                    author=strip_html(entry.get("author")) or source_name,
                    publish_time=publish_time,
                    tags=tags,
                    source_url=source_url,
                    language="en",
                )
            )

        logger.info("RSS(%s) 抓取到 %d 条资讯: %s", source_name, len(items), feed_url)
        return items


# ==================== 组合抓取：主源失败自动降级 ====================


class FallbackNewsFetcher(NewsFetcher):
    """主源 + 备用源的组合抓取器（主源无结果时降级到备用源）"""

    name = "Auto"

    def __init__(self, fetchers: list[NewsFetcher]) -> None:
        self._fetchers = fetchers

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        for fetcher in self._fetchers:
            items = fetcher.fetch(limit)
            if items:
                return items
            logger.info("抓取源 %s 无结果，尝试下一个来源", fetcher.name)
        return []


def build_default_fetcher(settings: Settings) -> NewsFetcher:
    """
    构造默认抓取器

    顺序：AniNewsAPI -> 备用 RSS。任一源成功即返回，
    全部失败时返回空列表（工作流会记录并正常结束）。
    """
    fetchers: list[NewsFetcher] = []
    if settings.aninews_enabled:
        fetchers.append(AniNewsAPIFetcher(settings))
    if settings.news_fallback_rss:
        fetchers.append(RSSFetcher(settings))
    return FallbackNewsFetcher(fetchers)


# ==================== 正文补全 ====================

#: HTML 里声明的字符集
_CHARSET_RE = re.compile(rb'charset=["\']?\s*([\w-]+)', re.I)

#: 抽取结果的最小可替换长度（低于此值视为抓到了无关片段）
_MIN_REPLACEMENT_CHARS = 100
#: 抽取结果相对原文的最小增量（字符）
_MIN_REPLACEMENT_GAIN = 80


def _is_http_url(url: str) -> bool:
    """只接受 http(s) 地址"""
    return bool(url) and url.lower().startswith(("http://", "https://"))


def _decode_response(response: requests.Response) -> str:
    """
    按正确编码解码响应

    requests 在响应头没有 charset 时会猜成 ISO-8859-1，直接把 UTF-8 页面
    解成乱码。这里优先用响应头声明的编码，其次看 HTML meta，最后退回 utf-8。
    """
    encoding = (response.encoding or "").lower()
    if not encoding or encoding == "iso-8859-1":
        match = _CHARSET_RE.search(response.content[:2048] or b"")
        encoding = match.group(1).decode("ascii", "ignore").lower() if match else "utf-8"
    try:
        return response.content.decode(encoding or "utf-8", errors="replace")
    except (LookupError, UnicodeDecodeError):
        return response.content.decode("utf-8", errors="replace")


def fetch_article_text(url: str, settings: Settings) -> str:
    """
    抓取详情页并抽取正文

    Args:
        url: 文章地址
        settings: 配置（超时等）

    Returns:
        正文纯文本；失败返回空串
    """
    if not _is_http_url(url):
        return ""

    # 只对已配置规则的站点发请求，避免对未适配站点做无意义的抓取
    if not supports_site(url):
        logger.debug("站点未适配正文抽取，跳过补全: host=%s", host_of(url))
        return ""

    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=settings.news_enrich_timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("正文补全请求失败: url=%s, error=%s", url, exc)
        return ""

    return extract_article_text(_decode_response(response), url)


def needs_enrichment(item: NewsItem, settings: Settings) -> bool:
    """
    判断条目正文是否残缺

    两个判据：
    1. 正文短于 `news_enrich_min_chars`（RSS 摘要普遍只有几百字）
    2. 正文以省略号结尾（RSS 硬截断的典型特征）
    """
    content = (item.content or "").strip()
    if len(content) < int(settings.news_enrich_min_chars):
        return True
    return content.endswith(("...", "…"))


def enrich_items(items: list[NewsItem], settings: Settings) -> list[NewsItem]:
    """
    用详情页全文补全摘要式的条目正文

    RSS 源只给摘要，正文在词中间被截断；要发布完整资讯必须回到详情页抓取。
    逐条处理并受 `news_enrich_limit` 限制，单条失败不影响其他条目。

    Args:
        items: 待补全条目（通常已是筛掉旧内容后的新条目）
        settings: 配置

    Returns:
        原地修改后的条目列表（保持顺序）
    """
    if not items or not settings.news_enrich_enabled:
        return items

    # 限流按**请求次数**计（而非成功次数）：抽不到正文时同样消耗配额，
    # 否则一个改版的站点会让每轮都把全部条目请求一遍。
    budget = max(int(settings.news_enrich_limit), 0)
    attempts = 0
    enriched = 0
    added_chars = 0

    for item in items:
        if attempts >= budget:
            logger.info("[正文补全] 已达请求上限 %d 条，剩余条目保留原摘要", budget)
            break
        if not needs_enrichment(item, settings):
            continue

        original = item.content or ""
        attempts += 1
        text = fetch_article_text(item.source_url, settings)

        # 请求间隔放在每次请求之后，避免被站点限流
        if settings.news_enrich_delay > 0:
            time.sleep(settings.news_enrich_delay)

        if not text:
            continue

        # 只有明显更完整时才替换，避免用页脚/侧边栏文本覆盖原文：
        #   1) 至少达到最小可读长度，防止抓到一句无关文字就覆盖
        #   2) 至少长出一个可观幅度，防止篇幅持平却被覆盖
        if len(text) < _MIN_REPLACEMENT_CHARS:
            logger.debug(
                "[正文补全] 抽取结果过短(%d 字)，保留原文: uid=%s",
                len(text),
                item.source_uid,
            )
            continue

        min_gain = max(_MIN_REPLACEMENT_GAIN, int(len(original) * 0.2))
        if len(text) - len(original) < min_gain:
            logger.debug(
                "[正文补全] 抽取结果不更完整，保留原文: uid=%s 原文=%d 抽取=%d",
                item.source_uid,
                len(original),
                len(text),
            )
            continue

        item.content = text
        item.content_enriched = True
        enriched += 1
        added_chars += len(text) - len(original)
        logger.info(
            "[正文补全] uid=%s %d -> %d 字（%s）",
            item.source_uid,
            len(original),
            len(text),
            host_of(item.source_url),
        )

    if enriched:
        logger.info(
            "[正文补全] 请求 %d 次，补全 %d 条，新增 %d 字正文",
            attempts,
            enriched,
            added_chars,
        )
    else:
        logger.info("[正文补全] 请求 %d 次，无需补全（或均失败）", attempts)

    return items
