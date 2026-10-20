package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.service.AnimeScraperService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 动漫数据抓取控制器
 */
@Slf4j
@RestController
@RequestMapping("/anime/scraper")
@RequiredArgsConstructor
public class AnimeScraperController {
    
    private final AnimeScraperService animeScraperService;
    
    /**
     * 根据MAL ID抓取动漫信息并保存
     * 
     * @param malId MyAnimeList的动漫ID
     * @return 保存结果
     */
    @PostMapping("/fetch/{malId}")
    public Result<Long> fetchAnime(@PathVariable Integer malId) {
        log.info("收到抓取请求: malId={}", malId);
        
        try {
            Long animeId = animeScraperService.fetchAndSaveAnime(malId);
            return Result.success("抓取成功", animeId);
        } catch (Exception e) {
            log.error("抓取失败: malId={}, error={}", malId, e.getMessage(), e);
            return Result.error("抓取失败: " + e.getMessage());
        }
    }
    
    /**
     * 批量抓取多个动漫
     * 
     * @param malIds MAL ID列表，用逗号分隔
     * @return 抓取结果
     */
    @PostMapping("/fetch/batch")
    public Result<String> fetchBatchAnime(@RequestParam String malIds) {
        log.info("收到批量抓取请求: malIds={}", malIds);
        
        try {
            String[] idArray = malIds.split(",");
            StringBuilder result = new StringBuilder();
            int successCount = 0;
            int notFoundCount = 0;  // 404数量
            int failCount = 0;      // 其他失败数量
            
            for (String idStr : idArray) {
                try {
                    Integer malId = Integer.parseInt(idStr.trim());
                    Long animeId = animeScraperService.fetchAndSaveAnime(malId);
                    result.append("✅ MAL ID ").append(malId).append(" -> 动漫ID ").append(animeId).append("\n");
                    successCount++;
                    
                    // 避免频繁请求，休眠1秒
                    Thread.sleep(1000);
                    
                } catch (RuntimeException e) {
                    String errorMsg = e.getMessage();
                    
                    // 判断是否为404错误
                    if (errorMsg != null && errorMsg.contains("动漫不存在")) {
                        result.append("❌ MAL ID ").append(idStr.trim()).append(" -> 不存在 (404)\n");
                        notFoundCount++;
                        log.warn("批量抓取 - 动漫不存在: malId={}", idStr.trim());
                    } else {
                        result.append("⚠️ MAL ID ").append(idStr.trim()).append(" -> 失败: ").append(errorMsg).append("\n");
                        failCount++;
                        log.error("批量抓取 - 其他错误: malId={}, error={}", idStr.trim(), errorMsg);
                    }
                    
                    // 即使失败也继续处理下一个，不休眠
                    
                } catch (Exception e) {
                    result.append("⚠️ MAL ID ").append(idStr.trim()).append(" -> 系统错误: ").append(e.getMessage()).append("\n");
                    failCount++;
                    log.error("批量抓取 - 系统错误: malId={}, error={}", idStr.trim(), e.getMessage(), e);
                }
            }
            
            String summary = String.format("批量抓取完成:\n✅ 成功: %d 个\n❌ 不存在: %d 个\n⚠️ 失败: %d 个\n\n详细结果:\n%s", 
                    successCount, notFoundCount, failCount, result.toString());
            log.info("批量抓取统计 - 成功: {}, 不存在: {}, 失败: {}", successCount, notFoundCount, failCount);
            
            return Result.success(summary, null);
        } catch (Exception e) {
            log.error("批量抓取失败: error={}", e.getMessage(), e);
            return Result.error("批量抓取失败: " + e.getMessage());
        }
    }
}
