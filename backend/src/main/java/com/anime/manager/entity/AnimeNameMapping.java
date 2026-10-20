package com.anime.manager.entity;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;
import lombok.Builder;

import java.time.LocalDateTime;

/**
 * 动漫中文名称映射实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnimeNameMapping {

    /**
     * 主键ID
     */
    private Long id;

    /**
     * 关联动漫ID
     */
    private Long animeId;

    /**
     * 中文名称
     */
    private String chineseName;

    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
}
