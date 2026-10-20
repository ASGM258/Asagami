package com.anime.manager.service.impl;

import com.anime.manager.common.CacheKeyConstants;
import com.anime.manager.dto.AnimeDetail;
import com.anime.manager.entity.Anime;
import com.anime.manager.mapper.AnimeMapper;
import com.anime.manager.service.AnimeDetailSource;
import com.anime.manager.service.AnimeScraperService;
import com.anime.manager.service.CacheService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * 动漫数据抓取服务实现类
 *
 * <p>数据来源已从 Jikan API 切换为可插拔的 {@link AnimeDetailSource}，
 * 当前默认实现为 AniList（见 {@code AniListAnimeDetailSource}）。
 * 入参仍为 MAL ID，调用方无需改动。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AnimeScraperServiceImpl implements AnimeScraperService {

    private final AnimeMapper animeMapper;
    private final CacheService cacheService;
    private final AnimeDetailSource animeDetailSource;

    /**
     * 根据 MAL ID 抓取动漫信息并保存到数据库
     */
    @Override
    public Long fetchAndSaveAnime(Integer malId) {
        log.info("开始抓取动漫信息: malId={}, 数据源={}", malId, animeDetailSource.sourceName());

        try {
            AnimeDetail detail = animeDetailSource.fetchByMalId(malId);
            Anime anime = toEntity(detail);

            // 先按日文标题去重（与本项目其他链路保持一致），再退回普通标题
            Anime existing = null;
            if (anime.getTitleJp() != null) {
                existing = animeMapper.findByTitleJp(anime.getTitleJp());
            }
            if (existing == null && anime.getTitle() != null) {
                existing = animeMapper.findByTitle(anime.getTitle());
            }
            if (existing != null) {
                log.info("动漫已存在，跳过保存: id={}, title={}", existing.getId(), existing.getTitle());
                return existing.getId();
            }

            animeMapper.insert(anime);
            log.info("动漫信息保存成功: id={}, title={}", anime.getId(), anime.getTitle());

            clearAnimeCache(anime.getId());
            return anime.getId();

        } catch (AnimeDetailSource.AnimeNotFoundException e) {
            // 资源不存在，交由调用方按 404 处理（异步补抓据此不重试）
            log.warn("动漫不存在: malId={}", malId);
            throw new RuntimeException(e.getMessage(), e);

        } catch (IllegalArgumentException e) {
            log.error("参数错误: malId={}, error={}", malId, e.getMessage());
            throw e;

        } catch (Exception e) {
            log.error("抓取动漫信息失败: malId={}, error={}", malId, e.getMessage(), e);
            throw new RuntimeException("抓取动漫信息失败: " + e.getMessage(), e);
        }
    }

    /**
     * 归一化详情 → 实体
     *
     * <p>title 字段存英文标题（中文标题由翻译脚本回填），
     * 无英文标题时退化为日文标题，避免 title 为空导致 NOT NULL 约束失败。
     */
    private Anime toEntity(AnimeDetail detail) {
        String title = detail.englishTitle() != null ? detail.englishTitle() : detail.titleJp();

        return Anime.builder()
                .title(title)
                .titleJp(detail.titleJp())
                .coverImage(detail.coverImage())
                .synopsis(detail.synopsis())
                .episodes(detail.episodes())
                .status(detail.status())
                .releaseDate(detail.releaseDate())
                .genres(detail.genres() == null || detail.genres().isEmpty()
                        ? null : String.join(",", detail.genres()))
                .rating(detail.rating() != null ? detail.rating() : BigDecimal.ZERO)
                .build();
    }

    /**
     * 清除动漫相关缓存
     */
    private void clearAnimeCache(Long animeId) {
        cacheService.delete(String.format(CacheKeyConstants.ANIME_DETAIL, animeId));
        cacheService.deleteByPattern(CacheKeyConstants.animePagePattern());
        log.info("已清除动漫{}的相关缓存", animeId);
    }
}
