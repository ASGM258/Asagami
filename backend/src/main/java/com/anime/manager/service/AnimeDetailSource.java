package com.anime.manager.service;

import com.anime.manager.dto.AnimeDetail;

/**
 * 动漫详情数据源抽象
 *
 * <p>以 MAL ID 为输入获取动漫详情。原先该逻辑直接写死在
 * {@code AnimeScraperServiceImpl} 中并绑定 Jikan API；Jikan 不可用后
 * 抽出本接口，便于替换数据源。
 *
 * <p>当前实现：{@code AniListAnimeDetailSource}（AniList GraphQL 支持
 * {@code Media(idMal: Int)} 查询，因此仍以 MAL ID 为入口）。
 */
public interface AnimeDetailSource {

    /**
     * 数据源名称（日志用）
     */
    String sourceName();

    /**
     * 按 MAL ID 获取动漫详情
     *
     * @param malId MyAnimeList 动漫ID
     * @return 详情
     * @throws AnimeNotFoundException 该 MAL ID 不存在
     */
    AnimeDetail fetchByMalId(Integer malId);

    /**
     * 数据源中不存在该动漫
     */
    class AnimeNotFoundException extends RuntimeException {
        public AnimeNotFoundException(String message) {
            super(message);
        }
    }
}
