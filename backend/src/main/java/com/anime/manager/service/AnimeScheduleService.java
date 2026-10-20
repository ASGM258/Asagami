package com.anime.manager.service;

import com.anime.manager.dto.AnimeScheduleDTO;

import java.util.List;

/**
 * 番剧排期业务服务接口
 */
public interface AnimeScheduleService {
    
    /**
     * 根据星期几查询当天更新的动漫列表
     * 
     * @param dayOfWeek 星期几 (1-7对应周一到周日, 0表示查询所有)
     * @return 动漫排期列表
     */
    List<AnimeScheduleDTO> getAnimeByDayOfWeek(Integer dayOfWeek);
}
