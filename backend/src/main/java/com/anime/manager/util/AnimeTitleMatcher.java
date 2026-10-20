package com.anime.manager.util;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/**
 * 动漫标题匹配辅助工具
 *
 * <p>数据源（如 AniList）返回的常是续作标题：《作品 第3期》《作品 Season 2》
 * 《作品：副标题》。而 anime 表中保存的多为基础标题，直接精确匹配会全部落空，
 * 导致每条新番都被误判为"需要补抓"。
 *
 * <p>本工具负责把续作标题归一化为一组可用于匹配的候选词：
 * <ol>
 *   <li>剥离季数/续作后缀（第N期、第N季、Season N、2nd Season…）</li>
 *   <li>按标题分隔符截取主标题（副标题/篇章名之后的部分不参与匹配）</li>
 * </ol>
 *
 * <p>纯函数、无外部依赖，便于单测。
 */
public final class AnimeTitleMatcher {

    /**
     * 续作/季数后缀
     *
     * <p>两个容易踩的坑：
     * <ul>
     *   <li>标题可能使用全角空格（U+3000），默认模式下 {@code \s} 不匹配它</li>
     *   <li>季数可能是全角数字（如 {@code Season２}），{@code \d} 不匹配全角数字，
     *       故用 {@code [0-9０-９]} 显式覆盖</li>
     * </ul>
     */
    private static final List<Pattern> SEQUEL_SUFFIX_PATTERNS = List.of(
            Pattern.compile("[ \\u3000]+第[ \\u3000]*[0-9０-９]+[ \\u3000]*[期季部章][ \\u3000]*$"),
            Pattern.compile("[ \\u3000]+Season[ \\u3000]*[0-9０-９]+[ \\u3000]*$",
                    Pattern.CASE_INSENSITIVE),
            Pattern.compile("[ \\u3000]+[0-9０-９]+(?:st|nd|rd|th)[ \\u3000]+Season[ \\u3000]*$",
                    Pattern.CASE_INSENSITIVE),
            Pattern.compile("[ \\u3000]*[（(][ \\u3000]*第[ \\u3000]*[0-9０-９]+[ \\u3000]*[期季][ \\u3000]*[)）][ \\u3000]*$")
    );

    /**
     * 标题分隔符：其后的副标题不参与匹配
     *
     * <p>包含全角空格（U+3000）——《ジョジョの奇妙な冒険　スティール・ボール・ラン》
     * 这类标题用全角空格分隔主标题与篇章名。
     */
    private static final String[] TITLE_SEPARATORS = {"：", ":", " - ", "—", "～", "\u3000"};

    /** 候选词最短长度，避免过短关键词造成误配 */
    private static final int MIN_CANDIDATE_LENGTH = 3;

    private AnimeTitleMatcher() {
    }

    /**
     * 剥离续作/季数后缀
     *
     * @param title 原始标题
     * @return 去掉后缀的标题；原样返回无法匹配时的输入
     */
    public static String stripSequelSuffix(String title) {
        if (title == null) {
            return null;
        }
        String result = title.trim();
        for (Pattern pattern : SEQUEL_SUFFIX_PATTERNS) {
            result = pattern.matcher(result).replaceAll("").trim();
        }
        return result;
    }

    /**
     * 生成用于匹配 anime 表的候选标题
     *
     * <p>不包含原标题本身（原标题由调用方先行精确匹配），
     * 结果已去重、保序，并过滤掉过短的候选。
     *
     * @param title 原始标题
     * @return 候选标题列表，可能为空
     */
    public static List<String> buildCandidates(String title) {
        List<String> candidates = new ArrayList<>();
        if (title == null || title.isBlank()) {
            return candidates;
        }

        String original = title.trim();
        String base = stripSequelSuffix(original);
        addCandidate(candidates, base, original);

        for (String separator : TITLE_SEPARATORS) {
            int index = base.indexOf(separator);
            if (index > 0) {
                addCandidate(candidates, base.substring(0, index).trim(), original);
            }
        }

        return candidates;
    }

    private static void addCandidate(List<String> candidates, String candidate, String original) {
        if (candidate == null || candidate.length() < MIN_CANDIDATE_LENGTH
                || candidate.equals(original) || candidates.contains(candidate)) {
            return;
        }
        candidates.add(candidate);
    }
}
