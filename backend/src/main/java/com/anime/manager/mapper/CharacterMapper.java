package com.anime.manager.mapper;

import com.anime.manager.entity.Character;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 角色Mapper接口
 */
@Mapper
public interface CharacterMapper {
    
    /**
     * 插入角色
     */
    int insert(Character character);
    
    /**
     * 根据MAL ID查询角色（历史数据，来自 Jikan 时代）
     */
    Character findByMalId(@Param("malId") Integer malId);
    
    /**
     * 根据 AniList 角色ID查询角色
     *
     * <p>当前数据源（AniList）的唯一去重键。AniList 不提供 MAL 角色ID，
     * 因此新数据以本字段判断是否已存在。
     */
    Character findByAnilistId(@Param("anilistId") Integer anilistId);
    
    /**
     * 根据名称查询角色
     */
    Character findByName(@Param("name") String name);
    
    /**
     * 批量插入角色
     */
    int batchInsert(@Param("list") List<Character> characters);
    
    /**
     * 分页查询角色列表（支持名称模糊搜索）
     * @param name 角色名称（可选，支持模糊匹配）
     * @param userId 用户ID（可选，用于查询喜欢状态）
     * @return 角色列表
     */
    List<Character> findCharactersPage(@Param("name") String name, @Param("userId") Long userId);
    
    /**
     * 根据ID查询角色详情
     * @param characterId 角色ID
     * @return 角色详情VO中的CharacterInfo对象
     */
    com.anime.manager.vo.CharacterDetailVO.CharacterInfo findCharacterDetailById(@Param("characterId") Long characterId);
    
    /**
     * 分页查询用户喜欢角色历史（只返回favorite_status=1的记录）
     * @param userId 用户ID
     * @param name 角色名称（可选，支持模糊匹配）
     * @return 角色列表（包含喜欢状态）
     */
    List<Character> findUserFavoriteCharacterHistory(@Param("userId") Long userId, @Param("name") String name);
}
