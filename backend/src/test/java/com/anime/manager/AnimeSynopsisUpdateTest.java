package com.anime.manager;

import com.anime.manager.config.TestConfig;
import com.anime.manager.entity.Anime;
import com.anime.manager.mapper.AnimeMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

/**
 * 动漫简介更新测试类
 * 用于批量更新数据库中现有动漫的简介(synopsis)字段
 */
@Slf4j
@SpringBootTest(classes = TestConfig.class)
@Import(TestConfig.class)
public class AnimeSynopsisUpdateTest {
    
    @Autowired
    private AnimeMapper animeMapper;
    
    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    // Jikan API v4 基础URL
    private static final String JIKAN_API_BASE_URL = "https://api.jikan.moe/v4";
    
    /**
     * 批量更新指定ID范围内的动漫简介
     * 从数据库读取动漫列表，通过Jikan API搜索找到对应的MAL ID，然后获取最新简介并更新
     */
    @Test
    public void testUpdateSynopsisBatch() {
        log.info("========== 开始批量更新动漫简介 ==========");
        
        // 配置参数
        int startId = 21;   // 起始ID（根据截图数据）
        int endId = 124;    // 结束ID（根据截图数据）
        long requestDelay = 1000; // 请求间隔（毫秒），避免API限流
        
        int totalSuccessCount = 0;
        int totalFailCount = 0;
        int totalSkipCount = 0;
        int totalNotFoundCount = 0;
        
        try {
            for (int id = startId; id <= endId; id++) {
                log.info("\n========== 正在处理 ID: {}/{} ==========", id, endId);
                
                // 从数据库查询动漫
                Anime anime = animeMapper.findById((long) id);
                
                if (anime == null) {
                    log.warn("⚠️ [{}] 数据库中不存在该动漫，跳过", id);
                    totalSkipCount++;
                    continue;
                }
                
                // 不跳过已有简介，全部重新更新（因为现有简介可能有问题）
                log.info("[{}] 准备更新简介 - 标题: {}, 日文标题: {}", id, anime.getTitle(), anime.getTitleJp());
                log.info("  当前简介状态: {}", 
                    anime.getSynopsis() != null && !anime.getSynopsis().isEmpty() ? 
                        "已有简介(长度=" + anime.getSynopsis().length() + ")" : "无简介");
                
                try {
                    // 通过标题搜索找到MAL ID，然后获取并更新简介
                    boolean updated = searchAndUpdateSynopsis(anime);
                    
                    if (updated) {
                        totalSuccessCount++;
                        log.info("✅ [{}] 更新成功", id);
                    } else {
                        totalSkipCount++;
                        log.info("ℹ️ [{}] 无需更新或未找到匹配", id);
                    }
                    
                } catch (RuntimeException e) {
                    String errorMsg = e.getMessage();
                    if (errorMsg != null && errorMsg.contains("未找到匹配的动漫")) {
                        log.warn("❌ [{}] 在MAL中未找到匹配的动漫 - {}", id, errorMsg);
                        totalNotFoundCount++;
                    } else {
                        log.error("️ [{}] 更新失败 - {}", id, errorMsg);
                        totalFailCount++;
                    }
                    
                } catch (Exception e) {
                    log.error("⚠️ [{}] 系统错误 - {}", id, e.getMessage(), e);
                    totalFailCount++;
                }
                
                // 请求间隔，避免触发API限流
                if (id < endId) {
                    try {
                        Thread.sleep(requestDelay);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        log.error("线程被中断");
                        break;
                    }
                }
            }
            
        } catch (Exception e) {
            log.error("❌ 批量更新过程中发生严重错误: {}", e.getMessage(), e);
        }
        
        log.info("\n========== 批量更新全部完成 ==========");
        log.info("最终统计结果:");
        log.info("  ✅ 更新成功: {} 个", totalSuccessCount);
        log.info("  ℹ️ 跳过(无需更新): {} 个", totalSkipCount);
        log.info("  ❌ 未找到匹配: {} 个", totalNotFoundCount);
        log.info("  ⚠️ 失败: {} 个", totalFailCount);
        log.info("   总计处理: {} 个", 
                totalSuccessCount + totalSkipCount + totalNotFoundCount + totalFailCount);
        log.info("====================================");
    }
    
    /**
     * 通过标题搜索找到MAL ID，然后获取简介并更新到数据库
     * 
     * @param anime 动漫实体
     * @return 是否更新了简介
     */
    private boolean searchAndUpdateSynopsis(Anime anime) {
        log.info("正在搜索匹配的MAL ID: title={}, titleJp={}", anime.getTitle(), anime.getTitleJp());
        
        try {
            // 优先使用日文标题搜索，其次使用中文/英文标题
            String searchQuery = (anime.getTitleJp() != null && !anime.getTitleJp().isEmpty()) 
                    ? anime.getTitleJp() : anime.getTitle();
            
            if (searchQuery == null || searchQuery.isEmpty()) {
                log.warn("标题为空，无法搜索: id={}", anime.getId());
                return false;
            }
            
            // 调用Jikan API搜索动漫
            String url = JIKAN_API_BASE_URL + "/anime?q=" + java.net.URLEncoder.encode(searchQuery, "UTF-8") + "&limit=5";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            
            if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
                throw new RuntimeException("API请求失败: " + response.getStatusCode());
            }
            
            // 解析JSON响应
            JsonNode rootNode = objectMapper.readTree(response.getBody());
            JsonNode dataNode = rootNode.get("data");
            
            if (dataNode == null || !dataNode.isArray() || dataNode.size() == 0) {
                log.warn("未找到任何匹配的动漫: query={}", searchQuery);
                throw new RuntimeException("未找到匹配的动漫");
            }
            
            // 遍历搜索结果，找到最匹配的
            Integer matchedMalId = null;
            String matchedTitle = null;
            
            for (JsonNode resultNode : dataNode) {
                Integer malId = resultNode.has("mal_id") ? resultNode.get("mal_id").asInt() : null;
                String resultTitle = resultNode.has("title") ? resultNode.get("title").asText() : null;
                String resultTitleJp = resultNode.has("title_japanese") ? resultNode.get("title_japanese").asText() : null;
                
                // 精确匹配日文标题
                if (anime.getTitleJp() != null && resultTitleJp != null && 
                    anime.getTitleJp().equals(resultTitleJp)) {
                    matchedMalId = malId;
                    matchedTitle = resultTitle;
                    log.info("✅ 精确匹配日文标题: MAL ID={}, title={}", malId, resultTitle);
                    break;
                }
                
                // 匹配中文/英文标题
                if (matchedMalId == null && resultTitle != null && 
                    resultTitle.equalsIgnoreCase(anime.getTitle())) {
                    matchedMalId = malId;
                    matchedTitle = resultTitle;
                    log.info("✅ 匹配标题: MAL ID={}, title={}", malId, resultTitle);
                }
            }
            
            if (matchedMalId == null) {
                log.warn("未找到精确匹配的动漫: query={}, 搜索结果数={}", searchQuery, dataNode.size());
                // 如果没找到精确匹配，使用第一个结果
                JsonNode firstResult = dataNode.get(0);
                matchedMalId = firstResult.has("mal_id") ? firstResult.get("mal_id").asInt() : null;
                matchedTitle = firstResult.has("title") ? firstResult.get("title").asText() : null;
                log.info("⚠️ 使用第一个搜索结果: MAL ID={}, title={}", matchedMalId, matchedTitle);
            }
            
            if (matchedMalId == null) {
                throw new RuntimeException("无法获取MAL ID");
            }
            
            // 通过MAL ID获取详细信息
            return fetchSynopsisByMalId(anime, matchedMalId);
            
        } catch (HttpClientErrorException e) {
            log.error("HTTP客户端错误 ({}): id={}, message={}", 
                    e.getStatusCode(), anime.getId(), e.getMessage());
            throw new RuntimeException("API请求失败 (" + e.getStatusCode() + ")", e);
            
        } catch (Exception e) {
            log.error("系统错误: id={}, error={}", anime.getId(), e.getMessage(), e);
            throw new RuntimeException("搜索并更新简介失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 通过MAL ID获取简介并更新到数据库
     * 
     * @param anime 动漫实体
     * @param malId MyAnimeList的动漫ID
     * @return 是否更新了简介
     */
    private boolean fetchSynopsisByMalId(Anime anime, Integer malId) {
        log.info("通过MAL ID获取简介: malId={}", malId);
        
        try {
            // 构建API URL
            String url = JIKAN_API_BASE_URL + "/anime/" + malId;
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                // 解析JSON响应
                JsonNode rootNode = objectMapper.readTree(response.getBody());
                JsonNode dataNode = rootNode.get("data");
                
                if (dataNode == null) {
                    throw new RuntimeException("API返回数据为空");
                }
                
                // 提取简介
                String synopsis = null;
                if (dataNode.has("synopsis") && !dataNode.get("synopsis").isNull()) {
                    synopsis = dataNode.get("synopsis").asText();
                }
                
                // 如果获取到简介且不为空，则更新数据库
                if (synopsis != null && !synopsis.isEmpty()) {
                    anime.setSynopsis(synopsis);
                    int updateCount = animeMapper.update(anime);
                    
                    if (updateCount > 0) {
                        log.info("简介更新成功: id={}, malId={}, 简介长度={}", 
                                anime.getId(), malId, synopsis.length());
                        return true;
                    } else {
                        log.warn("数据库更新失败: id={}", anime.getId());
                        return false;
                    }
                } else {
                    log.info("API返回的简介为空: id={}, malId={}", anime.getId(), malId);
                    return false;
                }
                
            } else {
                throw new RuntimeException("API请求失败: " + response.getStatusCode());
            }
            
        } catch (HttpClientErrorException.NotFound e) {
            // 404 - 动漫不存在
            log.warn("动漫在MAL中不存在 (404): malId={}", malId);
            throw new RuntimeException("动漫不存在于MyAnimeList", e);
            
        } catch (HttpClientErrorException e) {
            // 其他客户端错误 (4xx)
            log.error("HTTP客户端错误 ({}): malId={}, message={}", 
                    e.getStatusCode(), malId, e.getMessage());
            throw new RuntimeException("API请求失败 (" + e.getStatusCode() + ")", e);
            
        } catch (Exception e) {
            // 其他系统错误
            log.error("系统错误: malId={}, error={}", malId, e.getMessage(), e);
            throw new RuntimeException("获取简介失败: " + e.getMessage(), e);
        }
    }
    
    /**
     * 测试更新单个动漫简介（用于调试）
     */
    @Test
    public void testUpdateSingleSynopsis() {
        log.info("========== 测试更新单个动漫简介 ==========");
        
        // 选择一个需要更新的动漫ID进行测试
        Long testId = 21L;
        
        try {
            Anime anime = animeMapper.findById(testId);
            
            if (anime == null) {
                log.error("❌ 数据库中不存在该动漫: id={}", testId);
                return;
            }
            
            log.info("当前动漫信息:");
            log.info("  ID: {}", anime.getId());
            log.info("  标题: {}", anime.getTitle());
            log.info("  日文标题: {}", anime.getTitleJp());
            log.info("  当前简介: {}", anime.getSynopsis() != null ? 
                    (anime.getSynopsis().length() > 50 ? 
                            anime.getSynopsis().substring(0, 50) + "..." : 
                            anime.getSynopsis()) : "(空)");
            
            // 执行更新
            boolean updated = searchAndUpdateSynopsis(anime);
            
            if (updated) {
                log.info("✅ 更新成功!");
                // 重新查询验证
                Anime updatedAnime = animeMapper.findById(testId);
                log.info("更新后简介: {}", updatedAnime.getSynopsis() != null ? 
                        (updatedAnime.getSynopsis().length() > 100 ? 
                                updatedAnime.getSynopsis().substring(0, 100) + "..." : 
                                updatedAnime.getSynopsis()) : "(仍为空)");
            } else {
                log.info("ℹ️ 未进行更新");
            }
            
        } catch (Exception e) {
            log.error("❌ 更新失败: {}", e.getMessage(), e);
        }
        
        log.info("========== 测试完成 ==========");
    }
}
