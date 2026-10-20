package com.anime.manager;

import com.anime.manager.config.TestConfig;
import com.anime.manager.service.CharacterScraperService;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * 角色爬虫测试类
 *
 * <p>数据源已从 Jikan(MAL) 迁移到 AniList。注意：**AniList 的角色ID与 MAL
 * 角色ID不是同一套编号**，因此这里的 ID 换成了 AniList 的角色ID。
 */
@Slf4j
@SpringBootTest(classes = TestConfig.class)
public class CharacterScraperTest {

    @Autowired
    private CharacterScraperService characterScraperService;

    /** 若干知名角色的 AniList ID */
    private static final Integer[] ANILIST_CHARACTER_IDS = {
            127691,  // 五条悟 Satoru Gojou（咒术回战）
            45627,   // 利威尔 Levi（进击的巨人）
            417,     // 鲁路修 Lelouch Lamperouge（叛逆的鲁路修）
    };

    /**
     * 测试抓取角色列表（限制页数，避免时间过长）
     */
    @Test
    public void testFetchAllCharacters() {
        log.info("========== 开始测试：抓取角色 ==========");

        try {
            // 限制抓取前 2 页（每页 50 个角色），避免测试时间过长
            Integer maxPages = 2;
            log.info("准备抓取最多 {} 页角色数据...", maxPages);

            Integer successCount = characterScraperService.fetchAndSaveAllCharacters(maxPages);

            log.info("测试完成！成功入库 {} 个角色", successCount);

        } catch (Exception e) {
            log.error("测试失败: {}", e.getMessage(), e);
            throw e;
        }
    }

    /**
     * 测试抓取单个角色
     */
    @Test
    public void testFetchSingleCharacter() {
        log.info("========== 开始测试：抓取单个角色 ==========");

        try {
            Integer anilistId = ANILIST_CHARACTER_IDS[0];
            log.info("准备抓取角色: anilistId={}", anilistId);

            Long characterId = characterScraperService.fetchAndSaveCharacter(anilistId);

            log.info("测试完成！角色ID: {}", characterId);

        } catch (Exception e) {
            log.error("测试失败: {}", e.getMessage(), e);
            throw e;
        }
    }

    /**
     * 测试批量抓取指定角色
     */
    @Test
    public void testFetchMultipleCharacters() {
        log.info("========== 开始测试：批量抓取指定角色 ==========");

        int successCount = 0;
        int failCount = 0;

        for (Integer anilistId : ANILIST_CHARACTER_IDS) {
            try {
                log.info("正在抓取角色: anilistId={}", anilistId);
                Long characterId = characterScraperService.fetchAndSaveCharacter(anilistId);
                log.info("成功保存角色: anilistId={}, id={}", anilistId, characterId);
                successCount++;

                // 礼貌间隔（AniList 限流为 90 请求/分钟）
                Thread.sleep(1000);

            } catch (Exception e) {
                log.error("抓取角色失败: anilistId={}, error={}", anilistId, e.getMessage());
                failCount++;
            }
        }

        log.info("测试完成！成功: {}, 失败: {}", successCount, failCount);
    }
}
