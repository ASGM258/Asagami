package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.common.UserContext;
import com.anime.manager.entity.UserFavoriteCharacter;
import com.anime.manager.mapper.UserFavoriteCharacterMapper;
import com.anime.manager.service.CacheService;
import com.anime.manager.service.UserFavoriteCharacterService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 用户喜欢角色服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserFavoriteCharacterServiceImpl implements UserFavoriteCharacterService {
    
    private final UserFavoriteCharacterMapper userFavoriteCharacterMapper;
    private final CacheService cacheService;
    
    /**
     * 更新或创建用户喜欢角色记录
     * 如果该用户对该角色的记录不存在则创建，否则更新
     */
    @Override
    public boolean updateOrCreateUserFavoriteCharacter(Long characterId, Integer favoriteStatus) {
        log.info("更新或创建用户喜欢角色记录: characterId={}, favoriteStatus={}", 
                characterId, favoriteStatus);
        
        // 从ThreadLocal获取当前用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            log.error("未获取到用户ID");
            throw new RuntimeException("请先登录");
        }
        
        // 验证必要参数
        if (characterId == null) {
            throw new RuntimeException("角色ID不能为空");
        }
        
        if (favoriteStatus == null) {
            throw new RuntimeException("喜欢状态不能为空");
        }
        
        // 验证喜欢状态的有效性：只能是0（默认）或1（喜欢）
        if (favoriteStatus != 0 && favoriteStatus != 1) {
            throw new RuntimeException("喜欢状态无效，只能是0（默认）或1（喜欢）");
        }
        
        // 查询是否已存在记录
        UserFavoriteCharacter existingRecord = userFavoriteCharacterMapper.findByUserIdAndCharacterId(userId, characterId);
        
        if (existingRecord == null) {
            // 不存在则创建新记录
            log.info("创建新的喜欢记录: userId={}, characterId={}", userId, characterId);
            
            UserFavoriteCharacter userFavoriteCharacter = new UserFavoriteCharacter();
            userFavoriteCharacter.setUserId(userId);
            userFavoriteCharacter.setCharacterId(characterId);
            userFavoriteCharacter.setFavoriteStatus(favoriteStatus);
            
            int result = userFavoriteCharacterMapper.insert(userFavoriteCharacter);
            log.info("创建喜欢记录成功: id={}", userFavoriteCharacter.getId());
            
            // 清除相关缓存
            clearUserCache(userId, characterId);
            
            return result > 0;
            
        } else {
            // 存在则更新记录
            log.info("更新已有喜欢记录: id={}, userId={}, characterId={}", 
                    existingRecord.getId(), userId, characterId);
            
            // 构建更新对象
            UserFavoriteCharacter updateUserFavoriteCharacter = new UserFavoriteCharacter();
            updateUserFavoriteCharacter.setId(existingRecord.getId());
            updateUserFavoriteCharacter.setFavoriteStatus(favoriteStatus);
            
            int result = userFavoriteCharacterMapper.updateSelective(updateUserFavoriteCharacter);
            log.info("更新喜欢记录成功: affectedRows={}", result);
            
            // 清除相关缓存
            clearUserCache(userId, characterId);
            
            return result > 0;
        }
    }
    
    /**
     * 查询用户是否喜欢某个角色
     */
    @Override
    public Boolean isUserLikedCharacter(Long userId, Long characterId) {
        if (userId == null || characterId == null) {
            return false;
        }
        
        try {
            UserFavoriteCharacter record = userFavoriteCharacterMapper.findByUserIdAndCharacterId(userId, characterId);
            // 如果记录存在且favoriteStatus为1，则表示喜欢
            return record != null && record.getFavoriteStatus() != null && record.getFavoriteStatus() == 1;
        } catch (Exception e) {
            log.error("查询用户喜欢状态失败: userId={}, characterId={}", userId, characterId, e);
            return false;
        }
    }
    
    /**
     * 清除用户相关的缓存
     */
    private void clearUserCache(Long userId, Long characterId) {
        // 清除用户的喜欢列表缓存（如果有）
        String favoritePattern = "user:favorite:character:" + userId + "*";
        cacheService.deleteByPattern(favoritePattern);
        
        // 清除角色详情缓存（如果喜欢数变化）
        if (characterId != null) {
            String detailKey = "character:detail:" + characterId;
            cacheService.delete(detailKey);
        }
        
        // 清除该用户的角色分页列表缓存（因为包含isLiked字段）
        String pagePattern = "character:page:*:*:*:" + userId;
        cacheService.deleteByPattern(pagePattern);
        
        // 清除用户喜欢角色历史缓存
        String historyPattern = CacheKeyConstants.userFavoriteCharacterPattern(userId);
        cacheService.deleteByPattern(historyPattern);
        
        log.info("已清除用户{}的相关缓存", userId);
    }
}
