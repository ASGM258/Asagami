package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 角色评论点赞实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CharacterCommentLike {
    
    /**
     * 主键ID
     */
    private Long id;
    
    /**
     * 用户ID
     */
    private Long userId;
    
    /**
     * 评论ID（关联character_comment或character_comment_reply）
     */
    private Long commentId;
    
    /**
     * 层级：0=根评论(character_comment)，1=子回复(character_comment_reply)
     */
    private Integer level;
    
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    
    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
    
    /**
     * 是否删除（0-未删除，1-已删除）
     */
    private Integer isDeleted;
}
