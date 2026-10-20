package com.anime.manager.service;

/**
 * 动漫数据抓取服务接口
 */
public interface AnimeScraperService {
    
    /**
     * 根据MAL ID抓取动漫信息并保存到数据库
     * 
     * @param malId MyAnimeList的动漫ID
     * @return 保存的动漫ID
     */
    Long fetchAndSaveAnime(Integer malId);
}
