package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.service.SeasonalScraperService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 当季新番抓取控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/anime/scraper/seasonal")
@RequiredArgsConstructor
public class SeasonalScraperController {
    
    private final SeasonalScraperService seasonalScraperService;
    
    /**
     * 抓取当年当季新番并保存到anime_schedule表
     * 
     * @return 抓取结果
     */
    @PostMapping("/fetch")
    public Result<Integer> fetchSeasonalAnime() {
        log.info("收到抓取当季新番请求");
        
        try {
            Integer count = seasonalScraperService.fetchAndSaveSeasonalAnime();
            return Result.success("抓取成功，共保存 " + count + " 条记录", count);
        } catch (Exception e) {
            log.error("抓取当季新番失败: {}", e.getMessage(), e);
            return Result.error("抓取失败: " + e.getMessage());
        }
    }
    
    /**
     * 刷新当季新番数据（清空现有数据后重新抓取）
     * 
     * @return 刷新结果
     */
    @PostMapping("/refresh")
    public Result<Integer> refreshSeasonalAnime() {
        log.info("收到刷新当季新番数据请求");
        
        try {
            Integer count = seasonalScraperService.refreshSeasonalAnime();
            return Result.success("刷新成功，共保存 " + count + " 条记录", count);
        } catch (Exception e) {
            log.error("刷新当季新番数据失败: {}", e.getMessage(), e);
            return Result.error("刷新失败: " + e.getMessage());
        }
    }
    
    /**
     * 智能更新当季新番（推荐使用）
     * - 自动判断季度是否变更
     * - 同一季度：更新现有数据
     * - 不同季度：清空旧数据，插入新数据
     * - 定时任务每天凌晨00:00自动执行此逻辑
     * 
     * @return 更新结果
     */
    @PostMapping("/smart-update")
    public Result<Integer> smartUpdateSeasonalAnime() {
        log.info("收到智能更新当季新番请求");
        
        try {
            Integer count = seasonalScraperService.smartUpdateSeasonalAnime();
            return Result.success("智能更新成功，共保存 " + count + " 条记录", count);
        } catch (Exception e) {
            log.error("智能更新当季新番失败: {}", e.getMessage(), e);
            return Result.error("智能更新失败: " + e.getMessage());
        }
    }
}
