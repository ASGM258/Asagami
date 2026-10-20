package com.anime.manager.dto;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

/**
 * 角色简单信息DTO（用于列表展示）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CharacterSimpleDTO {
    
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
     * 受欢迎程度
     */
    private Integer favorites;
    
    /**
     * 用户是否喜欢该角色（0-未喜欢，1-喜欢）
     */
    private Integer isLiked;
}
