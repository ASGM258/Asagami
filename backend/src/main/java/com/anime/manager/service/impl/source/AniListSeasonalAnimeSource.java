package com.anime.manager.service.impl.source;

import com.anime.manager.dto.SeasonalAnimeItem;
import com.anime.manager.dto.SeasonalAnimePage;
import com.anime.manager.service.SeasonalAnimeSource;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * AniList GraphQL 当季新番数据源
 *
 * <p>为什么换成 AniList：
 * <ul>
 *   <li>原 Jikan API（api.jikan.moe）已不可用（连接超时）</li>
 *   <li>MyAnimeList 官方 API v2 需要申请 Client ID，且对多数账号已关闭新注册</li>
 *   <li>AniList 免费、无需密钥，且响应中带 <code>idMal</code> 字段 ——
 *       即 MyAnimeList 的动漫ID，可直接复用现有基于 MAL ID 的匹配与补抓逻辑</li>
 * </ul>
 *
 * <p>字段映射要点：
 * <ul>
 *   <li><code>idMal</code> → malId（缺失时该条无法补抓 anime 记录，但仍会入库展示）</li>
 *   <li><code>title.native</code> → title（日文原名，用于匹配 anime 表；缺失时退化为 romaji）</li>
 *   <li><code>averageScore</code> 为 0-100，需 ÷10 转成 10 分制（anime_schedule.rating 为 decimal(3,1)）</li>
 *   <li><code>nextAiringEpisode.airingAt</code> 为 Unix 秒，换算为星期几与 HH:mm（Asia/Shanghai）</li>
 * </ul>
 */
@Slf4j
@Component
public class AniListSeasonalAnimeSource implements SeasonalAnimeSource {

    /** AniList GraphQL 端点 */
    private static final String DEFAULT_API_URL = "https://graphql.anilist.co";

    /** 每页条数（AniList 上限 50） */
    private static final int DEFAULT_PER_PAGE = 50;

    /** AniList 对 perPage 的硬上限 */
    private static final int MAX_PER_PAGE = 50;

    /** 广播时间所在时区（与上游 Java 后端整体保持一致） */
    private static final ZoneId BROADCAST_ZONE = ZoneId.of("Asia/Shanghai");

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final String apiUrl;

    private final int pageSize;

    /**
     * 构造器注入，便于测试直接 new 出实例（字段注入无法在单测中赋值）
     */
    public AniListSeasonalAnimeSource(
            RestTemplate restTemplate,
            @Value("${scraper.seasonal.anilist-url:" + DEFAULT_API_URL + "}") String apiUrl,
            @Value("${scraper.seasonal.page-size:" + DEFAULT_PER_PAGE + "}") int pageSize) {
        this.restTemplate = restTemplate;
        this.apiUrl = apiUrl;
        this.pageSize = pageSize;
    }

    /**
     * 季度与年份作为变量传入，避免字符串拼接注入；
     * 同时取 nextAiringEpisode 用于推导更新星期与时间。
     */
    private static final String QUERY = """
            query ($page: Int, $perPage: Int, $season: MediaSeason, $seasonYear: Int) {
              Page(page: $page, perPage: $perPage) {
                pageInfo { total currentPage lastPage hasNextPage }
                media(
                  season: $season,
                  seasonYear: $seasonYear,
                  type: ANIME,
                  sort: POPULARITY_DESC
                ) {
                  id
                  idMal
                  title { native romaji english }
                  coverImage { extraLarge large medium }
                  averageScore
                  episodes
                  status
                  format
                  nextAiringEpisode { airingAt episode }
                }
              }
            }
            """;

    @Override
    public String sourceName() {
        return "AniList";
    }

    @Override
    public SeasonalAnimePage fetchPage(int page) {
        String season = currentSeason();
        int seasonYear = currentSeasonYear();

        int effectivePerPage = pageSize <= 0 ? DEFAULT_PER_PAGE : Math.min(pageSize, MAX_PER_PAGE);

        ObjectNode variables = objectMapper.createObjectNode();
        variables.put("page", Math.max(page, 1));
        variables.put("perPage", effectivePerPage);
        variables.put("season", season);
        variables.put("seasonYear", seasonYear);

        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("query", QUERY);
        payload.set("variables", variables);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));

        ResponseEntity<String> response = restTemplate.postForEntity(
                apiUrl, new HttpEntity<>(payload.toString(), headers), String.class);

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            throw new IllegalStateException("AniList 请求失败: " + response.getStatusCode());
        }

        try {
            JsonNode root = objectMapper.readTree(response.getBody());

            // GraphQL 层面错误（例如语法或配额问题）
            JsonNode errors = root.get("errors");
            if (errors != null && errors.isArray() && !errors.isEmpty()) {
                throw new IllegalStateException("AniList 返回错误: " + errors.toString());
            }

            JsonNode pageNode = root.path("data").path("Page");
            JsonNode pageInfo = pageNode.path("pageInfo");
            JsonNode mediaNodes = pageNode.path("media");

            if (mediaNodes.isMissingNode() || !mediaNodes.isArray()) {
                throw new IllegalStateException("AniList 返回数据格式错误: 缺少 Page.media");
            }

            List<SeasonalAnimeItem> items = new ArrayList<>(mediaNodes.size());
            for (JsonNode media : mediaNodes) {
                SeasonalAnimeItem item = mapMedia(media);
                if (item != null) {
                    items.add(item);
                }
            }

            int currentPage = pageInfo.path("currentPage").asInt(Math.max(page, 1));
            int lastPage = pageInfo.path("lastPage").asInt(currentPage);
            boolean hasNextPage = pageInfo.path("hasNextPage").asBoolean(false);
            int total = pageInfo.path("total").asInt(-1);

            log.info("AniList 抓取成功: season={}-{}, 第{}/{}页, 本页{}条, 总计{}条",
                    seasonYear, season, currentPage, lastPage, items.size(), total);

            return new SeasonalAnimePage(items, currentPage, lastPage, hasNextPage, total);

        } catch (IllegalStateException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("解析 AniList 响应失败: " + e.getMessage(), e);
        }
    }

    /**
     * 把 AniList 的单条 media 映射为归一化条目
     *
     * @return 条目；标题缺失时返回 null
     */
    private SeasonalAnimeItem mapMedia(JsonNode media) {
        // 标题：优先日文原名（用于匹配 anime.title_jp），其次罗马音
        String title = textOrNull(media.path("title").path("native"));
        if (title == null) {
            title = textOrNull(media.path("title").path("romaji"));
        }
        if (title == null || title.isBlank()) {
            log.warn("AniList 条目缺少标题，跳过: id={}", media.path("id").asInt());
            return null;
        }

        // MAL ID：字段名就是 idMal
        Integer malId = media.hasNonNull("idMal") ? media.get("idMal").asInt() : null;

        // 封面：优先最大尺寸
        String coverImage = firstNonBlank(
                textOrNull(media.path("coverImage").path("extraLarge")),
                textOrNull(media.path("coverImage").path("large")),
                textOrNull(media.path("coverImage").path("medium"))
        );

        // 评分：averageScore 为 0-100，转换为 10 分制并保留一位小数
        BigDecimal rating = BigDecimal.ZERO;
        if (media.hasNonNull("averageScore")) {
            rating = BigDecimal.valueOf(media.get("averageScore").asDouble())
                    .divide(BigDecimal.TEN, 1, RoundingMode.HALF_UP);
        }

        int episodes = media.hasNonNull("episodes") ? media.get("episodes").asInt() : 0;

        // 状态：FINISHED / CANCELLED 视为完结，其余（RELEASING / NOT_YET_RELEASED）视为连载中
        String status = media.path("status").asText("");
        int statusCode = ("FINISHED".equals(status) || "CANCELLED".equals(status)) ? 1 : 0;

        // 更新星期与时间：由下一次放送的 Unix 时间戳换算
        Integer dayOfWeek = null;
        String updateTime = "待定";
        JsonNode nextAiring = media.path("nextAiringEpisode");
        if (nextAiring != null && nextAiring.hasNonNull("airingAt")) {
            long airingAt = nextAiring.get("airingAt").asLong();
            ZonedDateTime airingTime = Instant.ofEpochSecond(airingAt).atZone(BROADCAST_ZONE);

            dayOfWeek = airingTime.getDayOfWeek().getValue();
            updateTime = getDayName(dayOfWeek)
                    + String.format("%02d:%02d", airingTime.getHour(), airingTime.getMinute())
                    + "后";
        }

        return new SeasonalAnimeItem(
                malId, title, coverImage, rating, Math.max(episodes, 0),
                statusCode, dayOfWeek, updateTime
        );
    }

    /**
     * 当前季度（AniList 的 MediaSeason 枚举）
     * 1-3月 WINTER，4-6月 SPRING，7-9月 SUMMER，10-12月 FALL
     */
    private String currentSeason() {
        int month = ZonedDateTime.now(BROADCAST_ZONE).getMonthValue();
        if (month <= 3) {
            return "WINTER";
        } else if (month <= 6) {
            return "SPRING";
        } else if (month <= 9) {
            return "SUMMER";
        }
        return "FALL";
    }

    private int currentSeasonYear() {
        return ZonedDateTime.now(BROADCAST_ZONE).getYear();
    }

    private String getDayName(Integer dayOfWeek) {
        if (dayOfWeek == null) {
            return "";
        }
        return switch (dayOfWeek) {
            case 1 -> "周一";
            case 2 -> "周二";
            case 3 -> "周三";
            case 4 -> "周四";
            case 5 -> "周五";
            case 6 -> "周六";
            case 7 -> "周日";
            default -> "";
        };
    }

    private static String textOrNull(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        String value = node.asText();
        return (value == null || value.isBlank()) ? null : value;
    }

    private static String firstNonBlank(String... candidates) {
        for (String candidate : candidates) {
            if (candidate != null && !candidate.isBlank()) {
                return candidate;
            }
        }
        return null;
    }

    /** 供配置类读取的默认值（便于文档与测试引用） */
    public static Map<String, Object> defaults() {
        return Map.of("apiUrl", DEFAULT_API_URL, "pageSize", DEFAULT_PER_PAGE);
    }
}
