package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 评论回复实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CommentReply {
    
    /**
     * 回复ID
     */
    private Long id;
    
    /**
     * 所属主评论ID
     */
    private Long commentId;
    
    /**
     * 回复用户ID
     */
    private Long userId;
    
    /**
     * 父回复ID（用于嵌套回复，NULL表示直接回复主评论）
     */
    private Long parentReplyId;
    
    /**
     * 回复内容
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
