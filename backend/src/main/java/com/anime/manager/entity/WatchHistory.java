package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 观看历史记录实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class WatchHistory {
    
    /**
     * 记录ID
     */
    private Long id;
    
    /**
     * 用户ID
     */
    private Long userId;
    
    /**
     * 动漫ID
     */
    private Long animeId;
    
    /**
     * 观看的集数
     */
    private Integer episode;
    
    /**
     * 观看时间
     */
    private LocalDateTime watchedAt;
    
    /**
     * 观看时长(分钟)
     */
    private Integer duration;
}
