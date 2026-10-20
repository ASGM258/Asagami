package com.anime.manager.util;

import java.util.regex.Pattern;

/**
 * 文本清洗工具
 *
 * <p>数据源的简介字段常带有富文本标记 —— 例如 AniList 的 {@code description}
 * 即使显式声明 {@code asHtml: false}，仍会返回 {@code <i>}、{@code <br>}
 * 等标签。入库前需清洗为纯文本，避免前端直接渲染出标签。
 */
public final class TextCleaner {

    /** HTML 标签 */
    private static final Pattern HTML_TAG = Pattern.compile("<[^>]+>");

    /** 连续空白（含制表与换行） */
    private static final Pattern WHITESPACE = Pattern.compile("\\s+");

    private TextCleaner() {
    }

    /**
     * 去除 HTML 标签与常见实体，并压缩空白
     *
     * @param text 原始文本
     * @return 清洗后的纯文本；输入为空白时返回 null
     */
    public static String stripHtml(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }
        String cleaned = HTML_TAG.matcher(text).replaceAll(" ");
        cleaned = cleaned
                .replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&quot;", "\"")
                .replace("&#039;", "'")
                .replace("&apos;", "'")
                .replace("&mdash;", "—")
                .replace("&ndash;", "–")
                .replace("&lt;", "<")
                .replace("&gt;", ">");
        cleaned = WHITESPACE.matcher(cleaned).replaceAll(" ").trim();
        return cleaned.isEmpty() ? null : cleaned;
    }

    /**
     * 取第一个非空白字符串
     */
    public static String firstNonBlank(String... candidates) {
        if (candidates == null) {
            return null;
        }
        for (String candidate : candidates) {
            if (candidate != null && !candidate.isBlank()) {
                return candidate;
            }
        }
        return null;
    }
}
