package com.anime.manager.common;

/**
 * Redis缓存键常量类
 */
public class CacheKeyConstants {

    /**
     * 缓存键前缀
     */
    private static final String PREFIX = "anime:manager:";

    // ==================== 动漫相关缓存 ====================

    /**
     * 动漫分页列表缓存
     * 格式：anime:manager:anime:page:{pageNum}:{pageSize}:{title}:{year}
     */
    public static final String ANIME_PAGE = PREFIX + "anime:page:%d:%d:%s:%d";

    /**
     * 动漫详情缓存
     * 格式：anime:manager:anime:detail:{animeId}
     */
    public static final String ANIME_DETAIL = PREFIX + "anime:detail:%d";

    /**
     * 动漫详情缓存（包含用户观看状态）
     * 格式：anime:manager:anime:detail:user:{animeId}:{userId}
     */
    public static final String ANIME_DETAIL_WITH_USER = PREFIX + "anime:detail:user:%d:%d";

    /**
     * 用户追番历史缓存
     * 格式：anime:manager:user:history:{userId}:{pageNum}:{pageSize}:{title}:{year}
     */
    public static final String USER_WATCH_HISTORY = PREFIX + "user:history:%d:%d:%d:%s:%d";

    /**
     * 用户喜欢角色历史缓存
     * 格式：anime:manager:user:favorite-character:{userId}:{pageNum}:{pageSize}:{name}
     */
    public static final String USER_FAVORITE_CHARACTER_HISTORY = PREFIX + "user:favorite-character:%d:%d:%d:%s";

    // ==================== 轮播图相关缓存 ====================

    /**
     * 轮播图缓存
     * 格式：anime:manager:banner:{limit}
     */
    public static final String BANNER = PREFIX + "banner:%d";

    // ==================== 评论相关缓存 ====================

    /**
     * 动漫评论列表缓存
     * 格式：anime:manager:comment:anime:{animeId}
     */
    public static final String COMMENT_ANIME = PREFIX + "comment:anime:%d";

    /**
     * 评论回复列表缓存
     * 格式：anime:manager:comment:reply:{commentId}
     */
    public static final String COMMENT_REPLY = PREFIX + "comment:reply:%d";

    /**
     * 用户点赞状态缓存
     * 格式：anime:manager:like:{userId}:{targetType}:{targetId}
     */
    public static final String USER_LIKE_STATUS = PREFIX + "like:%d:%s:%d";

    // ==================== 其他工具方法 ====================

    /**
     * 生成通配符模式，用于批量删除
     * 例如：anime:manager:anime:page:*
     */
    public static String pattern(String prefix) {
        return prefix + "*";
    }

    /**
     * 生成用户追番历史的通配符模式
     * @param userId 用户ID
     * @return 通配符模式，例如：anime:manager:user:history:123:*
     */
    public static String userHistoryPattern(Long userId) {
        return PREFIX + "user:history:" + userId + ":*";
    }

    /**
     * 生成用户喜欢角色历史的通配符模式
     * @param userId 用户ID
     * @return 通配符模式，例如：anime:manager:user:favorite-character:123:*
     */
    public static String userFavoriteCharacterPattern(Long userId) {
        return PREFIX + "user:favorite-character:" + userId + ":*";
    }

    /**
     * 生成动漫分页的通配符模式
     * @return 通配符模式，例如：anime:manager:anime:page:*
     */
    public static String animePagePattern() {
        return PREFIX + "anime:page:*";
    }

    /**
     * 生成轮播图的通配符模式
     * @return 通配符模式，例如：anime:manager:banner:*
     */
    public static String bannerPattern() {
        return PREFIX + "banner:*";
    }
}
