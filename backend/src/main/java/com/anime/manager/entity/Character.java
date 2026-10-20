package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 动漫角色实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Character {
    
    /**
     * 角色ID
     */
    private Long id;
    
    /**
     * MAL角色ID（历史数据来自 Jikan API）
     */
    private Integer malId;
    
    /**
     * AniList角色ID（当前数据源）
     *
     * <p>AniList 的角色对象不提供 MAL ID，因此单独建列。
     * 新数据的唯一去重键为本字段，malId 仅保留历史语义。
     */
    private Integer anilistId;
    
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
     * 角色简介
     */
    private String about;
    
    /**
     * 角色昵称/别名（逗号分隔）
     */
    private String nicknames;
    
    /**
     * 角色生日（格式：MM-DD，可能为空）
     */
    private String birthday;
    
    /**
     * 角色 favorites 数量（受欢迎程度）
     */
    private Integer favorites;
    
    /**
     * 用户是否喜欢该角色（0-未喜欢，1-喜欢）- 仅用于查询结果
     */
    private Integer isLiked;
    
    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
    
    /**
     * 更新时间
     */
    private LocalDateTime updatedAt;
}
