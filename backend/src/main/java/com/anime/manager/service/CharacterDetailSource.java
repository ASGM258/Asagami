package com.anime.manager.service;

import com.anime.manager.dto.CharacterDetail;
import com.anime.manager.dto.CharacterDetailPage;

/**
 * 角色详情数据源抽象
 *
 * <p>原先角色抓取直接绑定 Jikan API（{@code api.jikan.moe}），该服务已不可用。
 * 抽出本接口后，数据源可替换。
 *
 * <p>当前实现：{@code AniListCharacterSource}。
 *
 * <p>⚠️ 与动漫不同，AniList 的角色对象**没有 MAL ID**，因此本接口以
 * AniList 角色ID为标识，不再接受 MAL ID。原 Jikan 时代的
 * {@code mal_id} 列仅保留历史数据语义。
 */
public interface CharacterDetailSource {

    /**
     * 数据源名称（日志用）
     */
    String sourceName();

    /**
     * 分页抓取角色（按收藏数倒序，即热门优先）
     *
     * @param page 页码（从 1 开始）
     * @return 分页结果
     */
    CharacterDetailPage fetchPage(int page);

    /**
     * 按 AniList 角色ID获取单个角色详情
     *
     * @param anilistId AniList 角色ID
     * @return 角色详情
     * @throws CharacterNotFoundException 该角色不存在
     */
    CharacterDetail fetchById(Integer anilistId);

    /**
     * 数据源中不存在该角色
     */
    class CharacterNotFoundException extends RuntimeException {
        public CharacterNotFoundException(String message) {
            super(message);
        }
    }
}
