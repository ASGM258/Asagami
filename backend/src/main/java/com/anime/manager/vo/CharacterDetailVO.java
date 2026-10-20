package com.anime.manager.vo;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.util.List;

/**
 * 角色详情VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CharacterDetailVO {
    
    /**
     * 角色基本信息
     */
    private CharacterInfo characterInfo;
    
    /**
     * 评论列表（包含评论人信息）
     */
    private List<CommentWithUserInfo> comments;
    
    /**
     * 用户是否喜欢该角色
     */
    private Boolean isLiked;
    
    /**
     * 角色基本信息内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CharacterInfo {
        /**
         * 角色ID
         */
        private Long id;
        
        /**
         * MAL角色ID
         */
        private Integer malId;
        
        /**
         * 角色名称（英文/罗马音）
         */
        private String name;
        
        /**
         * 角色名称（日文）
         */
        private String nameJp;
        
        /**
         * 角色头像URL
         */
        private String imageUrl;
        
        /**
         * 角色简介
         */
        private String about;
        
        /**
         * 角色昵称/别名（逗号分隔）
         */
        private String nicknames;
        
        /**
         * 角色生日（格式：MM-DD）
         */
        private String birthday;
        
        /**
         * 受欢迎程度
         */
        private Integer favorites;
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
         * 点赞数
         */
        private Integer likeCount;
        
        /**
         * 点踩数
         */
        private Integer dislikeCount;
        
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
