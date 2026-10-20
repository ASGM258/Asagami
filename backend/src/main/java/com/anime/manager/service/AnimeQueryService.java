package com.anime.manager.service;

import com.anime.manager.dto.AnimeSimpleDTO;
import com.anime.manager.vo.AnimeDetailVO;
import com.github.pagehelper.PageInfo;

/**
 * 动漫查询服务接口
 */
public interface AnimeQueryService {
    
    /**
     * 分页查询动漫简单信息（包含中文标题和封面图）
     * 
     * @param pageNum 页码
     * @param pageSize 每页大小
     * @param title 标题搜索关键词（可选，支持中文、英文、日文模糊匹配）
     * @param year 年份过滤（可选）
     * @return 分页结果
     */
    PageInfo<AnimeSimpleDTO> getAnimePage(Integer pageNum, Integer pageSize, String title, Integer year);
    
    /**
     * 分页查询用户追番历史（只返回user_anime表中存在的记录）
     * 
     * @param pageNum 页码
     * @param pageSize 每页大小
     * @param title 标题搜索关键词（可选，支持中文、英文、日文模糊匹配）
     * @param year 年份过滤（可选）
     * @return 分页结果
     */
    PageInfo<AnimeSimpleDTO> getUserWatchHistory(Integer pageNum, Integer pageSize, String title, Integer year);
    
    /**
     * 查询动漫详情（包含动画信息和评论列表）
     * 
     * @param animeId 动漫ID
     * @return 动漫详情VO
     */
    AnimeDetailVO getAnimeDetail(Long animeId);
}
