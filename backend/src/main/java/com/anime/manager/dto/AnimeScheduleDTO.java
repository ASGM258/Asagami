package com.anime.manager.dto;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;

/**
 * 番剧排期前端返回DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnimeScheduleDTO {
    
    /**
     * 动漫ID(对应anime表的id)
     */
    private Long id;
    
    /**
     * 主番剧ID(如果为空则返回null)
     */
    private Long mainId;
    
    /**
     * 标题(日文标题)
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
     * 更新星期 0=周一~6=周六
     */
    private Integer dayOfWeek;
    
    /**
     * 更新时间文字描述
     */
    private String updateTime;
}
