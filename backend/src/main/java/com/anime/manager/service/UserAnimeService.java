package com.anime.manager.service;

import com.anime.manager.dto.UserAnimeUpdateRequest;

/**
 * 用户追番记录服务接口
 */
public interface UserAnimeService {
    
    /**
     * 更新或创建用户追番记录
     * 如果该用户对该动漫的记录不存在则创建，否则更新
     * 
     * @param request 更新请求
     * @return 是否成功
     */
    boolean updateOrCreateUserAnime(UserAnimeUpdateRequest request);
}
