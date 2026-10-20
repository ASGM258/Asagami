package com.anime.manager.service.impl.source;

import com.anime.manager.dto.AnimeDetail;
import com.anime.manager.service.AnimeDetailSource;
import com.anime.manager.util.TextCleaner;
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
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * AniList GraphQL 动漫详情数据源
 *
 * <p>为什么换成 AniList：
 * <ul>
 *   <li>原 Jikan API（api.jikan.moe）已不可用（连接超时）</li>
 *   <li>MyAnimeList 官方 API v2 需要申请 Client ID</li>
 *   <li>AniList 免费、无需密钥，且支持
 *       {@code Media(idMal: Int)} —— 仍以 MAL ID 为入口，调用方无需改动</li>
 * </ul>
 *
 * <p>字段映射要点：
 * <ul>
 *   <li>入参是 MAL ID，通过 <code>idMal</code> 参数查询</li>
 *   <li><code>title.native</code> → titleJp；<code>title.english</code> → englishTitle</li>
 *   <li><code>averageScore</code> 为 0-100，需 ÷10 转 10 分制</li>
 *   <li><code>description</code> 即使声明 asHtml:false 仍含 <code>&lt;i&gt;</code>、
 *       <code>&lt;br&gt;</code> 等标记，必须清洗</li>
 * </ul>
 *
 * <p>⚠️ 不存在的 MAL ID 会让 AniList 返回 <b>HTTP 404</b>，而 RestTemplate 默认在
 * 4xx 时直接抛 HttpClientErrorException，根本读不到响应体。因此这里为每次请求
 * 单独设置一个把错误响应原样交回的 ErrorHandler，从而能统一走
 * {@link AnimeNotFoundException}。异常消息中含 "404"，异步补抓据此判定无需重试。
 */
@Slf4j
@Component
public class AniListAnimeDetailSource implements AnimeDetailSource {

    /** 默认端点 */
    private static final String DEFAULT_API_URL = "https://graphql.anilist.co";

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final String apiUrl;

    public AniListAnimeDetailSource(
            RestTemplate restTemplate,
            @Value("${scraper.anime.anilist-url:" + DEFAULT_API_URL + "}") String apiUrl) {
        this.restTemplate = restTemplate;
        this.apiUrl = apiUrl;
    }

    private static final String QUERY = """
            query ($idMal: Int) {
              Media(idMal: $idMal, type: ANIME) {
                id
                idMal
                title { native romaji english }
                coverImage { extraLarge large medium }
                description(asHtml: false)
                episodes
                status
                format
                startDate { year month day }
                averageScore
                genres
              }
            }
            """;

    @Override
    public String sourceName() {
        return "AniList";
    }

    @Override
    public AnimeDetail fetchByMalId(Integer malId) {
        if (malId == null) {
            throw new IllegalArgumentException("malId 不能为空");
        }

        ObjectNode variables = objectMapper.createObjectNode();
        variables.put("idMal", malId);

        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("query", QUERY);
        payload.set("variables", variables);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));

        ResponseEntity<String> response;
        try {
            response = restTemplate.postForEntity(
                    apiUrl, new HttpEntity<>(payload.toString(), headers), String.class);
        } catch (HttpClientErrorException e) {
            // AniList 对无效 idMal 返回 404；此处按资源不存在处理
            if (e.getStatusCode().value() == 404) {
                throw new AnimeNotFoundException("动漫不存在 (MAL ID: " + malId + ")");
            }
            throw new IllegalStateException(
                    "AniList 请求失败 (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        } catch (HttpServerErrorException e) {
            throw new IllegalStateException(
                    "AniList 服务错误 (" + e.getStatusCode() + ")，请稍后重试", e);
        }

        JsonNode media = null;
        try {
            JsonNode root = objectMapper.readTree(response.getBody());
            media = root.path("data").path("Media");
        } catch (Exception e) {
            throw new IllegalStateException("解析 AniList 响应失败: " + e.getMessage(), e);
        }

        // 双保险：即使数据源改为返回 200 + Media:null，也按不存在处理
        if (media == null || media.isMissingNode() || media.isNull()) {
            throw new AnimeNotFoundException("动漫不存在 (MAL ID: " + malId + ")");
        }

        return mapMedia(media, malId);
    }

    /**
     * 把 AniList 的 Media 映射为归一化详情
     */
    private AnimeDetail mapMedia(JsonNode media, Integer malId) {
        String nativeTitle = textOrNull(media.path("title").path("native"));
        String englishTitle = textOrNull(media.path("title").path("english"));
        String romajiTitle = textOrNull(media.path("title").path("romaji"));

        String coverImage = firstNonBlank(
                textOrNull(media.path("coverImage").path("extraLarge")),
                textOrNull(media.path("coverImage").path("large")),
                textOrNull(media.path("coverImage").path("medium"))
        );

        String synopsis = TextCleaner.stripHtml(textOrNull(media.path("description")));

        Integer episodes = media.hasNonNull("episodes") ? media.get("episodes").asInt() : null;

        // FINISHED / CANCELLED 视为完结，其余（RELEASING / NOT_YET_RELEASED）视为连载中
        String status = media.path("status").asText("");
        int statusCode = ("FINISHED".equals(status) || "CANCELLED".equals(status)) ? 1 : 0;

        LocalDate releaseDate = parseStartDate(media.path("startDate"));

        List<String> genres = new ArrayList<>();
        JsonNode genresNode = media.path("genres");
        if (genresNode.isArray()) {
            for (JsonNode genre : genresNode) {
                String name = textOrNull(genre);
                if (name != null) {
                    genres.add(name);
                }
            }
        }

        BigDecimal rating = BigDecimal.ZERO;
        if (media.hasNonNull("averageScore")) {
            rating = BigDecimal.valueOf(media.get("averageScore").asDouble())
                    .divide(BigDecimal.TEN, 1, RoundingMode.HALF_UP);
        }

        return new AnimeDetail(
                malId,
                nativeTitle,
                firstNonBlank(englishTitle, romajiTitle, nativeTitle),
                coverImage,
                synopsis,
                episodes,
                statusCode,
                releaseDate,
                genres,
                rating
        );
    }

    /**
     * 解析开播日期
     *
     * <p>AniList 的 startDate 各字段可能为 null，需同时校验合法性后再构造 LocalDate。
     */
    private LocalDate parseStartDate(JsonNode startDate) {
        if (startDate == null || startDate.isMissingNode()) {
            return null;
        }
        int year = startDate.path("year").asInt(0);
        int month = startDate.path("month").asInt(0);
        int day = startDate.path("day").asInt(0);

        if (year <= 0 || month <= 0 || day <= 0) {
            return null;
        }
        try {
            return LocalDate.of(year, month, day);
        } catch (Exception e) {
            log.warn("解析开播日期失败: {}-{}-{}", year, month, day);
            return null;
        }
    }

    /**
     * 取值：字段缺失或空白时返回 null
     */
    private static String textOrNull(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        String value = node.asText();
        return (value == null || value.isBlank()) ? null : value;
    }

    private static String firstNonBlank(String... candidates) {
        return TextCleaner.firstNonBlank(candidates);
    }
}
