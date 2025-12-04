package com.global17.auth_service.util;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

    @Value("${tavily.api-key}")
    private String apiKey;

    private final RestTemplate restTemplate = new RestTemplate();
    private final String TAVILY_URL = "https://api.tavily.com/search";

    public List<Map<String, String>> search(String query) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> body = new HashMap<>();
        body.put("api_key", apiKey);
        body.put("query", query);
        body.put("search_depth", "basic");
        body.put("include_answer", false);
        body.put("max_results", 10);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<JsonNode> response = restTemplate.postForEntity(TAVILY_URL, request, JsonNode.class);
            JsonNode resultsNode = response.getBody().get("results");
            
            List<Map<String, String>> results = new ArrayList<>();
            if (resultsNode.isArray()) {
                for (JsonNode node : resultsNode) {
                    Map<String, String> item = new HashMap<>();
                    item.put("title", node.get("title").asText());
                    item.put("url", node.get("url").asText());
                    results.add(item);
                }
            }
            return results;
        } catch (Exception e) {
            e.printStackTrace();
            return new ArrayList<>();
        }
    }
}



