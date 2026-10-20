package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;

/**
 * 番剧更新排期实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnimeSchedule {
    
    /**
     * 排期记录ID
     */
    private Integer id;
    
    /**
     * 关联番剧主表ID(对应anime表的id)
     */
    private Long mainId;
    
    /**
     * 番剧名称(日文标题)
     */
    private String title;
    
    /**
     * 封面链接
     */
    private String coverImage;
    
    /**
     * 评分
     */
    private BigDecimal rating;
    
    /**
     * 总集数
     */
    private Integer episodes;
    
    /**
     * 状态 0=连载中 1=完结
     */
    private Integer status;
    
    /**
     * 更新星期 1=周一~7=周日, null=未知/待定
     */
    private Integer dayOfWeek;
    
    /**
     * 更新时间文字描述
     */
    private String updateTime;
}
