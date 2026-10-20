package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.common.UserContext;
import com.anime.manager.dto.AnimeSimpleDTO;
import com.anime.manager.mapper.AnimeMapper;
import com.anime.manager.service.CacheService;
import com.anime.manager.service.AnimeQueryService;
import com.anime.manager.service.CommentService;
import com.anime.manager.vo.AnimeDetailVO;
import com.anime.manager.vo.CommentResponse;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 动漫查询服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AnimeQueryServiceImpl implements AnimeQueryService {
    
    private final AnimeMapper animeMapper;
    private final CommentService commentService;
    private final CacheService cacheService;
    
    /**
     * 分页查询动漫简单信息（包含中文标题、封面图和观看状态）
     */
    @Override
    public PageInfo<AnimeSimpleDTO> getAnimePage(Integer pageNum, Integer pageSize, String title, Integer year) {
        log.info("分页查询动漫: pageNum={}, pageSize={}, title={}, year={}", pageNum, pageSize, title, year);
            
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
            log.debug("未获取到用户ID（可能是公开接口），使用默认值0");
            userId = 0L;
        }
        log.debug("当前用户ID: {}", userId);
            
        // 处理title和year的null值，用于生成缓存key
        String titleKey = title != null ? title : "";
        Integer yearKey = year != null ? year : 0;
            
        // 生成缓存键
        String cacheKey = String.format(CacheKeyConstants.ANIME_PAGE, pageNum, pageSize, titleKey, yearKey);
            
        // 尝试从缓存获取
        @SuppressWarnings("unchecked")
        PageInfo<AnimeSimpleDTO> cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取数据: key={}", cacheKey);
            return cachedResult;
        }
            
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
            
        // 使用PageHelper进行分页
        PageHelper.startPage(pageNum, pageSize);
            
        // 查询数据（传入用户ID以获取观看状态）
        List<AnimeSimpleDTO> list = animeMapper.findAnimePageWithChineseName(title, year, userId);
            
        // 先用PageHelper的Page对象封装，保留分页信息
        com.github.pagehelper.Page<AnimeSimpleDTO> page = (com.github.pagehelper.Page<AnimeSimpleDTO>) list;
            
        // 用PageInfo包装，并设置正确的分页信息
        PageInfo<AnimeSimpleDTO> pageInfo = new PageInfo<>(list);
        pageInfo.setTotal(page.getTotal());
        pageInfo.setPages(page.getPages());
        pageInfo.setPageNum(page.getPageNum());
        pageInfo.setPageSize(page.getPageSize());
            
        log.info("查询结果: total={}, pages={}, 当前页数据量={}", pageInfo.getTotal(), pageInfo.getPages(), list != null ? list.size() : 0);
        if (list != null && !list.isEmpty()) {
            log.info("========== 第一页数据详情 ==========");
            for (int i = 0; i < Math.min(5, list.size()); i++) {
                AnimeSimpleDTO dto = list.get(i);
                log.info("第{}条: id={}, title={}, coverImage={}, episodes={}, rating={}, releaseYear={}, watchStatus={}",
                    i + 1, dto.getId(), dto.getTitle(), dto.getCoverImage(), 
                    dto.getEpisodes(), dto.getRating(), dto.getReleaseYear(), dto.getWatchStatus());
            }
            if (list.size() > 5) {
                log.info("... 还有 {} 条数据", list.size() - 5);
            }
            log.info("====================================");
        } else {
            log.warn("查询结果为空！请检查数据库是否有数据");
        }
            
        // 将结果存入缓存，过期时间30分钟
        cacheService.set(cacheKey, pageInfo, 30, TimeUnit.MINUTES);
        log.info("数据已存入缓存: key={}", cacheKey);
            
        return pageInfo;
    }
    
    /**
     * 分页查询用户追番历史（只返回user_anime表中存在的记录）
     */
    @Override
    public PageInfo<AnimeSimpleDTO> getUserWatchHistory(Integer pageNum, Integer pageSize, String title, Integer year) {
        log.info("分页查询用户追番历史: pageNum={}, pageSize={}, title={}, year={}", pageNum, pageSize, title, year);
            
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
            log.warn("未获取到用户ID，无法查询追番历史");
            throw new RuntimeException("请先登录");
        }
        log.debug("当前用户ID: {}", userId);
            
        // 处理title和year的null值，用于生成缓存key
        String titleKey = title != null ? title : "";
        Integer yearKey = year != null ? year : 0;
            
        // 生成缓存键
        String cacheKey = String.format(CacheKeyConstants.USER_WATCH_HISTORY, userId, pageNum, pageSize, titleKey, yearKey);
            
        // 尝试从缓存获取
        @SuppressWarnings("unchecked")
        PageInfo<AnimeSimpleDTO> cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取用户追番历史: key={}", cacheKey);
            return cachedResult;
        }
            
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
            
        // 使用PageHelper进行分页
        PageHelper.startPage(pageNum, pageSize);
            
        // 查询数据（只查询user_anime表中存在的记录）
        List<AnimeSimpleDTO> list = animeMapper.findUserWatchHistory(userId, title, year);
            
        // 先用PageHelper的Page对象封装，保留分页信息
        com.github.pagehelper.Page<AnimeSimpleDTO> page = (com.github.pagehelper.Page<AnimeSimpleDTO>) list;
            
        // 用PageInfo包装，并设置正确的分页信息
        PageInfo<AnimeSimpleDTO> pageInfo = new PageInfo<>(list);
        pageInfo.setTotal(page.getTotal());
        pageInfo.setPages(page.getPages());
        pageInfo.setPageNum(page.getPageNum());
        pageInfo.setPageSize(page.getPageSize());
            
        log.info("查询结果: total={}, pages={}", pageInfo.getTotal(), pageInfo.getPages());
            
        // 将结果存入缓存，过期时间30分钟
        cacheService.set(cacheKey, pageInfo, 30, TimeUnit.MINUTES);
        log.info("数据已存入缓存: key={}", cacheKey);
            
        return pageInfo;
    }
    
    /**
     * 查询动漫详情（包含动画信息和评论列表）
     */
    @Override
    public AnimeDetailVO getAnimeDetail(Long animeId) {
        log.info("查询动漫详情: animeId={}", animeId);
        
        if (animeId == null) {
            throw new IllegalArgumentException("动漫ID不能为空");
        }
        
        // 从 ThreadLocal获取当前用户ID
        Long userId = UserContext.getUserId();
        if (userId == null) {
            log.debug("未获取到用户ID，使用默认值0");
            userId = 0L;
        }
        log.debug("当前用户ID: {}", userId);
        
        // 生成缓存键（需要包含用户ID，因为不同用户的观看状态可能不同）
        String cacheKey = String.format(CacheKeyConstants.ANIME_DETAIL_WITH_USER, animeId, userId);
        
        // 尝试从缓存获取
        AnimeDetailVO cachedResult = cacheService.get(cacheKey);
        if (cachedResult != null) {
            log.info("从缓存获取动漫详情: key={}", cacheKey);
            return cachedResult;
        }
        
        // 缓存未命中，查询数据库
        log.info("缓存未命中，查询数据库");
        
        // 1. 查询动漫基本信息（联表查询中文名称和用户观看状态）
        AnimeDetailVO.AnimeInfo animeInfo = animeMapper.findAnimeDetailById(animeId, userId);
        if (animeInfo == null) {
            throw new RuntimeException("动漫不存在");
        }
        
        // 2. 复用CommentService查询评论列表（避免代码重复）
        java.util.List<CommentResponse> comments = commentService.getCommentsByAnimeId(animeId);
        
        // 3. 将CommentResponse转换为AnimeDetailVO.CommentWithUserInfo
        java.util.List<AnimeDetailVO.CommentWithUserInfo> commentList = comments.stream()
            .map(comment -> {
                return AnimeDetailVO.CommentWithUserInfo.builder()
                    .commentId(comment.getCommentId())
                    .content(comment.getContent())
                    .createdAt(comment.getCreatedAt())
                    .commenter(AnimeDetailVO.UserInfo.builder()
                        .userId(comment.getCommenter().getUserId())
                        .avatar(comment.getCommenter().getAvatar())
                        .nickname(comment.getCommenter().getNickname())
                        .build())
                    .build();
            })
            .toList();
        
        // 4. 组装最终结果
        AnimeDetailVO result = AnimeDetailVO.builder()
            .animeInfo(animeInfo)
            .comments(commentList)
            .build();
        
        log.info("查询完成: 评论数量={}, watchStatus={}", commentList.size(), animeInfo.getWatchStatus());
        
        // 将结果存入缓存，过期时间1小时
        cacheService.set(cacheKey, result, 1, TimeUnit.HOURS);
        log.info("数据已存入缓存: key={}", cacheKey);
        
        return result;
    }
}
