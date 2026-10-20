package com.anime.manager.dto;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.math.BigDecimal;

/**
 * 动漫简单信息DTO（用于列表展示）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnimeSimpleDTO {
    
    /**
     * 动漫ID
     */
    private Long id;
    
    /**
     * 中文标题
     */
    private String title;
    
    /**
     * 封面图URL
     */
    private String coverImage;
    
    /**
     * 总集数
     */
    private Integer episodes;
    
    /**
     * 评分
     */
    private BigDecimal rating;
    
    /**
     * 发布年份
     */
    private Integer releaseYear;
    
    /**
     * 观看状态
     * 0-未开始, 1-观看中, 2-已完成, 3-已放弃
     * 如果该用户在user_anime表中不存在记录，则返回0
     */
    @Builder.Default
    private Integer watchStatus = 0;
}
