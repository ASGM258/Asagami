package com.anime.manager.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 点赞请求DTO
 */
@Data
public class LikeRequest {
    
    /**
     * 目标ID（评论ID或回复ID，根据targetType确定）
     */
    @NotNull(message = "目标ID不能为空")
    private Long targetId;
    
    /**
     * 操作类型：like-点赞，dislike-点踩
     */
    @NotBlank(message = "操作类型不能为空")
    private String type;
    
    /**
     * 目标类型：comment-评论，reply-回复
     */
    @NotBlank(message = "目标类型不能为空")
    private String targetType;
}
