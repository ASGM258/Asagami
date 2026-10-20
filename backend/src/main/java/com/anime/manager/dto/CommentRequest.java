package com.anime.manager.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 发表评论请求DTO
 */
@Data
public class CommentRequest {
    
    /**
     * 动漫ID（必填）
     */
    @NotNull(message = "动漫ID不能为空")
    private Long animeId;
    
    /**
     * 评论内容（必填）
     */
    @NotBlank(message = "评论内容不能为空")
    private String content;
}
