package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.common.UserContext;
import com.anime.manager.dto.UserAnimeUpdateRequest;
import com.anime.manager.entity.UserAnime;
import com.anime.manager.mapper.UserAnimeMapper;
import com.anime.manager.service.CacheService;
import com.anime.manager.service.UserAnimeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 用户追番记录服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserAnimeServiceImpl implements UserAnimeService {
    
    private final UserAnimeMapper userAnimeMapper;
    private final CacheService cacheService;
    
    /**
     * 更新或创建用户追番记录
     * 如果该用户对该动漫的记录不存在则创建，否则更新
     */
    @Override
    public boolean updateOrCreateUserAnime(UserAnimeUpdateRequest request) {
        log.info("更新或创建用户追番记录: animeId={}, watchStatus={}", 
                request.getAnimeId(), request.getWatchStatus());
        
        // 从ThreadLocal获取当前用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            log.error("未获取到用户ID");
            throw new RuntimeException("请先登录");
        }
        
        // 验证必要参数
        if (request.getAnimeId() == null) {
            throw new RuntimeException("动漫ID不能为空");
        }
        
        if (request.getWatchStatus() == null) {
            throw new RuntimeException("观看状态不能为空");
        }
        
        // 查询是否已存在记录
        UserAnime existingRecord = userAnimeMapper.findByUserIdAndAnimeId(userId, request.getAnimeId());
        
        if (existingRecord == null) {
            // 不存在则创建新记录
            log.info("创建新的追番记录: userId={}, animeId={}", userId, request.getAnimeId());
            
            UserAnime userAnime = new UserAnime();
            userAnime.setUserId(userId);
            userAnime.setAnimeId(request.getAnimeId());
            userAnime.setWatchStatus(request.getWatchStatus());
            userAnime.setCurrentEpisode(request.getCurrentEpisode());
            userAnime.setRating(request.getRating());
            userAnime.setComment(request.getComment());
            userAnime.setTags(request.getTags());
            
            // 根据观看状态设置开始/完成时间
            if (request.getWatchStatus() == 1) {
                // 观看中 - 设置开始时间
                userAnime.setStartedAt(LocalDateTime.now());
            } else if (request.getWatchStatus() == 2) {
                // 已完成 - 设置开始和完成时间
                userAnime.setStartedAt(LocalDateTime.now());
                userAnime.setFinishedAt(LocalDateTime.now());
            }
            
            int result = userAnimeMapper.insert(userAnime);
            log.info("创建追番记录成功: id={}", userAnime.getId());
            
            // 清除相关缓存
            clearUserCache(userId, request.getAnimeId());
            
            return result > 0;
            
        } else {
            // 存在则更新记录
            log.info("更新已有追番记录: id={}, userId={}, animeId={}", 
                    existingRecord.getId(), userId, request.getAnimeId());
            
            // 构建更新对象（只更新非null字段）
            UserAnime updateUserAnime = new UserAnime();
            updateUserAnime.setId(existingRecord.getId());
            updateUserAnime.setWatchStatus(request.getWatchStatus());
            updateUserAnime.setCurrentEpisode(request.getCurrentEpisode());
            updateUserAnime.setRating(request.getRating());
            updateUserAnime.setComment(request.getComment());
            updateUserAnime.setTags(request.getTags());
            
            // 根据观看状态设置开始/完成时间
            if (request.getWatchStatus() == 1 && existingRecord.getStartedAt() == null) {
                // 变为观看中且之前没有开始时间
                updateUserAnime.setStartedAt(LocalDateTime.now());
            } else if (request.getWatchStatus() == 2 && existingRecord.getFinishedAt() == null) {
                // 变为已完成且之前没有完成时间
                updateUserAnime.setFinishedAt(LocalDateTime.now());
            }
            
            int result = userAnimeMapper.updateSelective(updateUserAnime);
            log.info("更新追番记录成功: affectedRows={}", result);
            
            // 清除相关缓存
            clearUserCache(userId, request.getAnimeId());
            
            return result > 0;
        }
    }
    
    /**
     * 清除用户相关的缓存
     */
    private void clearUserCache(Long userId, Long animeId) {
        // 清除该用户的追番历史缓存（所有分页和过滤条件）
        String historyPattern = CacheKeyConstants.userHistoryPattern(userId);
        cacheService.deleteByPattern(historyPattern);
        
        // 清除动漫列表缓存（因为观看状态可能改变）
        String animePagePattern = CacheKeyConstants.animePagePattern();
        cacheService.deleteByPattern(animePagePattern);
        
        // 清除动漫详情缓存（如果评论或点赞数变化）
        if (animeId != null) {
            String detailKey = String.format(CacheKeyConstants.ANIME_DETAIL, animeId);
            cacheService.delete(detailKey);
        }
        
        log.info("已清除用户{}的相关缓存，清除模式: {}", userId, historyPattern);
    }
}
