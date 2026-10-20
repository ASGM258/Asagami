package com.anime.manager.scheduler;

import com.anime.manager.service.SeasonalScraperService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 当季新番爬虫定时任务调度器
 * 
 * 执行策略：
 * - 每天凌晨 00:00 执行一次
 * - 智能判断季度变更，自动清理上一季度数据并插入新季度数据
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class SeasonalScraperScheduler {
    
    private final SeasonalScraperService seasonalScraperService;
    
    /**
     * 定时任务：每天凌晨 00:00 执行当季新番爬取
     * 
     * Cron表达式说明：
     * - second: 0 (第0秒)
     * - minute: 0 (第0分钟)
     * - hour: 0 (第0小时，即凌晨12点)
     * - day of month: * (每天)
     * - month: * (每月)
     * - day of week: ? (不指定星期几)
     */
    @Scheduled(cron = "0 0 0 * * ?")
    public void scheduleSeasonalAnimeFetch() {
        log.info("========================================");
        log.info("【定时任务】开始执行当季新番爬取任务");
        log.info("执行时间: {}", java.time.LocalDateTime.now());
        log.info("========================================");
        
        try {
            // 调用智能更新方法，自动处理季度变更
            Integer count = seasonalScraperService.smartUpdateSeasonalAnime();
            
            log.info("========================================");
            log.info("【定时任务】当季新番爬取任务执行成功");
            log.info("共保存 {} 条记录", count);
            log.info("下次执行时间: 明天凌晨 00:00");
            log.info("========================================");
            
        } catch (Exception e) {
            log.error("========================================");
            log.error("【定时任务】当季新番爬取任务执行失败");
            log.error("错误信息: {}", e.getMessage(), e);
            log.error("========================================");
            // 不抛出异常，避免影响其他定时任务
        }
    }
}
