package com.anime.manager.service;

/**
 * 角色爬虫服务接口
 *
 * <p>数据源已从 Jikan API（api.jikan.moe，已不可用）迁移到 AniList GraphQL。
 * AniList 的角色对象**不提供 MAL 角色ID**，因此标识改用 AniList 角色ID。
 */
public interface CharacterScraperService {
    
    /**
     * 抓取角色并保存到数据库
     *
     * @param maxPages 最大抓取页数（每页 50 个角色），null 表示不额外限制
     * @return 成功新增的角色数量
     */
    Integer fetchAndSaveAllCharacters(Integer maxPages);
    
    /**
     * 根据 AniList 角色ID抓取单个角色并保存
     *
     * @param anilistId AniList 角色ID（注意：不是 MAL 角色ID）
     * @return 角色ID（本系统 anime_character.id）
     */
    Long fetchAndSaveCharacter(Integer anilistId);
}
