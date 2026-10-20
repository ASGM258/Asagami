package com.anime.manager.mapper;

import com.anime.manager.dto.AnimeSimpleDTO;
import com.anime.manager.entity.Anime;
import org.apache.ibatis.annotations.*;

import java.util.List;

/**
 * 动漫Mapper接口
 */
@Mapper
public interface AnimeMapper {
    
    /**
     * 根据ID查询动漫
     */
    @Select("SELECT * FROM anime WHERE id = #{id}")
    Anime findById(Long id);
    
    /**
     * 根据标题查询动漫
     */
    @Select("SELECT * FROM anime WHERE title = #{title}")
    Anime findByTitle(String title);
    
    /**
     * 插入动漫
     */
    @Insert("INSERT INTO anime(title, title_jp, cover_image, synopsis, episodes, status, release_date, genres, rating, created_at, updated_at) " +
            "VALUES(#{title}, #{titleJp}, #{coverImage}, #{synopsis}, #{episodes}, #{status}, #{releaseDate}, #{genres}, #{rating}, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(Anime anime);
    
    /**
     * 更新动漫信息
     */
    @Update("UPDATE anime SET title = #{title}, title_jp = #{titleJp}, cover_image = #{coverImage}, " +
            "synopsis = #{synopsis}, episodes = #{episodes}, status = #{status}, release_date = #{releaseDate}, " +
            "genres = #{genres}, rating = #{rating}, updated_at = NOW() WHERE id = #{id}")
    int update(Anime anime);
    
    /**
     * 删除动漫
     */
    @Delete("DELETE FROM anime WHERE id = #{id}")
    int deleteById(Long id);
    
    /**
     * 分页查询动漫简单信息（联表查询中文名称和观看状态）
     * 
     * @param title 标题搜索关键词（可选）
     * @param year 年份过滤（可选）
     * @param userId 用户ID
     * @return 动漫简单信息列表
     */
    List<AnimeSimpleDTO> findAnimePageWithChineseName(@Param("title") String title, @Param("year") Integer year, @Param("userId") Long userId);
    
    /**
     * 分页查询用户追番历史（只返回user_anime表中存在的记录）
     * 
     * @param userId 用户ID
     * @param title 标题搜索关键词（可选）
     * @param year 年份过滤（可选）
     * @return 动漫简单信息列表
     */
    List<AnimeSimpleDTO> findUserWatchHistory(@Param("userId") Long userId, @Param("title") String title, @Param("year") Integer year);
    
    /**
     * 查询动漫详情（联表查询中文名称和用户观看状态）
     * 
     * @param animeId 动漫ID
     * @param userId 用户ID（可选，用于查询观看状态）
     * @return 动漫详情VO中的动画信息部分
     */
    com.anime.manager.vo.AnimeDetailVO.AnimeInfo findAnimeDetailById(@Param("animeId") Long animeId, @Param("userId") Long userId);
    
    /**
     * 根据日文标题精确匹配查询动漫
     * 
     * @param titleJp 日文标题
     * @return 动漫实体
     */
    @Select("SELECT * FROM anime WHERE title_jp = #{titleJp}")
    Anime findByTitleJp(String titleJp);
    
    /**
     * 标题前缀匹配查询动漫（双向校验，避免误配续作）
     *
     * <p>用于「季数/续作后缀」场景：数据源返回的是《作品 第3期》这类标题，
     * 而 anime 表中存的是基础标题《作品》。双向条件保证 anime 中的标题确实
     * 是查询词的前缀，不会把续作错配到第一季。
     *
     * <p>两侧均使用参数绑定，不做字符串拼接。
     *
     * @param keyword 候选标题（已剥离季数后缀）
     * @return 命中的动漫实体，未命中返回 null
     */
    @Select("SELECT * FROM anime WHERE title_jp LIKE CONCAT(#{keyword}, '%') "
            + "AND #{keyword} LIKE CONCAT(title_jp, '%') LIMIT 1")
    Anime findPrefixByTitleJp(@Param("keyword") String keyword);
    
    /**
     * 中文/普通标题前缀匹配（语义同上）
     *
     * @param keyword 候选标题
     * @return 命中的动漫实体，未命中返回 null
     */
    @Select("SELECT * FROM anime WHERE title LIKE CONCAT(#{keyword}, '%') "
            + "AND #{keyword} LIKE CONCAT(title, '%') LIMIT 1")
    Anime findPrefixByTitle(@Param("keyword") String keyword);
}
