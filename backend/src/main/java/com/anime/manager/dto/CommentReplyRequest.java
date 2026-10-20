package com.anime.manager.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 评论回复请求DTO
 */
@Data
public class CommentReplyRequest {
    
    /**
     * 所属主评论ID（必填）
     */
    @NotNull(message = "评论ID不能为空")
    private Long commentId;
    
    /**
     * 父回复ID（可选，NULL表示直接回复主评论）
     */
    private Long parentReplyId;
    
    /**
     * 回复内容（必填）
     */
    @NotBlank(message = "回复内容不能为空")
    private String content;
}
