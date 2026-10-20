package com.anime.manager.mapper;

import com.anime.manager.dto.AnimeScheduleDTO;
import com.anime.manager.dto.BannerItem;
import com.anime.manager.entity.AnimeSchedule;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 番剧排期Mapper接口
 */
@Mapper
public interface AnimeScheduleMapper {
    
    /**
     * 根据ID查询排期记录
     */
    AnimeSchedule findById(Integer id);
    
    /**
     * 根据星期几查询当天更新的动漫列表
     */
    List<AnimeSchedule> findByDayOfWeek(Integer dayOfWeek);
    
    /**
     * 查询所有排期记录
     */
    List<AnimeSchedule> findAll();
    
    /**
     * 根据日文标题查询排期记录
     */
    AnimeSchedule findByTitle(String title);
    
    /**
     * 插入排期记录
     */
    int insert(AnimeSchedule schedule);
    
    /**
     * 批量插入排期记录
     */
    int batchInsert(@Param("list") List<AnimeSchedule> list);
    
    /**
     * 更新排期记录（只更新非空字段）
     */
    int update(AnimeSchedule schedule);
    
    /**
     * 删除排期记录
     */
    int deleteById(Integer id);
    
    /**
     * 清空所有排期数据
     */
    void clearAll();
    
    /**
     * 根据星期几查询排期记录（返回DTO，包含anime表的id）
     */
    List<AnimeScheduleDTO> findDTOByDayOfWeek(@Param("dayOfWeek") Integer dayOfWeek);
    
    /**
     * 随机获取指定数量的轮播图数据
     * @param limit 数量限制
     * @return 轮播图列表
     */
    List<BannerItem> findRandomBanners(@Param("limit") Integer limit);
}
