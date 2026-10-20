package com.anime.manager.dto;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

/**
 * 用户喜欢角色请求DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserFavoriteCharacterRequest {
    
    /**
     * 角色ID
     */
    private Long characterId;
    
    /**
     * 喜欢状态：0-默认（未喜欢），1-喜欢
     */
    private Integer favoriteStatus;
}
