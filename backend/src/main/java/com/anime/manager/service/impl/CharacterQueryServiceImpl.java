package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.common.UserContext;
import com.anime.manager.dto.CharacterSimpleDTO;
import com.anime.manager.entity.Character;
import com.anime.manager.mapper.CharacterMapper;
import com.anime.manager.service.CacheService;
import com.anime.manager.service.CharacterCommentService;
import com.anime.manager.service.CharacterQueryService;
import com.anime.manager.service.UserFavoriteCharacterService;
import com.anime.manager.vo.CharacterCommentResponse;
import com.anime.manager.vo.CharacterDetailVO;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 角色查询服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CharacterQueryServiceImpl implements CharacterQueryService {
    
    private final CharacterMapper characterMapper;
    private final CharacterCommentService characterCommentService;
    private final CacheService cacheService;
    private final UserFavoriteCharacterService userFavoriteCharacterService;
    
    /**
     * 分页查询角色简单信息
     */
    @Override
    public PageInfo<CharacterSimpleDTO> getCharacterPage(Integer pageNum, Integer pageSize, String name) {
        log.info("分页查询角色: pageNum={}, pageSize={}, name={}", pageNum, pageSize, name);
        
        // 设置默认值
        if (pageNum == null || pageNum < 1) {
            pageNum = 1;
        }
        if (pageSize == null || pageSize < 1) {
            pageSize = 10;
        }
        
        // 处理name的null值，用于生成缓存key
        String nameKey = name != null ? name : "";
        
        // 获取当前用户ID
        Long userId = UserContext.getUserId();
        
        // 生成缓存键（包含userId以区分不同用户的喜欢状态）
        String cacheKey = String.format("character:page:%d:%d:%s:%d", pageNum, pageSize, nameKey, userId != null ? userId : 0);
        
        // 尝试从缓存获取
        @SuppressWarnings("unchecked")
        PageInfo<CharacterSimpleDTO> cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取数据: key={}", cacheKey);
            return cachedResult;
        }
        
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
        
        // 使用PageHelper进行分页
        PageHelper.startPage(pageNum, pageSize);
        
        // 查询数据（传递userId以联表查询喜欢状态）
        List<Character> characters = characterMapper.findCharactersPage(name, userId);
        
        // 先用PageHelper的Page对象封装，保留分页信息
        com.github.pagehelper.Page<Character> page = (com.github.pagehelper.Page<Character>) characters;
        
        // 转换为DTO（包含isLiked字段）
        List<CharacterSimpleDTO> list = characters.stream()
            .map(character -> CharacterSimpleDTO.builder()
                .id(character.getId())
                .malId(character.getMalId())
                .name(character.getName())
                .nameJp(character.getNameJp())
                .imageUrl(character.getImageUrl())
                .favorites(character.getFavorites())
                .isLiked(character.getIsLiked() != null ? character.getIsLiked() : 0)
                .build())
            .toList();
        
        // 用PageInfo包装转换后的List，并设置正确的分页信息
        PageInfo<CharacterSimpleDTO> pageInfo = new PageInfo<>(list);
        pageInfo.setTotal(page.getTotal());
        pageInfo.setPages(page.getPages());
        pageInfo.setPageNum(page.getPageNum());
        pageInfo.setPageSize(page.getPageSize());
        
        log.info("查询结果: total={}, pages={}, 当前页数据量={}", 
            pageInfo.getTotal(), pageInfo.getPages(), list.size());
        
        // 将结果存入缓存，过期时间30分钟
        cacheService.set(cacheKey, pageInfo, 30, TimeUnit.MINUTES);
        log.info("数据已存入缓存: key={}", cacheKey);
        
        return pageInfo;
    }
    
    /**
     * 查询角色详情（包含角色信息和评论列表）
     */
    @Override
    public CharacterDetailVO getCharacterDetail(Long characterId) {
        log.info("查询角色详情: characterId={}", characterId);
        
        if (characterId == null) {
            throw new IllegalArgumentException("角色ID不能为空");
        }
        
        // 生成缓存键
        String cacheKey = String.format("character:detail:%d", characterId);
        
        // 尝试从缓存获取
        CharacterDetailVO cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取角色详情: key={}", cacheKey);
            return cachedResult;
        }
        
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
        
        // 1. 查询角色基本信息
        CharacterDetailVO.CharacterInfo characterInfo = characterMapper.findCharacterDetailById(characterId);
        if (characterInfo == null) {
            throw new RuntimeException("角色不存在");
        }
        
        // 2. 查询评论列表
        List<CharacterCommentResponse> comments = characterCommentService.getCommentsByCharacterId(characterId);
        
        // 3. 将CharacterCommentResponse转换为CharacterDetailVO.CommentWithUserInfo
        List<CharacterDetailVO.CommentWithUserInfo> commentList = comments.stream()
            .map(comment -> {
                return CharacterDetailVO.CommentWithUserInfo.builder()
                    .commentId(comment.getCommentId())
                    .content(comment.getContent())
                    .createdAt(comment.getCreatedAt())
                    .likeCount(comment.getLikeCount())
                    .dislikeCount(comment.getDislikeCount())
                    .commenter(CharacterDetailVO.UserInfo.builder()
                        .userId(comment.getCommenter().getUserId())
                        .avatar(comment.getCommenter().getAvatar())
                        .nickname(comment.getCommenter().getNickname())
                        .build())
                    .build();
            })
            .toList();
        
        // 4. 查询用户是否喜欢该角色
        Boolean isLiked = false;
        Long userId = UserContext.getUserId();
        if (userId != null) {
            try {
                isLiked = userFavoriteCharacterService.isUserLikedCharacter(userId, characterId);
            } catch (Exception e) {
                log.warn("查询用户喜欢状态失败: {}", e.getMessage());
                isLiked = false;
            }
        }
        
        // 5. 组装最终结果
        CharacterDetailVO result = CharacterDetailVO.builder()
            .characterInfo(characterInfo)
            .comments(commentList)
            .isLiked(isLiked)
            .build();
        
        log.info("查询完成: 评论数量={}, isLiked={}", commentList.size(), isLiked);
        
        // 将结果存入缓存，过期时间1小时
        cacheService.set(cacheKey, result, 1, TimeUnit.HOURS);
        log.info("数据已存入缓存: key={}", cacheKey);
        
        return result;
    }
    
    /**
     * 分页查询用户喜欢角色历史（只返回favorite_status=1的记录）
     */
    @Override
    public PageInfo<CharacterSimpleDTO> getUserFavoriteCharacterHistory(Integer pageNum, Integer pageSize, String name) {
        log.info("分页查询用户喜欢角色历史: pageNum={}, pageSize={}, name={}", pageNum, pageSize, name);
        
        // 设置默认值
        if (pageNum == null || pageNum < 1) {
            pageNum = 1;
        }
        if (pageSize == null || pageSize < 1) {
            pageSize = 10;
        }
        
        // 从 ThreadLocal获取当前用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            log.warn("未获取到用户ID，无法查询喜欢角色历史");
            throw new RuntimeException("请先登录");
        }
        log.debug("当前用户ID: {}", userId);
        
        // 处理name的null值，用于生成缓存key
        String nameKey = name != null ? name : "";
        
        // 生成缓存键
        String cacheKey = String.format(CacheKeyConstants.USER_FAVORITE_CHARACTER_HISTORY, userId, pageNum, pageSize, nameKey);
        
        // 尝试从缓存获取
        @SuppressWarnings("unchecked")
        PageInfo<CharacterSimpleDTO> cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取用户喜欢角色历史: key={}", cacheKey);
            return cachedResult;
        }
        
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
        
        // 使用PageHelper进行分页
        PageHelper.startPage(pageNum, pageSize);
        
        // 查询数据（只查询favorite_status=1的记录）
        List<Character> characters = characterMapper.findUserFavoriteCharacterHistory(userId, name);
        
        // 先用PageHelper的Page对象封装，保留分页信息
        com.github.pagehelper.Page<Character> page = (com.github.pagehelper.Page<Character>) characters;
        
        // 转换为DTO（isLiked始终为1，因为只查询喜欢的记录）
        List<CharacterSimpleDTO> list = characters.stream()
            .map(character -> CharacterSimpleDTO.builder()
                .id(character.getId())
                .malId(character.getMalId())
                .name(character.getName())
                .nameJp(character.getNameJp())
                .imageUrl(character.getImageUrl())
                .favorites(character.getFavorites())
                .isLiked(1)  // 喜欢的记录，状态始终为1
                .build())
            .toList();
        
        // 用PageInfo包装转换后的List，并设置正确的分页信息
        PageInfo<CharacterSimpleDTO> pageInfo = new PageInfo<>(list);
        pageInfo.setTotal(page.getTotal());
        pageInfo.setPages(page.getPages());
        pageInfo.setPageNum(page.getPageNum());
        pageInfo.setPageSize(page.getPageSize());
        
        log.info("查询结果: total={}, pages={}, 当前页数据量={}", 
            pageInfo.getTotal(), pageInfo.getPages(), list.size());
        
        // 将结果存入缓存，过期时间30分钟
        cacheService.set(cacheKey, pageInfo, 30, TimeUnit.MINUTES);
        log.info("数据已存入缓存: key={}", cacheKey);
        
        return pageInfo;
    }
}
