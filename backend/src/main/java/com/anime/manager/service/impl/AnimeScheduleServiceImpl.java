package com.anime.manager.service.impl;

import com.anime.manager.dto.AnimeScheduleDTO;
import com.anime.manager.mapper.AnimeScheduleMapper;
import com.anime.manager.service.AnimeScheduleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 番剧排期业务服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AnimeScheduleServiceImpl implements AnimeScheduleService {
    
    private final AnimeScheduleMapper animeScheduleMapper;
    
    /**
     * 根据星期几查询当天更新的动漫列表
     * @param dayOfWeek 星期几 (1-7对应周一到周日，8表示待定/null，null或不传表示查询所有)
     */
    @Override
    public List<AnimeScheduleDTO> getAnimeByDayOfWeek(Integer dayOfWeek) {
        log.info("查询星期{}的更新动漫", dayOfWeek);
        
        // 参数校验：允许 1-8（8表示待定），或 null（查询所有）
        if (dayOfWeek != null && (dayOfWeek < 1 || dayOfWeek > 8)) {
            log.warn("无效的星期参数: {}, 使用默认值null(查询所有)", dayOfWeek);
            dayOfWeek = null;
        }
        
        // 传入星期数字（1-7对应周一到周日，8表示待定/null）
        List<AnimeScheduleDTO> result = animeScheduleMapper.findDTOByDayOfWeek(dayOfWeek);
        
        log.info("查询结果: {} 条记录", result != null ? result.size() : 0);
        return result;
    }
}
