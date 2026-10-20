package com.anime.manager.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 更新评论请求DTO
 */
@Data
public class CommentUpdateRequest {
    
    /**
     * 评论ID（必填）
     */
    @NotNull(message = "评论ID不能为空")
    private Long commentId;
    
    /**
     * 评论内容（必填）
     */
    @NotBlank(message = "评论内容不能为空")
    private String content;
}
