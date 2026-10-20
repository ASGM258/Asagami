package com.anime.manager.dto;

import java.math.BigDecimal;

/**
 * 当季新番条目（数据源无关）
 *
 * <p>由 {@code SeasonalAnimeSource} 的各实现返回，已经完成字段归一化，
 * 使上层服务不必关心具体数据源的 JSON 结构差异。
 *
 * @param malId      MyAnimeList 动漫ID（用于补齐 anime 表记录；可能为 null）
 * @param title      标题，优先日文原名
 * @param coverImage 封面图链接
 * @param rating     评分，统一为 10 分制（对应 anime_schedule.rating decimal(3,1)）
 * @param episodes   总集数
 * @param status     状态：0=连载中，1=完结
 * @param dayOfWeek  更新星期：1=周一~7=周日，null=待定
 * @param updateTime 更新时间文字描述，如"周三23:00更新"
 */
public record SeasonalAnimeItem(
        Integer malId,
        String title,
        String coverImage,
        BigDecimal rating,
        Integer episodes,
        Integer status,
        Integer dayOfWeek,
        String updateTime
) {
}
