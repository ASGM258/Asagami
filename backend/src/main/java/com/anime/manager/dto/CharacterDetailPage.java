package com.anime.manager.dto;

import java.util.List;

/**
 * 角色分页结果（数据源无关）
 *
 * @param items       当前页角色
 * @param currentPage 当前页码（从 1 开始）
 * @param lastPage    最后一页页码
 * @param hasNextPage 是否还有下一页
 */
public record CharacterDetailPage(
        List<CharacterDetail> items,
        int currentPage,
        int lastPage,
        boolean hasNextPage
) {

    /** 空结果 */
    public static CharacterDetailPage empty() {
        return new CharacterDetailPage(List.of(), 1, 1, false);
    }
}
