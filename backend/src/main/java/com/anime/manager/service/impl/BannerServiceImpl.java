package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.dto.BannerItem;
import com.anime.manager.mapper.AnimeScheduleMapper;
import com.anime.manager.service.BannerService;
import com.anime.manager.service.CacheService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 轮播图服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class BannerServiceImpl implements BannerService {
    
    private final AnimeScheduleMapper animeScheduleMapper;
    private final CacheService cacheService;
    
    /**
     * 获取随机轮播图数据
     * @param limit 数量限制，默认10条
     * @return 轮播图列表
     */
    @Override
    public List<BannerItem> getRandomBanners(Integer limit) {
        // 参数校验，默认10条
        if (limit == null || limit <= 0) {
            limit = 10;
        }
        
        // 限制最大数量为50，防止过多查询
        if (limit > 50) {
            limit = 50;
        }
        
        log.info("获取随机轮播图数据，数量: {}", limit);
        
        // 生成缓存键
        String cacheKey = String.format(CacheKeyConstants.BANNER, limit);
        
        // 尝试从缓存获取
        @SuppressWarnings("unchecked")
        List<BannerItem> cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取轮播图: key={}", cacheKey);
            return cachedResult;
        }
        
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
        
        List<BannerItem> banners = animeScheduleMapper.findRandomBanners(limit);
        
        log.info("查询结果: {} 条记录", banners != null ? banners.size() : 0);
        
        // 将结果存入缓存，过期时间2小时（轮播图变化频率低）
        cacheService.set(cacheKey, banners, 2, TimeUnit.HOURS);
        log.info("数据已存入缓存: key={}", cacheKey);
        
        return banners;
    }
}
