package com.anime.manager.dto;

import java.util.List;

/**
 * 角色详情（数据源无关）
 *
 * <p>由 {@code CharacterDetailSource} 的各实现返回，字段已归一化。
 *
 * <p>注意：当前数据源（AniList）**不提供 MAL 角色ID**，因此本 DTO 不包含
 * malId 字段，唯一标识为 anilistId。
 *
 * @param anilistId AniList 角色ID（唯一标识）
 * @param name      角色名（罗马音/英文，如 "Satoru Gojou"）
 * @param nameJp    角色名（日文，如 "五条悟"）
 * @param imageUrl  头像链接
 * @param about     简介（已去除 HTML 标记与实体）
 * @param nicknames 别名列表
 * @param birthday  生日，格式 MM-DD（可能为 null）
 * @param favorites 收藏数（受欢迎程度）
 */
public record CharacterDetail(
        Integer anilistId,
        String name,
        String nameJp,
        String imageUrl,
        String about,
        List<String> nicknames,
        String birthday,
        Integer favorites
) {
}
