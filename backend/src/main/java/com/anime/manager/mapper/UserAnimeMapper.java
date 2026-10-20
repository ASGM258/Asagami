package com.anime.manager.mapper;

import com.anime.manager.entity.UserAnime;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 用户追番记录Mapper接口
 */
@Mapper
public interface UserAnimeMapper {
    
    /**
     * 根据用户ID和动漫ID查询追番记录
     * 
     * @param userId 用户ID
     * @param animeId 动漫ID
     * @return 追番记录，不存在则返回null
     */
    UserAnime findByUserIdAndAnimeId(@Param("userId") Long userId, @Param("animeId") Long animeId);
    
    /**
     * 插入追番记录
     * 
     * @param userAnime 追番记录
     * @return 影响行数
     */
    int insert(UserAnime userAnime);
    
    /**
     * 更新追番记录（动态SQL）
     * 只更新非null字段
     * 
     * @param userAnime 追番记录
     * @return 影响行数
     */
    int updateSelective(UserAnime userAnime);
}
