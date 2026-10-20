package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.BannerItem;
import com.anime.manager.service.BannerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 轮播图控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/anime")
@RequiredArgsConstructor
public class BannerController {
    
    private final BannerService bannerService;
    
    /**
     * 获取随机轮播图数据
     * 
     * @param limit 数量限制（可选，默认10条，最大50条）
     * @return 轮播图列表
     */
    @GetMapping("/banners")
    public Result<List<BannerItem>> getBanners(@RequestParam(required = false) Integer limit) {
        log.info("收到获取轮播图请求: limit={}", limit);
        
        try {
            List<BannerItem> banners = bannerService.getRandomBanners(limit);
            
            if (banners == null || banners.isEmpty()) {
                return Result.success("暂无数据", List.of());
            }
            
            return Result.success(banners);
            
        } catch (Exception e) {
            log.error("获取轮播图失败: {}", e.getMessage(), e);
            return Result.error("获取失败: " + e.getMessage());
        }
    }
}
