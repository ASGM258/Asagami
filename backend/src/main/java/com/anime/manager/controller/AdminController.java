package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.service.CacheService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 管理员控制器
 * 提供系统管理相关的API接口
 */
@Slf4j
@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminController {

    private final CacheService cacheService;

    /**
     * 清除所有Redis缓存
     * 
     * ️ 警告：这是一个危险操作，会清除所有缓存数据
     * 建议仅在开发环境或紧急情况下使用
     * 
     * @return 清除结果（包含删除的key数量）
     */
    @PostMapping("/cache/clear-all")
    public Result<Long> clearAllCache() {
        log.warn("⚠️ 收到清除所有缓存的请求");
        
        try {
            Long deletedCount = cacheService.clearAll();
            log.info("清除所有缓存成功: 删除数量={}", deletedCount);
            
            return Result.success("缓存清除成功", deletedCount);
        } catch (Exception e) {
            log.error("清除所有缓存失败: error={}", e.getMessage(), e);
            return Result.error("清除缓存失败: " + e.getMessage());
        }
    }
}
