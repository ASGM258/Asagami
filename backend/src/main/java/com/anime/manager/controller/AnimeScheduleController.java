package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.AnimeScheduleDTO;
import com.anime.manager.service.AnimeScheduleService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 番剧排期控制器（前端业务接口）
 */
@Slf4j
@RestController
@RequestMapping("/api/anime")
@RequiredArgsConstructor
public class AnimeScheduleController {
    
    private final AnimeScheduleService animeScheduleService;
    
    /**
     * 根据星期几查询当天更新的动漫列表
     * 
     * @param dayOfWeek 星期几 (可选, 1-7对应周一到周日，8表示待定，不传则返回所有)
     * @return 动漫排期列表
     */
    @GetMapping("/seasonal")
    public Result<List<AnimeScheduleDTO>> getSeasonalAnime(@RequestParam(required = false) Integer dayOfWeek) {
        log.info("收到查询当季新番请求: dayOfWeek={}", dayOfWeek);
        
        try {
            List<AnimeScheduleDTO> list = animeScheduleService.getAnimeByDayOfWeek(dayOfWeek);
            
            if (list == null || list.isEmpty()) {
                return Result.success("暂无数据", List.of());
            }
            
            return Result.success(list);
            
        } catch (Exception e) {
            log.error("查询失败: {}", e.getMessage(), e);
            return Result.error("查询失败: " + e.getMessage());
        }
    }
}
