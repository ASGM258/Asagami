package com.anime.manager.service.impl;

import com.anime.manager.dto.CharacterDetail;
import com.anime.manager.dto.CharacterDetailPage;
import com.anime.manager.entity.Character;
import com.anime.manager.mapper.CharacterMapper;
import com.anime.manager.service.CharacterDetailSource;
import com.anime.manager.service.CharacterScraperService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 角色爬虫服务实现类
 *
 * <p>数据来源已从 Jikan API 切换为可插拔的 {@link CharacterDetailSource}，
 * 当前默认实现为 AniList（见 {@code AniListCharacterSource}）。
 *
 * <p>相比原实现的两点改进：
 * <ol>
 *   <li>AniList 的角色列表接口直接返回完整字段（简介/生日/别名/收藏数），
 *       不再需要「先取列表页、再逐个请求详情」——原实现每个角色间隔 3 秒，
 *       抓 50 个角色就要 2.5 分钟以上</li>
 *   <li>去重键改为 AniList 角色ID（写入 anilist_id 列）。AniList 不提供
 *       MAL 角色ID，因此 mal_id 列在新数据下为空，仅保留历史数据语义</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CharacterScraperServiceImpl implements CharacterScraperService {

    private final CharacterMapper characterMapper;
    private final CharacterDetailSource characterDetailSource;

    /** 分页之间的间隔，避免给数据源造成压力 */
    private static final long PAGE_INTERVAL_MS = 500L;

    /** 安全阀：最大抓取页数，防止分页异常导致死循环 */
    private static final int MAX_PAGES = 200;

    /** 分批入库的批大小 */
    private static final int BATCH_SIZE = 100;

    /**
     * 抓取角色并保存到数据库
     *
     * @param maxPages 最大抓取页数（null 表示不额外限制，只受安全阀约束）
     */
    @Override
    public Integer fetchAndSaveAllCharacters(Integer maxPages) {
        log.info("开始抓取角色信息, 数据源={}, 最大页数={}", characterDetailSource.sourceName(), maxPages);

        try {
            int pageLimit = maxPages != null && maxPages > 0 ? Math.min(maxPages, MAX_PAGES) : MAX_PAGES;

            // 按 AniList 角色ID去重（LinkedHashMap 保序）
            Map<Integer, CharacterDetail> uniqueCharacters = new LinkedHashMap<>();
            int failCount = 0;

            int currentPage = 1;
            boolean hasNext = true;

            while (hasNext && currentPage <= pageLimit) {
                try {
                    CharacterDetailPage pageResult = characterDetailSource.fetchPage(currentPage);

                    for (CharacterDetail detail : pageResult.items()) {
                        if (detail.anilistId() != null) {
                            uniqueCharacters.putIfAbsent(detail.anilistId(), detail);
                        }
                    }

                    log.info("已处理第 {}/{} 页, 累计唯一角色 {} 个",
                            pageResult.currentPage(), pageResult.lastPage(), uniqueCharacters.size());

                    hasNext = pageResult.hasNextPage();
                    currentPage++;

                    if (hasNext) {
                        Thread.sleep(PAGE_INTERVAL_MS);
                    }

                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    log.warn("角色抓取被中断，返回已获取的 {} 个角色", uniqueCharacters.size());
                    break;
                } catch (Exception e) {
                    log.error("抓取第 {} 页角色失败: {}", currentPage, e.getMessage());
                    failCount++;
                    currentPage++;
                }
            }

            if (hasNext && currentPage > pageLimit) {
                log.info("已达到页数限制 {}，提前结束抓取", pageLimit);
            }

            log.info("角色列表抓取完成，共 {} 个唯一角色", uniqueCharacters.size());

            if (uniqueCharacters.isEmpty()) {
                log.warn("未获取到任何角色，本次不做任何写入");
                return 0;
            }

            // 过滤掉库中已存在的角色（按 anilist_id 去重）
            List<Character> toInsert = new ArrayList<>();
            int skipCount = 0;
            for (CharacterDetail detail : uniqueCharacters.values()) {
                if (characterMapper.findByAnilistId(detail.anilistId()) != null) {
                    skipCount++;
                    continue;
                }
                toInsert.add(toEntity(detail));
            }

            log.info("待入库 {} 个, 库中已存在 {} 个", toInsert.size(), skipCount);

            int inserted = batchInsert(toInsert, failCount);
            log.info("角色抓取完成: 入库={}, 跳过={}, 页面失败={}", inserted, skipCount, failCount);
            return inserted;

        } catch (Exception e) {
            log.error("抓取角色信息失败: {}", e.getMessage(), e);
            throw new RuntimeException("抓取角色信息失败: " + e.getMessage(), e);
        }
    }

    /**
     * 按 AniList 角色ID抓取单个角色并保存
     *
     * <p>注意：参数已从 MAL 角色ID改为 **AniList 角色ID**（AniList 不提供 MAL ID）。
     */
    @Override
    public Long fetchAndSaveCharacter(Integer anilistId) {
        log.info("开始抓取角色信息: anilistId={}, 数据源={}", anilistId, characterDetailSource.sourceName());

        try {
            Character existing = characterMapper.findByAnilistId(anilistId);
            if (existing != null) {
                log.info("角色已存在，跳过保存: anilistId={}, name={}", anilistId, existing.getName());
                return existing.getId();
            }

            CharacterDetail detail = characterDetailSource.fetchById(anilistId);
            Character character = toEntity(detail);

            characterMapper.insert(character);
            log.info("角色信息保存成功: id={}, name={}", character.getId(), character.getName());
            return character.getId();

        } catch (CharacterDetailSource.CharacterNotFoundException e) {
            log.warn("角色不存在: anilistId={}", anilistId);
            throw new RuntimeException(e.getMessage(), e);

        } catch (IllegalArgumentException e) {
            log.error("参数错误: anilistId={}, error={}", anilistId, e.getMessage());
            throw e;

        } catch (Exception e) {
            log.error("抓取角色信息失败: anilistId={}, error={}", anilistId, e.getMessage(), e);
            throw new RuntimeException("抓取角色信息失败: " + e.getMessage(), e);
        }
    }

    /**
     * 归一化详情 → 实体
     */
    private Character toEntity(CharacterDetail detail) {
        return Character.builder()
                // AniList 数据没有 MAL 角色ID，mal_id 留空（该列已改为可空）
                .malId(null)
                .anilistId(detail.anilistId())
                .name(detail.name())
                .nameJp(detail.nameJp())
                .imageUrl(detail.imageUrl())
                .about(detail.about())
                .nicknames(detail.nicknames() == null || detail.nicknames().isEmpty()
                        ? null : String.join(",", detail.nicknames()))
                .birthday(detail.birthday())
                .favorites(detail.favorites() != null ? detail.favorites() : 0)
                .build();
    }

    /**
     * 分批入库，批量失败时降级为逐条插入
     *
     * @return 成功入库条数
     */
    private int batchInsert(List<Character> characters, int failCountSeed) {
        int inserted = 0;
        int failCount = failCountSeed;

        for (int i = 0; i < characters.size(); i += BATCH_SIZE) {
            int end = Math.min(i + BATCH_SIZE, characters.size());
            List<Character> batch = characters.subList(i, end);

            try {
                characterMapper.batchInsert(batch);
                inserted += batch.size();
                log.info("批量插入成功: {}/{}", end, characters.size());
            } catch (Exception e) {
                log.error("批量插入失败，降级为逐条插入: {}", e.getMessage());
                for (Character character : batch) {
                    try {
                        // 逐条前再查一次，避免批量失败后重复插入
                        if (characterMapper.findByAnilistId(character.getAnilistId()) == null) {
                            characterMapper.insert(character);
                            inserted++;
                        }
                    } catch (Exception ex) {
                        log.error("插入角色失败: anilistId={}, error={}",
                                character.getAnilistId(), ex.getMessage());
                        failCount++;
                    }
                }
            }
        }

        if (failCount > 0) {
            log.warn("本次共 {} 条记录处理失败", failCount);
        }
        return inserted;
    }
}
