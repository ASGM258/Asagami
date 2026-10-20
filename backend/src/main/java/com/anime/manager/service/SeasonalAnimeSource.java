package com.anime.manager.service;

import com.anime.manager.dto.SeasonalAnimePage;

/**
 * 当季新番数据源抽象
 *
 * <p>把「从哪里取当季新番」与「如何入库」解耦。原先该逻辑直接写死在
 * {@code SeasonalScraperServiceImpl} 里并绑定了 Jikan API；Jikan 不可用后
 * 需要切换数据源，抽象出本接口后只需新增一个实现类即可替换。
 *
 * <p>当前实现：{@code AniListSeasonalAnimeSource}（AniList GraphQL，
 * 免费且无需密钥，响应中带 idMal 即 MAL ID）。
 */
public interface SeasonalAnimeSource {

    /**
     * 数据源名称（日志用）
     */
    String sourceName();

    /**
     * 抓取指定页的当季新番
     *
     * @param page 页码（从 1 开始）
     * @return 分页结果；请求失败时应抛出异常由调用方记录
     */
    SeasonalAnimePage fetchPage(int page);
}
