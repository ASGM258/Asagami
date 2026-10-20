"""
资讯正文补全测试

背景：RSS 源只给摘要（MyAnimeList 约 500 字、Anime Corner 约 100 字），
且在词中间被硬截断，因此需要回到详情页抓全文。

覆盖：
1. HTML 正文抽取（站点规则、通用规则、行内标签不被拆行、脚本被丢弃）
2. 需要补全的判定（过短 / 以省略号结尾）
3. 补全流程（只在更完整时替换、未适配站点不发请求、上限与开关生效）
"""

import pytest

from app.config import Settings
from app.news.extractor import (
    extract_article_text,
    host_of,
    html_to_text,
    supports_site,
)
from app.news.fetchers import NewsItem, enrich_items, needs_enrichment


class FakeResponse:
    """requests.Response 的最小替身"""

    def __init__(self, text: str, encoding: str = "utf-8", status: int = 200) -> None:
        self.content = text.encode(encoding)
        self.encoding = encoding
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_settings(**overrides) -> Settings:
    defaults = dict(deepseek_api_key="t", llm_model="fake")
    defaults.update(overrides)
    return Settings(**defaults)


def make_item(content: str, url: str = "https://myanimelist.net/news/1", uid: str = "uid") -> NewsItem:
    return NewsItem(
        source_uid=uid,
        title="Anime News",
        content=content,
        summary=content[:150],
        source_url=url,
    )


# ==================== 1. 正文抽取 ====================


class TestHtmlToText:
    def test_inline_tags_do_not_break_sentences(self):
        """行内标签去掉后不能把句子拆成多行"""
        html = 'Production company <a href="#">Aniplex</a> opened an <i>official</i> website.'
        assert html_to_text(html) == "Production company Aniplex opened an official website."

    def test_block_tags_become_newlines(self):
        html = "<p>第一段</p><p>第二段</p>"
        assert html_to_text(html) == "第一段\n第二段"

    def test_br_becomes_newline(self):
        assert html_to_text("第一行<br />第二行") == "第一行\n第二行"

    def test_drops_script_and_style(self):
        html = "<style>.a{color:red}</style><script>var x=1</script><p>正文</p>"
        assert html_to_text(html) == "正文"

    def test_unescapes_entities(self):
        assert html_to_text("Kokamumo&#039;s NullMeta &amp; more") == "Kokamumo's NullMeta & more"

    def test_empty(self):
        assert html_to_text("") == ""
        assert html_to_text(None) == ""


class TestExtractArticleText:
    MAL_PAGE = """
    <html><body>
      <div class="news-list"><a>Related 1</a><a>Related 2</a></div>
      <div class="content clearfix">
        <div style="text-align:center"><img src="cover.jpg" /></div><br />
        Production company <a href="#">Aniplex</a> opened an official website.
        <p>Animation studio Soigne is producing the anime, set to premiere in 2027.</p>
        <p>Staff<br />Director: Kai Ikarashi</p>
      </div>
      <div class="sidebar">More news</div>
    </body></html>
    """

    def test_extracts_mal_container(self):
        text = extract_article_text(self.MAL_PAGE, "https://myanimelist.net/news/74833036")

        assert "Production company Aniplex opened an official website." in text.replace("\n", " ")
        assert "Kai Ikarashi" in text
        # 侧栏/相关阅读不能被当成正文
        assert "Related 1" not in text
        assert "More news" not in text

    def test_falls_back_to_generic_article_tag(self):
        page = "<article><h1>标题</h1><p>正文段落一二三</p></article>"
        text = extract_article_text(page, "https://example.com/post/1")
        assert "正文段落一二三" in text

    def test_picks_longest_candidate(self):
        page = (
            '<div class="entry-content"><p>' + "很长的正文" * 30 + "</p></div>"
            "<article><p>短正文</p></article>"
        )
        text = extract_article_text(page, "https://animecorner.me/x/")
        assert "短正文" not in text
        assert len(text) > 100

    def test_handles_nested_divs(self):
        page = (
            '<div class="entry-content">'
            '<div><div>嵌套正文</div></div>'
            "<p>后续段落</p>"
            "</div>"
            "<p>容器外的内容</p>"
        )
        text = extract_article_text(page, "https://animecorner.me/x/")
        assert "嵌套正文" in text
        assert "后续段落" in text
        assert "容器外的内容" not in text

    def test_returns_empty_when_no_container(self):
        assert extract_article_text("<html><body>纯文本无容器</body></html>", "https://x.test/") == ""
        assert extract_article_text("", "https://x.test/") == ""


class TestSiteSupport:
    def test_known_hosts(self):
        assert supports_site("https://myanimelist.net/news/1")
        assert supports_site("https://animecorner.me/some-post/")

    def test_unknown_host(self):
        assert not supports_site("https://example.com/a")
        assert not supports_site("")

    def test_host_of(self):
        assert host_of("https://myanimelist.net/news/1?_location=rss") == "myanimelist.net"
        assert host_of("") == ""


# ==================== 2. 是否需要补全 ====================


class TestNeedsEnrichment:
    def test_short_content_needs_enrichment(self):
        settings = make_settings(news_enrich_min_chars=600)
        assert needs_enrichment(make_item("很短的摘要"), settings)

    def test_ellipsis_ending_needs_enrichment(self):
        settings = make_settings(news_enrich_min_chars=100)
        content = "正文" * 100 + "..."
        assert needs_enrichment(make_item(content), settings)

    def test_complete_long_content_needs_no_enrichment(self):
        settings = make_settings(news_enrich_min_chars=600)
        assert not needs_enrichment(make_item("完整正文。" * 200), settings)


# ==================== 3. 补全流程 ====================


class TestEnrichItems:
    def _patch_requests(self, monkeypatch, html: str, calls: list | None = None):
        import app.news.fetchers as F

        def fake_get(url, **kwargs):
            if calls is not None:
                calls.append(url)
            return FakeResponse(html)

        monkeypatch.setattr(F.requests, "get", fake_get)

    def test_replaces_truncated_content_with_full_article(self, monkeypatch):
        calls: list[str] = []
        self._patch_requests(monkeypatch, TestExtractArticleText.MAL_PAGE, calls)

        item = make_item("Production company Aniplex opened an official website...")
        settings = make_settings(news_enrich_min_chars=600)

        items = enrich_items([item], settings)

        assert len(calls) == 1
        assert len(items[0].content) > 100
        assert "Kai Ikarashi" in items[0].content
        assert not items[0].content.endswith("...")

    def test_keeps_original_when_extraction_not_longer(self, monkeypatch):
        self._patch_requests(monkeypatch, "<html><body>tiny</body></html>")

        original = "原始摘要内容..."
        item = make_item(original)
        settings = make_settings(news_enrich_min_chars=600)

        items = enrich_items([item], settings)
        assert items[0].content == original

    def test_no_request_for_unsupported_host(self, monkeypatch):
        calls: list[str] = []
        self._patch_requests(monkeypatch, "<article>正文</article>", calls)

        item = make_item("短摘要", url="https://unknown-site.test/post/1")
        enrich_items([item], make_settings())

        assert calls == [], "未适配的站点不应发补全请求"

    def test_no_request_when_disabled(self, monkeypatch):
        calls: list[str] = []
        self._patch_requests(monkeypatch, TestExtractArticleText.MAL_PAGE, calls)

        item = make_item("短摘要")
        enrich_items([item], make_settings(news_enrich_enabled=False))

        assert calls == []

    def test_respects_limit(self, monkeypatch):
        calls: list[str] = []
        self._patch_requests(monkeypatch, TestExtractArticleText.MAL_PAGE, calls)

        items = [make_item("短摘要", uid=f"u{i}") for i in range(5)]
        settings = make_settings(news_enrich_limit=2, news_enrich_delay=0)

        enrich_items(items, settings)
        assert len(calls) == 2

    def test_no_request_when_content_complete(self, monkeypatch):
        calls: list[str] = []
        self._patch_requests(monkeypatch, TestExtractArticleText.MAL_PAGE, calls)

        item = make_item("完整正文。" * 200)
        enrich_items([item], make_settings(news_enrich_min_chars=600))

        assert calls == []
        assert item.content.startswith("完整正文。")

    def test_empty_list_is_noop(self):
        assert enrich_items([], make_settings()) == []


# ==================== 4. 配置与翻译上限 ====================


class TestEnrichConfig:
    def test_defaults_enabled(self):
        settings = make_settings()

        assert settings.news_enrich_enabled is True
        assert settings.news_enrich_min_chars >= 300
        assert settings.news_enrich_limit > 0
        assert settings.news_enrich_timeout > 0

    def test_translation_output_budget(self):
        """翻译整篇正文需要足够的输出上限，1000 tokens 会把译文截断"""
        settings = make_settings()
        assert settings.news_llm_max_tokens >= 2000
        assert settings.news_translate_input_limit >= 8000

    def test_llm_accepts_max_tokens_override(self):
        from app.news.llm import create_llm

        llm = create_llm(make_settings(), temperature=0.1, max_tokens=4096)
        assert llm.max_tokens == 4096
