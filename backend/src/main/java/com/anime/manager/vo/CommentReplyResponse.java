package com.anime.manager.vo;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 评论回复响应VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CommentReplyResponse {
    
    /**
     * 回复ID
     */
    private Long replyId;
    
    /**
     * 父回复ID（NULL表示直接回复主评论）
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
    
    /**
     * 回复人信息
     */
    private ReplyUserInfo replier;
    
    /**
     * 子回复列表（嵌套回复）
     */
    private List<CommentReplyResponse> childReplies;
    
    /**
     * 回复人信息内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ReplyUserInfo {
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
