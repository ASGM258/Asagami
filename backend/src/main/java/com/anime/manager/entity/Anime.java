package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 动漫基本信息实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Anime {
    
    /**
     * 动漫ID
     */
    private Long id;
    
    /**
     * 动漫标题
     */
    private String title;
    
    /**
     * 日文标题
     */
    private String titleJp;
    
    /**
     * 封面图URL
     */
    private String coverImage;
    
    /**
     * 简介
     */
    private String synopsis;
    
    /**
     * 总集数
     */
    private Integer episodes;
    
    /**
     * 状态: 0-连载中, 1-已完结
     */
    private Integer status;
    
    /**
     * 发布日期
     */
    private LocalDate releaseDate;
    
    /**
     * 类型标签(逗号分隔)
     */
    private String genres;
    
    /**
     * 评分
     */
    private BigDecimal rating;
    
    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
    
    /**
     * 更新时间
     */
    private LocalDateTime updatedAt;
}
