package com.anime.manager.vo;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.util.Set;

/**
 * 用户点赞状态响应VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserLikeStatusResponse {
    
    /**
     * 已点赞的评论ID集合
     */
    private Set<Long> likedCommentIds;
    
    /**
     * 已点赞的回复ID集合
     */
    private Set<Long> likedReplyIds;
}
