package com.anime.manager.service;

/**
 * 当季新番抓取服务接口
 */
public interface SeasonalScraperService {
    
    /**
     * 抓取当年当季新番并保存到anime_schedule表
     * 
     * @return 抓取的动漫数量
     */
    Integer fetchAndSaveSeasonalAnime();
    
    /**
     * 清空现有排期数据并重新抓取
     * 
     * @return 抓取的动漫数量
     */
    Integer refreshSeasonalAnime();
    
    /**
     * 智能更新当季新番数据（定时任务使用）
     * - 如果当前是当季，则更新现有数据
     * - 如果已进入下一季度，则删除上一季度数据并插入新季度数据
     * 
     * @return 抓取的动漫数量
     */
    Integer smartUpdateSeasonalAnime();
}
