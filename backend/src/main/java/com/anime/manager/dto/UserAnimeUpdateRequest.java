package com.anime.manager.dto;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

/**
 * 用户追番记录更新请求DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserAnimeUpdateRequest {
    
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
}
