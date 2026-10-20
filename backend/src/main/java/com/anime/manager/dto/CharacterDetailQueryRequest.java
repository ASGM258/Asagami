package com.anime.manager.dto;

import lombok.Data;
import jakarta.validation.constraints.NotNull;

/**
 * 角色详情查询请求DTO
 */
@Data
public class CharacterDetailQueryRequest {
    /**
     * 角色ID（必填）
     */
    @NotNull(message = "角色ID不能为空")
    private Long characterId;
}
