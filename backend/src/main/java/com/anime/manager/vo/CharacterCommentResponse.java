package com.anime.manager.vo;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 角色评论响应VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CharacterCommentResponse {
    
    /**
     * 评论ID
     */
    private Long commentId;
    
    /**
     * 角色ID
     */
    private Long characterId;
    
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
    
    /**
     * 评论人信息
     */
    private CommenterInfo commenter;
    
    /**
     * 回复列表
     */
    private List<CommentReplyResponse> replies;
    
    /**
     * 评论人信息内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CommenterInfo {
        /**
         * 用户ID
         */
        private Long userId;
        
        /**
         * 头像URL
         */
        private String avatar;
        
        /**
         * 昵称
         */
        private String nickname;
    }
}
