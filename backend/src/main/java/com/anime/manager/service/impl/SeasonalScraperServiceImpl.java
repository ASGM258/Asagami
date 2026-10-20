package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.dto.SeasonalAnimeItem;
import com.anime.manager.dto.SeasonalAnimePage;
import com.anime.manager.entity.AnimeSchedule;
import com.anime.manager.mapper.AnimeMapper;
import com.anime.manager.mapper.AnimeScheduleMapper;
import com.anime.manager.service.AnimeScraperService;
import com.anime.manager.service.CacheService;
import com.anime.manager.service.SeasonalAnimeSource;
import com.anime.manager.service.SeasonalScraperService;
import com.anime.manager.util.AnimeTitleMatcher;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 当季新番抓取服务实现类
 *
 * <p>数据来源已从 Jikan API 切换为可插拔的 {@link SeasonalAnimeSource}，
 * 当前默认实现为 AniList（见 {@code AniListSeasonalAnimeSource}）。
 * 本类只负责编排：分页遍历 → 归一化 → 去重 → 入库 → 异步补齐 anime 记录。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SeasonalScraperServiceImpl implements SeasonalScraperService {

    private final AnimeMapper animeMapper;
    private final AnimeScheduleMapper animeScheduleMapper;
    private final AnimeScraperService animeScraperService;
    private final CacheService cacheService;
    private final SeasonalAnimeSource seasonalAnimeSource;

    /** 分页之间的间隔，避免给数据源造成压力 */
    private static final long PAGE_INTERVAL_MS = 1000L;

    /**
     * 安全阀：最大抓取页数。
     * 正常由数据源的 hasNextPage 收敛；此上限仅用于防止分页异常导致死循环。
     */
    private static final int MAX_PAGES = 120;

    /**
     * 抓取当年当季新番并保存到 anime_schedule 表
     */
    @Override
    public Integer fetchAndSaveSeasonalAnime() {
        log.info("开始抓取当年当季新番, 数据源: {}", seasonalAnimeSource.sourceName());

        try {
            List<SeasonalAnimeItem> allItems = fetchAllSeasonalItems();
            log.info("数据源共返回 {} 条当季新番", allItems.size());

            if (allItems.isEmpty()) {
                log.warn("数据源未返回任何当季新番，本次不做任何写入");
                return 0;
            }

            // 归一化为排期实体，同时收集需要补抓 anime 记录的 MAL ID
            List<AnimeSchedule> allScheduleList = new ArrayList<>(allItems.size());
            List<Integer> pendingMalIds = new ArrayList<>();
            int totalFailCount = 0;

            for (SeasonalAnimeItem item : allItems) {
                try {
                    AnimeSchedule schedule = toSchedule(item);

                    // 匹配 anime 表；匹配不到时把 MAL ID 入队，供后续异步补抓
                    Long mainId = findMainIdByJapaneseTitle(item.title(), item.malId(), pendingMalIds);
                    schedule.setMainId(mainId);

                    allScheduleList.add(schedule);
                } catch (Exception e) {
                    log.error("转换当季新番失败: title={}, error={}", item.title(), e.getMessage(), e);
                    totalFailCount++;
                }
            }

            // 应用层去重：以 title + dayOfWeek 为唯一键，与数据库唯一索引 uk_schedule_title_week 对齐
            Map<String, AnimeSchedule> uniqueMap = new LinkedHashMap<>();
            int duplicateInSourceCount = 0;
            for (AnimeSchedule item : allScheduleList) {
                String key = item.getTitle() + "-" + (item.getDayOfWeek() != null ? item.getDayOfWeek() : "null");
                if (uniqueMap.putIfAbsent(key, item) != null) {
                    duplicateInSourceCount++;
                }
            }

            List<AnimeSchedule> insertList = new ArrayList<>(uniqueMap.values());
            log.info("去重结果: 数据源{}条, 内部重复{}条, 待插入{}条",
                    allScheduleList.size(), duplicateInSourceCount, insertList.size());

            int totalSuccessCount = 0;
            int totalSkipCount = 0;

            if (!insertList.isEmpty()) {
                try {
                    animeScheduleMapper.batchInsert(insertList);
                    log.info("批量插入成功: {} 条记录", insertList.size());
                    totalSuccessCount = insertList.size();
                    clearScheduleCache();
                } catch (Exception e) {
                    // 捕获唯一约束冲突（数据库中已存在同一 title + dayOfWeek 的记录）
                    String errorMsg = e.getMessage();
                    if (errorMsg != null && (errorMsg.contains("Duplicate entry")
                            || errorMsg.contains("唯一约束")
                            || errorMsg.contains("UNIQUE constraint"))) {
                        log.warn("检测到与数据库已有记录重复，已跳过: {}", errorMsg);
                        totalSkipCount = insertList.size();
                    } else {
                        throw e;
                    }
                }
            } else {
                log.info("所有记录均为重复，无需插入");
                totalSkipCount = allScheduleList.size();
            }

            log.info("========== 当季新番抓取完成 ==========");
            log.info("总计: 成功={}, 跳过={}, 失败={}", totalSuccessCount, totalSkipCount, totalFailCount);
            log.info("=====================================");

            // 异步补齐 anime 表中缺失的当季新番，避免阻塞主流程
            if (!pendingMalIds.isEmpty()) {
                log.info("发现 {} 部动漫需要补充抓取", pendingMalIds.size());
                processPendingAnimeAsync(pendingMalIds);
            }

            return totalSuccessCount;

        } catch (Exception e) {
            log.error("抓取当季新番失败: {}", e.getMessage(), e);
            throw new RuntimeException("抓取当季新番失败: " + e.getMessage(), e);
        }
    }

    /**
     * 清空现有排期数据并重新抓取
     */
    @Override
    public Integer refreshSeasonalAnime() {
        log.info("开始刷新当季新番数据...");

        animeScheduleMapper.clearAll();
        log.info("已清空现有排期数据");

        return fetchAndSaveSeasonalAnime();
    }

    /**
     * 智能更新当季新番数据（定时任务使用）
     * 通过「现有数据与当季标题的匹配度」判断是否已进入新季度。
     */
    @Override
    public Integer smartUpdateSeasonalAnime() {
        log.info("========== 开始智能更新当季新番数据 ==========");

        try {
            List<AnimeSchedule> existingSchedules = animeScheduleMapper.findAll();

            if (existingSchedules == null || existingSchedules.isEmpty()) {
                log.info("数据库中没有现有数据，直接抓取当季新番");
                return fetchAndSaveSeasonalAnime();
            }

            // 收集当季全部标题用于匹配度检查
            Set<String> currentSeasonTitles = new HashSet<>();
            for (SeasonalAnimeItem item : fetchAllSeasonalItems()) {
                currentSeasonTitles.add(item.title());
            }

            log.info("当前季度共有 {} 部动漫", currentSeasonTitles.size());

            int matchCount = 0;
            for (AnimeSchedule schedule : existingSchedules) {
                if (currentSeasonTitles.contains(schedule.getTitle())) {
                    matchCount++;
                }
            }

            double matchRate = existingSchedules.isEmpty()
                    ? 0 : (double) matchCount / existingSchedules.size();
            log.info("匹配度检查: {}/{} 条记录匹配当前季度 ({:.1f}%)",
                    matchCount, existingSchedules.size(), matchRate * 100);

            if (matchRate < 0.5) {
                log.info("匹配度过低，判断为进入新季度，清空旧数据后重新抓取");
            } else {
                log.info("匹配度较高，判断为同一季度，刷新现有数据");
            }
            animeScheduleMapper.clearAll();

            Integer count = fetchAndSaveSeasonalAnime();

            log.info("========== 智能更新完成，共保存 {} 条记录 ==========", count);
            return count;

        } catch (Exception e) {
            log.error("智能更新当季新番失败: {}", e.getMessage(), e);
            throw new RuntimeException("智能更新失败: " + e.getMessage(), e);
        }
    }

    /**
     * 分页遍历数据源，取回当季全部新番
     *
     * @return 全部条目（顺序与数据源一致）
     */
    private List<SeasonalAnimeItem> fetchAllSeasonalItems() {
        List<SeasonalAnimeItem> all = new ArrayList<>();

        int currentPage = 1;
        boolean hasNext = true;

        while (hasNext && currentPage <= MAX_PAGES) {
            SeasonalAnimePage pageResult = seasonalAnimeSource.fetchPage(currentPage);
            all.addAll(pageResult.items());

            log.info("已处理第 {}/{} 页, 累计 {} 条",
                    pageResult.currentPage(), pageResult.lastPage(), all.size());

            hasNext = pageResult.hasNextPage();
            currentPage++;

            if (hasNext) {
                try {
                    Thread.sleep(PAGE_INTERVAL_MS);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    log.warn("分页抓取被中断，返回已获取的 {} 条", all.size());
                    break;
                }
            }
        }

        if (currentPage > MAX_PAGES && hasNext) {
            log.warn("已达到最大页数限制 {}，提前结束抓取", MAX_PAGES);
        }

        return all;
    }

    /**
     * 归一化条目 → 排期实体
     */
    private AnimeSchedule toSchedule(SeasonalAnimeItem item) {
        return AnimeSchedule.builder()
                .title(item.title())
                .coverImage(item.coverImage())
                .rating(item.rating() != null ? item.rating() : BigDecimal.ZERO)
                .episodes(item.episodes() != null ? item.episodes() : 0)
                .status(item.status() != null ? item.status() : 0)
                .dayOfWeek(item.dayOfWeek())
                .updateTime(item.updateTime())
                .build();
    }

    /**
     * 通过标题在 anime 表中查找对应主键
     *
     * <p>匹配分三轮，避免把续作错配到第一季：
     * <ol>
     *   <li>title_jp / title 精确匹配</li>
     *   <li>剥离续作后缀（第N期、Season N、第N季…）后再精确匹配</li>
     *   <li>双向前缀匹配（要求 anime 中的标题是候选词的前缀）</li>
     * </ol>
     *
     * <p>未命中时把 MAL ID 加入待抓取队列，供后续异步补齐 anime 记录。
     */
    private Long findMainIdByJapaneseTitle(String title, Integer malId, List<Integer> pendingMalIds) {
        if (title == null || title.isEmpty()) {
            return null;
        }

        // 第一轮：精确匹配
        var anime = animeMapper.findByTitleJp(title);
        if (anime != null) {
            log.debug("精确匹配到anime记录: titleJp={}, id={}", title, anime.getId());
            return anime.getId();
        }
        anime = animeMapper.findByTitle(title);
        if (anime != null) {
            log.debug("精确匹配到anime记录: title={}, id={}", title, anime.getId());
            return anime.getId();
        }

        // 第二、三轮：基于归一化候选词做精确与前缀匹配
        for (String candidate : AnimeTitleMatcher.buildCandidates(title)) {
            anime = animeMapper.findByTitleJp(candidate);
            if (anime == null) {
                anime = animeMapper.findByTitle(candidate);
            }
            if (anime == null) {
                anime = animeMapper.findPrefixByTitleJp(candidate);
            }
            if (anime == null) {
                anime = animeMapper.findPrefixByTitle(candidate);
            }

            if (anime != null) {
                log.info("归一化匹配成功: 原题={}, 候选={}, animeId={}, animeTitle={}",
                        title, candidate, anime.getId(), anime.getTitle());
                return anime.getId();
            }
        }

        // 仍未命中：交由异步补抓（依赖 AnimeScraperService，若其数据源不可用则该步会失败）
        if (malId != null) {
            log.info("未找到匹配的anime记录，加入待抓取队列: title={}, malId={}", title, malId);
            pendingMalIds.add(malId);
        } else {
            log.warn("未找到匹配的anime记录且无MAL ID: {}", title);
        }

        return null;
    }

    /**
     * 异步补齐 anime 表中缺失的当季新番
     *
     * <p>注意：这一步调用的是 {@link AnimeScraperService}，其数据源独立于本类的
     * 当季新番数据源。若该服务的数据源不可用，此处会记录失败日志，但不影响
     * anime_schedule 已入库的数据展示（main_id 保持为空）。
     */
    private void processPendingAnimeAsync(List<Integer> pendingMalIds) {
        new Thread(() -> {
            log.info("========== 开始异步补充抓取动漫 ==========");
            int successCount = 0;
            int failCount = 0;
            int retryCount = 0;
            final int MAX_RETRIES = 3;

            for (int i = 0; i < pendingMalIds.size(); i++) {
                Integer malId = pendingMalIds.get(i);
                boolean success = false;

                for (int attempt = 1; attempt <= MAX_RETRIES; attempt++) {
                    try {
                        if (attempt == 1) {
                            log.info("[{}/{}] 正在抓取: malId={}", i + 1, pendingMalIds.size(), malId);
                        } else {
                            log.info("[{}/{}] 第{}次重试: malId={}", i + 1, pendingMalIds.size(), attempt, malId);
                            retryCount++;
                        }

                        Long animeId = animeScraperService.fetchAndSaveAnime(malId);
                        if (animeId != null) {
                            successCount++;
                            log.info("[{}/{}] 抓取成功: malId={}, animeId={}", i + 1, pendingMalIds.size(), malId, animeId);
                            success = true;
                            break;
                        } else {
                            log.warn("[{}/{}] 抓取返回null: malId={}", i + 1, pendingMalIds.size(), malId);
                            break;
                        }

                    } catch (Exception e) {
                        String errorMsg = e.getMessage();

                        if (errorMsg != null && errorMsg.contains("404")) {
                            log.warn("[{}/{}] 动漫不存在 (404): malId={}", i + 1, pendingMalIds.size(), malId);
                            break;
                        }

                        if (errorMsg != null && errorMsg.contains("429")) {
                            log.warn("[{}/{}] 检测到429限流，等待60秒后重试...", i + 1, pendingMalIds.size());
                            try {
                                Thread.sleep(60000);
                            } catch (InterruptedException ie) {
                                Thread.currentThread().interrupt();
                                log.error("异步抓取被中断");
                                failCount += (MAX_RETRIES - attempt + 1);
                                return;
                            }
                        } else if (attempt < MAX_RETRIES) {
                            long waitTime = 2000L * attempt;
                            log.warn("[{}/{}] 抓取失败 (第{}/{}次): malId={}, error={}",
                                    i + 1, pendingMalIds.size(), attempt, MAX_RETRIES, malId, errorMsg);
                            log.info("等待{}ms后重试...", waitTime);
                            try {
                                Thread.sleep(waitTime);
                            } catch (InterruptedException ie) {
                                Thread.currentThread().interrupt();
                                log.error("异步抓取被中断");
                                failCount += (MAX_RETRIES - attempt + 1);
                                return;
                            }
                        } else {
                            log.error("[{}/{}] 达到最大重试次数({})，抓取失败: malId={}, error={}",
                                    i + 1, pendingMalIds.size(), MAX_RETRIES, malId, errorMsg);
                        }
                    }
                }

                if (!success) {
                    failCount++;
                }

                if (success && i < pendingMalIds.size() - 1) {
                    try {
                        Thread.sleep(400);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        log.error("异步抓取被中断");
                        break;
                    }
                }
            }

            log.info("========== 异步补充抓取完成 ==========");
            log.info("总计: 成功={}, 失败={}, 重试次数={}", successCount, failCount, retryCount);
            log.info("=====================================");
        }, "anime-scraper-async").start();
    }

    /**
     * 清除排期相关缓存
     */
    private void clearScheduleCache() {
        cacheService.deleteByPattern(CacheKeyConstants.bannerPattern());
        cacheService.deleteByPattern(CacheKeyConstants.animePagePattern());
        log.info("已清除排期相关缓存");
    }
}
