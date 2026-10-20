package com.anime.manager.service;

/**
 * 用户喜欢角色服务接口
 */
public interface UserFavoriteCharacterService {
    
    /**
     * 更新或创建用户喜欢角色记录
     * 如果该用户对该角色的记录不存在则创建，否则更新
     * 
     * @param characterId 角色ID
     * @param favoriteStatus 喜欢状态：0-默认（未喜欢），1-喜欢
     * @return 是否成功
     */
    boolean updateOrCreateUserFavoriteCharacter(Long characterId, Integer favoriteStatus);
    
    /**
     * 查询用户是否喜欢某个角色
     * 
     * @param userId 用户ID
     * @param characterId 角色ID
     * @return true-喜欢，false-未喜欢
     */
    Boolean isUserLikedCharacter(Long userId, Long characterId);
}
