package com.global17.auth_service.util;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
public class TavilyClient {

    private static final Logger logger = LoggerFactory.getLogger(TavilyClient.class);

    @Value("${tavily.api-key}")
    private String apiKey;

    private final RestTemplate restTemplate = new RestTemplate();
    private final String TAVILY_URL = "https://api.tavily.com/search";

    public List<Map<String, String>> search(String query) {
        return search(query, 100);
    }

    public List<Map<String, String>> search(String query, int days) {

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> body = new HashMap<>();
        body.put("api_key", apiKey);
        body.put("query", query);
        body.put("search_depth", "advanced");
        body.put("include_answer", false);
        body.put("days", days);
        body.put("max_results", 10);
        body.put("include_raw_content", false);

        // ==================================================================
        // [수정] 쿼리(검색어)를 보고 적절한 도메인 리스트를 자동으로 선택합니다.
        // ==================================================================
        List<String> targetDomains = new ArrayList<>();
        String lowerQuery = query.toLowerCase();

        if (lowerQuery.contains("govinfo") || lowerQuery.contains("fda") || lowerQuery.contains("federalregister") || lowerQuery.contains("ttb") || lowerQuery.contains("usa")) {
            // 미국 검색인 경우
            targetDomains.addAll(List.of("govinfo.gov", "federalregister.gov", "fda.gov", "ttb.gov"));
        } 
        else if (lowerQuery.contains("eec") || lowerQuery.contains("rospotrebnadzor") || lowerQuery.contains("russia") || lowerQuery.contains("tr cu")) {
            // 러시아 검색인 경우
            targetDomains.addAll(List.of("eec.eaeunion.org", "rospotrebnadzor.ru"));
        } 
        else if (lowerQuery.contains("setneg") || lowerQuery.contains("kemkes") || lowerQuery.contains("kemenkeu") || lowerQuery.contains("pom") || lowerQuery.contains("indonesia")) {
            // 인도네시아 검색인 경우
            targetDomains.addAll(List.of("setneg.go.id", "kemkes.go.id", "kemenkeu.go.id", "pom.go.id"));
        } 
        else {
            // 구분이 안 되면 전체 다 넣기 (기본값)
            targetDomains.addAll(List.of(
                "govinfo.gov", "federalregister.gov", "fda.gov", "ttb.gov",
                "eec.eaeunion.org", "rospotrebnadzor.ru",
                "setneg.go.id", "kemkes.go.id", "kemenkeu.go.id", "pom.go.id"
            ));
            logger.warn("⚠️ 국가 식별 실패, 전체 도메인으로 검색합니다: {}", query);
        }

        // 선택된 도메인만 필터에 적용
        body.put("include_domains", targetDomains);
        // ==================================================================

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<JsonNode> response = restTemplate.postForEntity(TAVILY_URL, request, JsonNode.class);

            if (response.getBody() == null || !response.getBody().has("results")) {
                logger.warn("Tavily API response is empty for query: {}", query);
                return new ArrayList<>();
            }

            JsonNode resultsNode = response.getBody().get("results");
            List<Map<String, String>> results = new ArrayList<>();

            if (resultsNode.isArray()) {
                for (JsonNode node : resultsNode) {
                    Map<String, String> item = new HashMap<>();
                    item.put("title", node.has("title") ? node.get("title").asText() : "No Title");
                    item.put("url", node.has("url") ? node.get("url").asText() : "");
                    item.put("content", node.has("content") ? node.get("content").asText() : "");
                    item.put("published_date", node.has("published_date") ? node.get("published_date").asText() : "Unknown");
                    results.add(item);
                }
            }
            return results;

        } catch (Exception e) {
            logger.error("Error during Tavily search: {}", e.getMessage(), e);
            return new ArrayList<>();
        }
    }
}





