package com.anime.manager.dto;

import java.util.List;

/**
 * 当季新番分页结果（数据源无关）
 *
 * @param items       当前页条目
 * @param currentPage 当前页码（从 1 开始）
 * @param lastPage    最后一页页码
 * @param hasNextPage 是否还有下一页
 * @param total       总条数（数据源未提供时为 -1）
 */
public record SeasonalAnimePage(
        List<SeasonalAnimeItem> items,
        int currentPage,
        int lastPage,
        boolean hasNextPage,
        int total
) {

    /** 空结果 */
    public static SeasonalAnimePage empty() {
        return new SeasonalAnimePage(List.of(), 1, 1, false, 0);
    }
}
