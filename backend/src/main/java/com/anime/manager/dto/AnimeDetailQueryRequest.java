package com.anime.manager.dto;

import lombok.Data;
import jakarta.validation.constraints.NotNull;

/**
 * 动漫详情查询请求DTO
 */
@Data
public class AnimeDetailQueryRequest {
    /**
     * 动漫ID（必填）
     */
    @NotNull(message = "动漫ID不能为空")
    private Long animeId;
}
