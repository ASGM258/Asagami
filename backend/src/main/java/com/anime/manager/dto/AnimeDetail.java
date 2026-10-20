package com.anime.manager.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 动漫详情（数据源无关）
 *
 * <p>由 {@code AnimeDetailSource} 的各实现返回，字段已归一化，
 * 上层服务据此填充 {@code Anime} 实体。
 *
 * @param malId       MyAnimeList 动漫ID
 * @param titleJp     日文标题
 * @param englishTitle 英文标题（可能为 null；调用方用于填充 title）
 * @param coverImage  封面图链接
 * @param synopsis    简介（已去除 HTML 标签）
 * @param episodes    总集数（可能为 null）
 * @param status      状态：0=连载中，1=已完结
 * @param releaseDate 开播日期（可能为 null）
 * @param genres      类型标签
 * @param rating      评分，统一为 10 分制
 */
public record AnimeDetail(
        Integer malId,
        String titleJp,
        String englishTitle,
        String coverImage,
        String synopsis,
        Integer episodes,
        Integer status,
        LocalDate releaseDate,
        List<String> genres,
        BigDecimal rating
) {
}
