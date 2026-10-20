package com.anime.manager.vo;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 动漫详情VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnimeDetailVO {
    
    /**
     * 动画信息
     */
    private AnimeInfo animeInfo;
    
    /**
     * 评论列表（包含评论人信息）
     */
    private List<CommentWithUserInfo> comments;
    
    /**
     * 动画信息内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class AnimeInfo {
        /**
         * 动漫ID
         */
        private Long id;
        
        /**
         * 标题（中文优先）
         */
        private String title;
        
        /**
         * 封面图URL
         */
        private String coverImage;
        
        /**
         * 简介
         */
        private String synopsis;
        
        /**
         * 题材/类型标签（逗号分隔）
         */
        private String genres;
        
        /**
         * 发行时间
         */
        private LocalDate releaseDate;
        
        /**
         * 评分
         */
        private BigDecimal rating;
        
        /**
         * 总集数
         */
        private Integer episodes;
        
        /**
         * 状态: 0-连载中, 1-已完结
         */
        private Integer status;
        
        /**
         * 用户观看状态: 0-未开始, 1-观看中, 2-已完成, 3-已放弃
         */
        private Integer watchStatus;
    }
    
    /**
     * 评论及评论人信息内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CommentWithUserInfo {
        /**
         * 评论ID
         */
        private Long commentId;
        
        /**
         * 评论内容
         */
        private String content;
        
        /**
         * 评论时间
         */
        private java.time.LocalDateTime createdAt;
        
        /**
         * 评论人信息
         */
        private UserInfo commenter;
    }
    
    /**
     * 用户信息内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class UserInfo {
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
