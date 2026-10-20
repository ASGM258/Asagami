package com.anime.manager.mapper;

import com.anime.manager.entity.AnimeNameMapping;
import org.apache.ibatis.annotations.*;

import java.util.List;

/**
 * 动漫名称映射Mapper接口
 */
@Mapper
public interface AnimeNameMappingMapper {

    /**
     * 根据动漫ID查询中文名称映射
     */
    @Select("SELECT * FROM anime_name_mapping WHERE anime_id = #{animeId}")
    AnimeNameMapping findByAnimeId(Long animeId);

    /**
     * 根据中文名称查询映射
     */
    @Select("SELECT * FROM anime_name_mapping WHERE chinese_name = #{chineseName}")
    AnimeNameMapping findByChineseName(String chineseName);

    /**
     * 查询所有名称映射
     */
    @Select("SELECT * FROM anime_name_mapping ORDER BY created_at DESC")
    List<AnimeNameMapping> findAll();

    /**
     * 插入名称映射（重复则更新）
     */
    @Insert("INSERT INTO anime_name_mapping(anime_id, chinese_name, created_at) " +
            "VALUES(#{animeId}, #{chineseName}, NOW()) " +
            "ON DUPLICATE KEY UPDATE chinese_name = #{chineseName}")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insertOrUpdate(AnimeNameMapping mapping);

    /**
     * 根据动漫ID删除映射
     */
    @Delete("DELETE FROM anime_name_mapping WHERE anime_id = #{animeId}")
    int deleteByAnimeId(Long animeId);
}
