package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 角色评论回复实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CharacterCommentReply {
    
    /**
     * 回复ID
     */
    private Long id;
    
    /**
     * 评论ID（关联character_comment）
     */
    private Long commentId;
    
    /**
     * 父回复ID（NULL表示顶级回复）
     */
    private Long parentReplyId;
    
    /**
     * 用户ID（回复人）
     */
    private Long userId;
    
    /**
     * 被回复的用户ID
     */
    private Long replyToUserId;
    
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
