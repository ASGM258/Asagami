"""
正文提取：把文章详情页 HTML 还原为纯文本

为什么需要这一步：RSS 源普遍只给摘要，且在词中间硬截断 ——
  - MyAnimeList news RSS：约 500 字，结尾是 "episode d..." 这种残句
  - Anime Corner feed：约 100 字
要拿到完整正文必须回到详情页抓取，本模块只负责「HTML → 纯文本」的抽取，
不含任何网络请求，因此可以脱离网络做单元测试。

站点差异用「容器规则表」表达：
  - 命中站点规则时优先用站点的正文容器
  - 同时尝试通用规则（<article>、WordPress 的 entry-content 等）兜底
  - 多个候选容器取**文本最长**的那个，避免抓到侧边栏/相关阅读
"""

import html as html_lib
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 正文容器规则：(host 正则, 容器开标签正则)
# 顺序即优先级；新增抓取源时在这里补一条即可
SITE_RULES: tuple[tuple[str, str], ...] = (
    # MyAnimeList 资讯详情页
    (r"(^|\.)myanimelist\.net$", r'<div\s+[^>]*class="[^"]*\bcontent clearfix\b[^"]*"'),
    # Anime Corner（WordPress）
    (r"(^|\.)animecorner\.me$", r'<div\s+[^>]*class="[^"]*\bentry-content\b[^"]*"'),
)

# 通用容器规则（站点未命中时使用）
GENERIC_RULES: tuple[str, ...] = (
    r"<article\b",
    r'<div\s+[^>]*class="[^"]*\bentry-content\b[^"]*"',
    r'<div\s+[^>]*class="[^"]*\bpost-content\b[^"]*"',
    r'<div\s+[^>]*class="[^"]*\barticle[-_]?(?:body|content|text)\b[^"]*"',
    r'<div\s+[^>]*id="[^"]*\barticle[-_]?(?:body|content)\b[^"]*"',
    r"<main\b",
)

# 行内标签：去掉但**不**产生换行，否则 "Production company\nAniplex\nopened" 会被拆碎
_INLINE_TAGS = (
    "a|abbr|b|bdi|bdo|cite|code|data|dfn|em|font|i|kbd|mark|q|s|samp|"
    "small|span|strong|sub|sup|time|tt|u|var|wbr"
)
# 整块丢弃的标签（内容或脚本，不属于正文）
_DROP_TAGS = "script|style|noscript|iframe|svg|form|button|nav|footer|aside"


def host_of(url: str) -> str:
    """取 URL 的主机名（小写，去掉端口）"""
    try:
        return (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return ""


def _slice_element(doc: str, start: int, tag: str) -> str:
    """
    从 start 处的开标签开始，按标签配对取出完整元素片段

    Args:
        doc: 完整 HTML
        start: 开标签起始下标
        tag: 标签名（div / article / main ...）

    Returns:
        元素片段；未闭合时返回到文档末尾
    """
    pattern = re.compile(rf"<{tag}\b|</{tag}\s*>", re.I)
    depth = 0
    for match in pattern.finditer(doc, start):
        token = match.group(0)
        if token[1:2] == "/":  # </tag>
            depth -= 1
            if depth <= 0:
                return doc[start : match.end()]
        else:  # <tag
            depth += 1
    return doc[start:]


def html_to_text(fragment: str) -> str:
    """
    HTML 片段转纯文本

    规则：
    - 丢掉 script/style/nav/aside 等非正文标签
    - `<br>` 与块级标签转成换行，行内标签直接去掉（避免把句子拆成多行）
    - 解码 HTML 实体，压缩行内空白，去掉空行
    """
    if not fragment:
        return ""

    text = re.sub(rf"(?is)<(?:{_DROP_TAGS})\b.*?</(?:{_DROP_TAGS})\s*>", " ", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(rf"(?is)</?(?:{_INLINE_TAGS})\b[^>]*>", "", text)
    text = re.sub(r"(?s)<[^>]+>", "\n", text)
    text = html_lib.unescape(text)

    lines = [
        re.sub(r"[ \t\u00a0\u3000]+", " ", line).strip()
        for line in text.split("\n")
    ]
    return "\n".join(line for line in lines if line)


def _tag_of(open_tag: str, default: str = "div") -> str:
    """从开标签文本里取出标签名"""
    match = re.match(r"<\s*([a-zA-Z0-9]+)", open_tag or "")
    return match.group(1).lower() if match else default


def supports_site(url: str) -> bool:
    """该站点是否有专门的正文容器规则（无规则的站点不发补全请求）"""
    host = host_of(url)
    if not host:
        return False
    return any(re.search(host_pattern, host) for host_pattern, _ in SITE_RULES)


def container_patterns(url: str) -> tuple[str, ...]:
    """
    给出该 URL 使用的候选容器规则

    站点规则在前、通用规则在后，最终按抽取出的文本长度择优。
    """
    host = host_of(url)
    patterns: list[str] = []
    for host_pattern, container_pattern in SITE_RULES:
        if host and re.search(host_pattern, host):
            patterns.append(container_pattern)
    patterns.extend(GENERIC_RULES)
    return tuple(patterns)


def extract_article_text(html: str, url: str = "") -> str:
    """
    从详情页 HTML 里抽出正文纯文本

    Args:
        html: 页面 HTML
        url: 页面地址（用于选择站点规则）

    Returns:
        正文文本；无法识别时返回空串（调用方据此保留原有内容）
    """
    if not html:
        return ""

    best = ""
    for pattern in container_patterns(url):
        try:
            matches = list(re.finditer(pattern, html, re.I))
        except re.error:  # 规则写错不应影响抓取
            logger.warning("正文容器规则无效，已跳过: %s", pattern)
            continue

        # 同一页面同种容器可能多处出现，取前几个里最长的
        for match in matches[:3]:
            tag = _tag_of(match.group(0), "div")
            fragment = _slice_element(html, match.start(), tag)
            text = html_to_text(fragment)
            if len(text) > len(best):
                best = text

    return best
