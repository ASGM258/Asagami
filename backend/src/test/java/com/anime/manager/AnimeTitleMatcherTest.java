package com.anime.manager;

import com.anime.manager.util.AnimeTitleMatcher;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 标题归一化匹配单元测试
 *
 * <p>纯函数测试，不依赖 Spring 容器、数据库或网络。
 *
 * <p>背景：数据源（AniList）返回的是续作标题，而 anime 表存基础标题。
 * 实测 50 条当季新番里精确匹配只能命中 1 条，加入归一化与前缀匹配后提升到 6 条，
 * 其余为 anime 表中确实不存在的新作。
 */
class AnimeTitleMatcherTest {

    @Test
    @DisplayName("剥离《第N期》形式的续作后缀")
    void stripsChineseSeasonSuffix() {
        assertEquals("薬屋のひとりごと", AnimeTitleMatcher.stripSequelSuffix("薬屋のひとりごと 第3期"));
        assertEquals("転生したら剣でした", AnimeTitleMatcher.stripSequelSuffix("転生したら剣でした 第2期"));
        assertEquals("作品名", AnimeTitleMatcher.stripSequelSuffix("作品名 第 12 季"));
        assertEquals("作品名", AnimeTitleMatcher.stripSequelSuffix("作品名（第2期）"));    }

    @Test
    @DisplayName("剥离 Season N / 2nd Season 形式的后缀")
    void stripsEnglishSeasonSuffix() {
        assertEquals("アオのハコ", AnimeTitleMatcher.stripSequelSuffix("アオのハコ Season２"));
        assertEquals("Attack on Titan", AnimeTitleMatcher.stripSequelSuffix("Attack on Titan 2nd Season"));
        assertEquals("Show", AnimeTitleMatcher.stripSequelSuffix("Show 3rd Season"));
    }

    @Test
    @DisplayName("不剥离标题末尾的裸数字，避免把作品名本身改坏")
    void keepsTrailingNumberInTitle() {
        // 数字可能是作品名的一部分（如 エッジランナーズ2），一律剥离会造成误配
        assertEquals("サイバーパンク: エッジランナーズ2",
                AnimeTitleMatcher.stripSequelSuffix("サイバーパンク: エッジランナーズ2"));
    }

    @Test
    @DisplayName("无后缀的标题保持不变")
    void keepsPlainTitle() {
        assertEquals("魔法使いの夜", AnimeTitleMatcher.stripSequelSuffix("魔法使いの夜"));
        assertEquals("メイドインアビス 目覚める神秘",
                AnimeTitleMatcher.stripSequelSuffix("メイドインアビス 目覚める神秘"));
    }

    @Test
    @DisplayName("候选词包含剥离后缀后的主标题")
    void buildsCandidateFromSuffix() {
        List<String> candidates = AnimeTitleMatcher.buildCandidates("薬屋のひとりごと 第3期");
        assertTrue(candidates.contains("薬屋のひとりごと"), "应包含剥离后缀的候选: " + candidates);
    }

    @Test
    @DisplayName("候选词包含按分隔符截取的主标题")
    void buildsCandidateFromSeparator() {
        assertTrue(AnimeTitleMatcher.buildCandidates("サイバーパンク: エッジランナーズ2")
                .contains("サイバーパンク"));

        assertTrue(AnimeTitleMatcher.buildCandidates("作品：副标题")
                .contains("作品"));
    }

    @Test
    @DisplayName("不把原标题本身作为候选（调用方已先做精确匹配）")
    void excludesOriginalTitle() {
        assertFalse(AnimeTitleMatcher.buildCandidates("魔法使いの夜").contains("魔法使いの夜"));
    }

    @Test
    @DisplayName("过滤过短候选，避免误配")
    void filtersTooShortCandidates() {
        // "作品" 只有 2 个字符，低于阈值
        assertFalse(AnimeTitleMatcher.buildCandidates("作品：副标题").contains("作品"));
        assertEquals(List.of(), AnimeTitleMatcher.buildCandidates("短：标题"));
    }

    @Test
    @DisplayName("候选词去重且保序")
    void candidatesAreDeduplicatedAndOrdered() {
        List<String> candidates = AnimeTitleMatcher.buildCandidates("同じタイトル：同じタイトル 第2期");

        long distinct = candidates.stream().distinct().count();
        assertEquals(candidates.size(), distinct, "候选词不应重复: " + candidates);
    }

    @Test
    @DisplayName("空值与空白输入安全返回")
    void handlesNullAndBlank() {
        assertEquals(List.of(), AnimeTitleMatcher.buildCandidates(null));
        assertEquals(List.of(), AnimeTitleMatcher.buildCandidates(""));
        assertEquals(List.of(), AnimeTitleMatcher.buildCandidates("   "));
        assertNull(AnimeTitleMatcher.stripSequelSuffix(null));
    }

    @Test
    @DisplayName("真实数据回归：AniList 当季标题的典型形态")
    void realWorldSamples() {
        // 注意：AniList 标题里用的是全角空格（U+3000），正则必须兼容
        assertEquals("ジョジョの奇妙な冒険", AnimeTitleMatcher.stripSequelSuffix(
                "ジョジョの奇妙な冒険\u3000スティール・ボール・ラン"));
        assertEquals("薬屋のひとりごと", AnimeTitleMatcher.stripSequelSuffix(
                "薬屋のひとりごと\u3000第3期"));
        assertTrue(AnimeTitleMatcher.buildCandidates("テムパル～アイテムの力～")
                .contains("テムパル"));
        // 无标准后缀时不应臆造候选，避免把续作误配到第一季
        assertTrue(AnimeTitleMatcher.buildCandidates("東京リベンジャーズ 三天戦争編")
                .isEmpty(), "无标准后缀时不应臆造候选");
    }

    @Test
    @DisplayName("全角空格（U+3000）也要能被识别为分隔")
    void handlesFullWidthSpace() {
        assertEquals("作品名", AnimeTitleMatcher.stripSequelSuffix("作品名\u3000第2期"));
        assertEquals("作品名", AnimeTitleMatcher.stripSequelSuffix("作品名　第 2 季"));
    }
}
