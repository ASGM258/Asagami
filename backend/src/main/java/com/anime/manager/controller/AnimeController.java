package com.anime.manager.controller;

import com.anime.manager.common.Result;
import com.anime.manager.dto.AnimeDetailQueryRequest;
import com.anime.manager.dto.AnimeSimpleDTO;
import com.anime.manager.dto.UserAnimeUpdateRequest;
import com.anime.manager.service.AnimeQueryService;
import com.anime.manager.service.UserAnimeService;
import com.anime.manager.vo.AnimeDetailVO;
import com.github.pagehelper.PageInfo;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 动漫管理控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/anime")
@RequiredArgsConstructor
public class AnimeController {
    
    private final AnimeQueryService animeQueryService;
    private final UserAnimeService userAnimeService;
    
    /**
     * 分页查询动漫简单信息（包含中文标题和封面图）
     * 
     * @param pageNum 页码，默认1
     * @param pageSize 每页大小，默认10
     * @param title 标题搜索关键词（可选）
     * @param year 年份过滤（可选）
     * @return 分页结果
     */
    @GetMapping("/list")
    public Result<PageInfo<AnimeSimpleDTO>> getAnimePage(
            @RequestParam(required = false, defaultValue = "1") Integer pageNum,
            @RequestParam(required = false, defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String title,
            @RequestParam(required = false) Integer year) {
        log.info("收到分页查询请求: pageNum={}, pageSize={}, title={}, year={}", pageNum, pageSize, title, year);
        
        try {
            PageInfo<AnimeSimpleDTO> pageInfo = animeQueryService.getAnimePage(pageNum, pageSize, title, year);
            return Result.success(pageInfo);
        } catch (Exception e) {
            log.error("分页查询失败: error={}", e.getMessage(), e);
            return Result.error("查询失败: " + e.getMessage());
        }
    }
    
    /**
     * 分页查询用户追番历史（只返回user_anime表中存在的记录）
     * 
     * @param pageNum 页码，默认1
     * @param pageSize 每页大小，默认10
     * @param title 标题搜索关键词（可选）
     * @param year 年份过滤（可选）
     * @return 分页结果
     */
    @GetMapping("/watch-history")
    public Result<PageInfo<AnimeSimpleDTO>> getUserWatchHistory(
            @RequestParam(required = false, defaultValue = "1") Integer pageNum,
            @RequestParam(required = false, defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String title,
            @RequestParam(required = false) Integer year) {
        log.info("收到追番历史查询请求: pageNum={}, pageSize={}, title={}, year={}", pageNum, pageSize, title, year);
        
        try {
            PageInfo<AnimeSimpleDTO> pageInfo = animeQueryService.getUserWatchHistory(pageNum, pageSize, title, year);
            return Result.success(pageInfo);
        } catch (RuntimeException e) {
            log.error("追番历史查询失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 更新或创建用户追番记录
     * 
     * @param request 更新请求（包含动漫ID、观看状态、当前集数、评分、评论、标签）
     * @return 操作结果
     */
    @PostMapping("/user-anime/update")
    public Result<Boolean> updateUserAnime(@RequestBody UserAnimeUpdateRequest request) {
        log.info("收到更新追番记录请求: animeId={}, watchStatus={}", 
                request.getAnimeId(), request.getWatchStatus());
        
        try {
            boolean success = userAnimeService.updateOrCreateUserAnime(request);
            if (success) {
                return Result.success("更新成功", true);
            } else {
                return Result.error("更新失败");
            }
        } catch (RuntimeException e) {
            log.error("更新追番记录失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
    
    /**
     * 查询动漫详情（包含动画信息和评论列表）
     * 
     * @param request 查询请求（包含动漫ID）
     * @return 动漫详情VO
     */
    @PostMapping("/detail")
    public Result<AnimeDetailVO> getAnimeDetail(@Valid @RequestBody AnimeDetailQueryRequest request) {
        log.info("收到动漫详情查询请求: animeId={}", request.getAnimeId());
        
        try {
            AnimeDetailVO detail = animeQueryService.getAnimeDetail(request.getAnimeId());
            return Result.success(detail);
        } catch (IllegalArgumentException e) {
            log.error("参数错误: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (RuntimeException e) {
            log.error("查询动漫详情失败: error={}", e.getMessage(), e);
            return Result.error(e.getMessage());
        } catch (Exception e) {
            log.error("系统错误: error={}", e.getMessage(), e);
            return Result.error("系统错误: " + e.getMessage());
        }
    }
}
