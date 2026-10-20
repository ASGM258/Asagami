package com.anime.manager.dto;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;
import java.util.List;

/**
 * 轮播图数据DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BannerItem {
    
    /**
     * 动漫ID
     */
    private Long animeId;
    
    /**
     * 标题
     */
    private String title;
    
    /**
     * 封面图URL
     */
    private String coverImage;
    
    /**
     * 简介
     */
    private String synopsis;
    
    /**
     * 评分
     */
    private BigDecimal rating;
    
    /**
     * 状态: 0-连载中, 1-已完结
     */
    private Integer status;
    
    /**
     * 观看次数（可选）
     */
    private Integer views;
    
    /**
     * 题材标签（可选）
     */
    private List<String> genres;
}
