package com.anime.manager.service.impl.source;

import com.anime.manager.dto.CharacterDetail;
import com.anime.manager.dto.CharacterDetailPage;
import com.anime.manager.service.CharacterDetailSource;
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

import java.util.ArrayList;
import java.util.List;

/**
 * AniList GraphQL 角色数据源
 *
 * <p>为什么换成 AniList：
 * <ul>
 *   <li>原 Jikan API（api.jikan.moe）已不可用（连接超时）</li>
 *   <li>AniList 免费、无需密钥，且角色列表接口**直接返回完整字段**
 *       （简介、生日、别名、收藏数），无需像 Jikan 那样「先取列表页、
 *       再逐个请求 /characters/{id}/full」——原实现每个角色要间隔 3 秒，
 *       抓 50 个角色就要 2.5 分钟以上</li>
 * </ul>
 *
 * <p>⚠️ 重要差异：**AniList 的角色对象不提供 MAL ID**（无 idMal 字段），
 * 因此本数据源以 AniList 角色ID为标识，对应 anime_character.anilist_id 列。
 *
 * <p>字段映射要点：
 * <ul>
 *   <li><code>name.full</code> → name（罗马音），<code>name.native</code> → nameJp</li>
 *   <li><code>name.alternative</code> → 别名（逗号分隔存储）</li>
 *   <li><code>dateOfBirth{{month,day}}</code> → birthday（MM-DD）</li>
 *   <li><code>favourites</code>（英式拼写）→ favorites</li>
 *   <li><code>description</code> 仍含 HTML 标记，必须清洗</li>
 * </ul>
 */
@Slf4j
@Component
public class AniListCharacterSource implements CharacterDetailSource {

    /** 默认端点 */
    private static final String DEFAULT_API_URL = "https://graphql.anilist.co";

    /** 每页条数（AniList 上限 50） */
    private static final int DEFAULT_PER_PAGE = 50;

    private static final int MAX_PER_PAGE = 50;

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final String apiUrl;
    private final int pageSize;

    public AniListCharacterSource(
            RestTemplate restTemplate,
            @Value("${scraper.character.anilist-url:" + DEFAULT_API_URL + "}") String apiUrl,
            @Value("${scraper.character.page-size:" + DEFAULT_PER_PAGE + "}") int pageSize) {
        this.restTemplate = restTemplate;
        this.apiUrl = apiUrl;
        this.pageSize = pageSize;
    }

    /**
     * 角色字段：列表与单个查询共用，避免两处结构不一致
     */
    private static final String CHARACTER_FIELDS = """
              id
              name { full native alternative }
              image { large medium }
              description(asHtml: false)
              dateOfBirth { year month day }
              favourites
            """;

    private static final String PAGE_QUERY = """
            query ($page: Int, $perPage: Int) {
              Page(page: $page, perPage: $perPage) {
                pageInfo { currentPage lastPage hasNextPage }
                characters(sort: FAVOURITES_DESC) {
            %s
                }
              }
            }
            """.formatted(CHARACTER_FIELDS);

    /** 单个角色查询（Character 是单对象，不接受 sort 参数） */
    private static final String BY_ID_QUERY = """
            query ($id: Int) {
              Character(id: $id) {
            %s
              }
            }
            """.formatted(CHARACTER_FIELDS);

    @Override
    public String sourceName() {
        return "AniList";
    }

    @Override
    public CharacterDetailPage fetchPage(int page) {
        int effectivePerPage = pageSize <= 0 ? DEFAULT_PER_PAGE : Math.min(pageSize, MAX_PER_PAGE);

        ObjectNode variables = objectMapper.createObjectNode();
        variables.put("page", Math.max(page, 1));
        variables.put("perPage", effectivePerPage);

        JsonNode pageNode = execute(PAGE_QUERY, variables).path("data").path("Page");
        JsonNode pageInfo = pageNode.path("pageInfo");
        JsonNode nodes = pageNode.path("characters");

        if (!nodes.isArray()) {
            throw new IllegalStateException("AniList 返回数据格式错误: 缺少 Page.characters");
        }

        List<CharacterDetail> items = new ArrayList<>(nodes.size());
        for (JsonNode node : nodes) {
            CharacterDetail detail = mapCharacter(node);
            if (detail != null) {
                items.add(detail);
            }
        }

        int currentPage = pageInfo.path("currentPage").asInt(Math.max(page, 1));
        int lastPage = pageInfo.path("lastPage").asInt(currentPage);
        boolean hasNextPage = pageInfo.path("hasNextPage").asBoolean(false);

        log.info("AniList 角色抓取成功: 第{}/{}页, 本页{}条", currentPage, lastPage, items.size());

        return new CharacterDetailPage(items, currentPage, lastPage, hasNextPage);
    }

    @Override
    public CharacterDetail fetchById(Integer anilistId) {
        if (anilistId == null) {
            throw new IllegalArgumentException("anilistId 不能为空");
        }

        ObjectNode variables = objectMapper.createObjectNode();
        variables.put("id", anilistId);

        // execute() 内部会把 404 转成 CharacterNotFoundException，直接向上抛出即可
        JsonNode node = execute(BY_ID_QUERY, variables).path("data").path("Character");

        if (node == null || node.isMissingNode() || node.isNull()) {
            throw new CharacterNotFoundException("角色不存在 (AniList ID: " + anilistId + ")");
        }

        CharacterDetail detail = mapCharacter(node);
        if (detail == null) {
            throw new CharacterNotFoundException("角色数据不完整 (AniList ID: " + anilistId + ")");
        }
        return detail;
    }

    /**
     * 统一执行 GraphQL 请求并处理错误
     */
    private JsonNode execute(String query, ObjectNode variables) {
        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("query", query);
        payload.set("variables", variables);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));

        ResponseEntity<String> response;
        try {
            response = restTemplate.postForEntity(
                    apiUrl, new HttpEntity<>(payload.toString(), headers), String.class);
        } catch (HttpClientErrorException e) {
            // AniList 对不存在的角色返回 404
            if (e.getStatusCode().value() == 404) {
                throw new CharacterNotFoundException("角色不存在");
            }
            throw new IllegalStateException(
                    "AniList 请求失败 (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        } catch (HttpServerErrorException e) {
            throw new IllegalStateException(
                    "AniList 服务错误 (" + e.getStatusCode() + ")，请稍后重试", e);
        }

        try {
            JsonNode root = objectMapper.readTree(response.getBody());
            JsonNode errors = root.get("errors");
            if (errors != null && errors.isArray() && !errors.isEmpty()) {
                throw new IllegalStateException("AniList 返回错误: " + errors);
            }
            return root;
        } catch (IllegalStateException e) {
            throw e;
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            throw new IllegalStateException("解析 AniList 响应失败: " + e.getMessage(), e);
        }
    }

    /**
     * 把 AniList 的 Character 映射为归一化详情
     *
     * @return 详情；名称为空时返回 null
     */
    private CharacterDetail mapCharacter(JsonNode node) {
        String name = TextCleaner.stripHtml(TextCleaner.firstNonBlank(
                textOrNull(node.path("name").path("full")),
                textOrNull(node.path("name").path("native"))));
        if (name == null) {
            log.warn("AniList 角色缺少名称，跳过: id={}", node.path("id").asInt());
            return null;
        }

        String nameJp = TextCleaner.stripHtml(textOrNull(node.path("name").path("native")));

        String imageUrl = TextCleaner.firstNonBlank(
                textOrNull(node.path("image").path("large")),
                textOrNull(node.path("image").path("medium"))
        );

        String about = TextCleaner.stripHtml(textOrNull(node.path("description")));

        List<String> nicknames = new ArrayList<>();
        JsonNode alternative = node.path("name").path("alternative");
        if (alternative.isArray()) {
            for (JsonNode alias : alternative) {
                String value = TextCleaner.stripHtml(textOrNull(alias));
                if (value != null) {
                    nicknames.add(value);
                }
            }
        }

        String birthday = formatBirthday(node.path("dateOfBirth"));

        Integer favourites = node.hasNonNull("favourites") ? node.get("favourites").asInt() : null;

        return new CharacterDetail(
                node.hasNonNull("id") ? node.get("id").asInt() : null,
                name,
                nameJp,
                imageUrl,
                about,
                nicknames,
                birthday,
                favourites
        );
    }

    /**
     * 生日格式化为 MM-DD
     *
     * <p>AniList 的 dateOfBirth 只保证 month/day 存在，year 常为 null，
     * 且两者都可能缺失，需分别容错。
     */
    private String formatBirthday(JsonNode dateOfBirth) {
        if (dateOfBirth == null || dateOfBirth.isMissingNode() || dateOfBirth.isNull()) {
            return null;
        }
        int month = dateOfBirth.path("month").asInt(0);
        int day = dateOfBirth.path("day").asInt(0);
        if (month <= 0 || day <= 0) {
            return null;
        }
        return String.format("%02d-%02d", month, day);
    }

    private static String textOrNull(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }
        String value = node.asText();
        return (value == null || value.isBlank()) ? null : value;
    }
}
