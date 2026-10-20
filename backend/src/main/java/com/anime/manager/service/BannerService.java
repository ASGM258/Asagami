package com.anime.manager.service;

import com.anime.manager.dto.BannerItem;

import java.util.List;

/**
 * 轮播图服务接口
 */
public interface BannerService {
    
    /**
     * 获取随机轮播图数据
     * @param limit 数量限制，默认10条
     * @return 轮播图列表
     */
    List<BannerItem> getRandomBanners(Integer limit);
}
