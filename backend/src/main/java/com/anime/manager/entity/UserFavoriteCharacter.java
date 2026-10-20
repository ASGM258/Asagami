package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 用户喜欢角色实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserFavoriteCharacter {
    
    /**
     * 主键ID
     */
    private Long id;
    
    /**
     * 用户ID
     */
    private Long userId;
    
    /**
     * 角色ID
     */
    private Long characterId;
    
    /**
     * 喜欢状态：0-默认（未喜欢），1-喜欢
     */
    private Integer favoriteStatus;
    
    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
    
    /**
     * 更新时间
     */
    private LocalDateTime updatedAt;
}
