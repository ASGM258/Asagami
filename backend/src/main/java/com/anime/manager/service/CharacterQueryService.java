package com.anime.manager.service;

import com.anime.manager.dto.CharacterSimpleDTO;
import com.anime.manager.vo.CharacterDetailVO;
import com.github.pagehelper.PageInfo;

/**
 * 角色查询服务接口
 */
public interface CharacterQueryService {
    
    /**
     * 分页查询角色简单信息
     * 
     * @param pageNum 页码
     * @param pageSize 每页大小
     * @param name 角色名称搜索关键词（可选）
     * @return 分页结果
     */
    PageInfo<CharacterSimpleDTO> getCharacterPage(Integer pageNum, Integer pageSize, String name);
    
    /**
     * 查询角色详情（包含角色信息和评论列表）
     * 
     * @param characterId 角色ID
     * @return 角色详情VO
     */
    CharacterDetailVO getCharacterDetail(Long characterId);
    
    /**
     * 分页查询用户喜欢角色历史（只返回favorite_status=1的记录）
     * 
     * @param pageNum 页码
     * @param pageSize 每页大小
     * @param name 角色名称搜索关键词（可选）
     * @return 分页结果
     */
    PageInfo<CharacterSimpleDTO> getUserFavoriteCharacterHistory(Integer pageNum, Integer pageSize, String name);
}
