package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 评论实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Comment {
    
    /**
     * 评论ID
     */
    private Long id;
    
    /**
     * 动漫ID
     */
    private Long animeId;
    
    /**
     * 用户ID（评论人）
     */
    private Long userId;
    
    /**
     * 评论内容
     */
    private String content;
    
    /**
     * 点赞数
     */
    private Integer likeCount;
    
    /**
     * 点踩数
     */
    private Integer dislikeCount;
    
    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
}
