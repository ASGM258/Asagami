package com.anime.manager;

import com.anime.manager.config.TestConfig;
import com.anime.manager.service.AnimeScraperService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

/**
 * 动漫爬虫服务测试类
 * 用于测试Jikan API数据抓取功能
 */
@Slf4j
@SpringBootTest(classes = TestConfig.class)
@Import(TestConfig.class)
public class AnimeScraperTest {
    
    @Autowired
    private AnimeScraperService animeScraperService;
    
    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    /**
     * 测试抓取单个动漫
     */
    @Test
    public void testFetchSingleAnime() {
        log.info("========== 开始测试单个动漫抓取 ==========");
        
        try {
            // 测试抓取 Cowboy Bebop (MAL ID: 1)
            Long animeId = animeScraperService.fetchAndSaveAnime(1);
            log.info("✅ 抓取成功，动漫ID: {}", animeId);
        } catch (Exception e) {
            log.error("❌ 抓取失败: {}", e.getMessage(), e);
        }
        
        log.info("========== 测试完成 ==========");
    }
    
    /**
     * 测试批量抓取所有动漫（通过Jikan API分页获取）
     */
    @Test
    public void testFetchAllAnime() {
        log.info("========== 开始测试批量抓取所有动漫 ==========");
        
        // 配置参数
        int startPage = 57;     // 起始页码（从上次中断处继续）
        int endPage = 1224;     // 结束页码（Jikan API当前总页数）
        int perPage = 25;       // 每页数量
        long requestDelay = 1000; // 请求间隔（毫秒），避免API限流
        
        int totalSuccessCount = 0;
        int totalFailCount = 0;
        int totalNotFoundCount = 0;
        int totalAlreadyExistsCount = 0;
        
        try {
            for (int page = startPage; page <= endPage; page++) {
                log.info("\n========== 正在处理第 {}/{} 页 ==========", page, endPage);
                
                // 调用Jikan API获取当前页的动漫列表
                String url = "https://api.jikan.moe/v4/top/anime?page=" + page;
                ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
                
                if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
                    log.error("❌ 第{}页API请求失败: {}", page, response.getStatusCode());
                    continue;
                }
                
                // 解析JSON响应
                JsonNode rootNode = objectMapper.readTree(response.getBody());
                JsonNode dataNode = rootNode.get("data");
                JsonNode paginationNode = rootNode.get("pagination");
                
                if (dataNode == null || !dataNode.isArray()) {
                    log.error("❌ 第{}页数据格式错误", page);
                    continue;
                }
                
                // 获取分页信息
                int currentPage = paginationNode != null && paginationNode.has("current_page") 
                        ? paginationNode.get("current_page").asInt() : page;
                int lastVisiblePage = paginationNode != null && paginationNode.has("last_visible_page") 
                        ? paginationNode.get("last_visible_page").asInt() : endPage;
                int totalItems = paginationNode != null && paginationNode.has("items") 
                        && paginationNode.get("items").has("total") 
                        ? paginationNode.get("items").get("total").asInt() : 0;
                
                log.info("📊 分页信息: 当前页={}/{}, 总数={}, 本页数量={}", 
                        currentPage, lastVisiblePage, totalItems, dataNode.size());
                
                // 遍历当前页的所有动漫
                int pageSuccessCount = 0;
                int pageFailCount = 0;
                int pageNotFoundCount = 0;
                int pageAlreadyExistsCount = 0;
                
                for (int i = 0; i < dataNode.size(); i++) {
                    JsonNode animeNode = dataNode.get(i);
                    Integer malId = animeNode.has("mal_id") ? animeNode.get("mal_id").asInt() : null;
                    String title = animeNode.has("title") ? animeNode.get("title").asText() : "Unknown";
                    
                    if (malId == null) {
                        log.warn("⚠️ [{}/{}] MAL ID为空，跳过", page, i + 1);
                        continue;
                    }
                    
                    log.info("[{}/{}] 正在抓取 MAL ID: {} - {}", page, i + 1, malId, title);
                    
                    try {
                        Long animeId = animeScraperService.fetchAndSaveAnime(malId);
                        log.info("✅ [{}/{}] 成功 - MAL ID: {} -> 动漫ID: {}", 
                                page, i + 1, malId, animeId);
                        pageSuccessCount++;
                        
                    } catch (RuntimeException e) {
                        String errorMsg = e.getMessage();
                        if (errorMsg != null && errorMsg.contains("动漫不存在")) {
                            log.warn("❌ [{}/{}] 不存在 - MAL ID: {} - {}", 
                                    page, i + 1, malId, errorMsg);
                            pageNotFoundCount++;
                        } else if (errorMsg != null && errorMsg.contains("已存在")) {
                            log.info("ℹ️ [{}/{}] 已存在 - MAL ID: {} - {}", 
                                    page, i + 1, malId, title);
                            pageAlreadyExistsCount++;
                        } else {
                            log.error("⚠️ [{}/{}] 失败 - MAL ID: {} - {}", 
                                    page, i + 1, malId, errorMsg);
                            pageFailCount++;
                        }
                        
                    } catch (Exception e) {
                        log.error("⚠️ [{}/{}] 系统错误 - MAL ID: {} - {}", 
                                page, i + 1, malId, e.getMessage(), e);
                        pageFailCount++;
                    }
                    
                    // 请求间隔，避免触发API限流
                    if (i < dataNode.size() - 1 || page < endPage) {
                        try {
                            Thread.sleep(requestDelay);
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            log.error("线程被中断");
                            break;
                        }
                    }
                }
                
                // 更新总计
                totalSuccessCount += pageSuccessCount;
                totalFailCount += pageFailCount;
                totalNotFoundCount += pageNotFoundCount;
                totalAlreadyExistsCount += pageAlreadyExistsCount;
                
                log.info("\n========== 第{}页完成 ==========", page);
                log.info("  ✅ 成功: {} 个", pageSuccessCount);
                log.info("  ℹ️ 已存在: {} 个", pageAlreadyExistsCount);
                log.info("  ❌ 不存在: {} 个", pageNotFoundCount);
                log.info("  ⚠️ 失败: {} 个", pageFailCount);
                log.info("  📊 累计成功: {}, 已存在: {}, 不存在: {}, 失败: {}", 
                        totalSuccessCount, totalAlreadyExistsCount, totalNotFoundCount, totalFailCount);
                
                // 如果到达最后一页，提前退出
                if (currentPage >= lastVisiblePage) {
                    log.info("\n✅ 已到达最后一页({}), 停止抓取", lastVisiblePage);
                    break;
                }
            }
            
        } catch (Exception e) {
            log.error("❌ 批量抓取过程中发生严重错误: {}", e.getMessage(), e);
        }
        
        log.info("\n========== 批量抓取全部完成 ==========");
        log.info("最终统计结果:");
        log.info("  ✅ 新增成功: {} 个", totalSuccessCount);
        log.info("  ℹ️ 已存在跳过: {} 个", totalAlreadyExistsCount);
        log.info("  ❌ 不存在: {} 个", totalNotFoundCount);
        log.info("  ⚠️ 失败: {} 个", totalFailCount);
        log.info("  📊 总计处理: {} 个", 
                totalSuccessCount + totalAlreadyExistsCount + totalNotFoundCount + totalFailCount);
        log.info("====================================");
    }
    
    /**
     * 测试抓取不存在的动漫（404测试）
     */
    @Test
    public void testFetchNonExistentAnime() {
        log.info("========== 测试404异常处理 ==========");
        
        try {
            // 使用一个很大的ID，确保不存在
            animeScraperService.fetchAndSaveAnime(999999999);
            log.error("❌ 应该抛出异常但没有抛出");
        } catch (RuntimeException e) {
            if (e.getMessage().contains("动漫不存在")) {
                log.info("✅ 正确捕获404异常: {}", e.getMessage());
            } else {
                log.error("❌ 捕获了异常但不是预期的404: {}", e.getMessage());
            }
        } catch (Exception e) {
            log.error("❌ 捕获了非RuntimeException: {}", e.getMessage(), e);
        }
        
        log.info("========== 测试完成 ==========");
    }
}
