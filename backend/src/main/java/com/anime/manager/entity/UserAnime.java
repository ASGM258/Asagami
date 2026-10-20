package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 用户观看记录实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserAnime {
    
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
     * 观看状态: 0-未开始, 1-观看中, 2-已完成, 3-已放弃
     */
    private Integer watchStatus;
    
    /**
     * 当前看到第几集
     */
    private Integer currentEpisode;
    
    /**
     * 个人评分(1-10)
     */
    private Integer rating;
    
    /**
     * 评论
     */
    private String comment;
    
    /**
     * 标签
     */
    private String tags;
    
    /**
     * 开始观看时间
     */
    private LocalDateTime startedAt;
    
    /**
     * 完成观看时间
     */
    private LocalDateTime finishedAt;
    
    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
    
    /**
     * 更新时间
     */
    private LocalDateTime updatedAt;
}
