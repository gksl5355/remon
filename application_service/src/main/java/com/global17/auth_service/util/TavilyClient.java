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

    /**
     * [기본 메서드] 기존 코드와의 호환성 유지
     */
    public List<Map<String, String>> search(String query) {
        return search(query, 100); // 기본값: 100일
    }

    /**
     * [개선된 메서드] 날짜 제한(days)을 설정할 수 있는 오버로딩 메서드
     */
    public List<Map<String, String>> search(String query, int days) {

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        // 1. [순서 중요] 먼저 body 변수를 생성(선언)해야 합니다.
        Map<String, Object> body = new HashMap<>();
        
        // 2. 기본 설정값 입력
        body.put("api_key", apiKey);
        body.put("query", query);
        body.put("search_depth", "advanced"); 
        body.put("include_answer", false);
        body.put("days", days); 
        body.put("max_results", 10);
        body.put("include_raw_content", false);

        // 3. [핵심 해결책] body가 만들어진 "후"에 도메인 설정을 넣어야 합니다.
        List<String> officialDomains = List.of(
            // 🇺🇸 미국
            "govinfo.gov", "federalregister.gov", "fda.gov", "ttb.gov",
            // 🇷🇺 러시아 (EAEU)
            "eec.eaeunion.org", "rospotrebnadzor.ru",
            // 🇮🇩 인도네시아
            "setneg.go.id", "kemkes.go.id", "kemenkeu.go.id", "pom.go.id"
        );

        // 이제 body 변수가 존재하므로 에러가 나지 않습니다.
        body.put("include_domains", officialDomains);


        // 4. 요청 전송
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

// package com.global17.auth_service.util;

// import com.fasterxml.jackson.databind.JsonNode;
// import org.slf4j.Logger; // 로거 추가
// import org.slf4j.LoggerFactory;
// import org.springframework.beans.factory.annotation.Value;
// import org.springframework.http.*;
// import org.springframework.stereotype.Component;
// import org.springframework.web.client.RestTemplate;

// import java.util.ArrayList;
// import java.util.HashMap;
// import java.util.List;
// import java.util.Map;

// @Component
// public class TavilyClient {

//     private static final Logger logger = LoggerFactory.getLogger(TavilyClient.class);

//     @Value("${tavily.api-key}")
//     private String apiKey;

//     private final RestTemplate restTemplate = new RestTemplate();
//     private final String TAVILY_URL = "https://api.tavily.com/search";

//     /**
//      * [기본 메서드] 기존 코드와의 호환성 유지
//      * 기존 서비스 로직에서 search(query)만 호출해도 동작하도록 함.
//      * 기본적으로 최근 1년(365일) 이내의 문서를 검색하도록 설정.
//      */
//     public List<Map<String, String>> search(String query) {
//         return search(query, 100); // 기본값: 1년
//     }

//     /**
//      * [개선된 메서드] 날짜 제한(days)을 설정할 수 있는 오버로딩 메서드
//      * @param query 검색어 (예: "site:fda.gov/tobacco-products final rule...")
//      * @param days  최근 며칠 내의 문서를 찾을지 (예: 30, 365)
//      */
//     public List<Map<String, String>> search(String query, int days) {

//         // [핵심 해결책] 허용된 "공식 정부 사이트" 리스트 정의
//     // 이 리스트에 없는 Zhihu, StackOverflow 등은 검색 결과에서 아예 배제됩니다.
//         List<String> officialDomains = List.of(
//         // 🇺🇸 미국
//             "govinfo.gov", "federalregister.gov", "fda.gov", "ttb.gov",
//         // 🇷🇺 러시아 (EAEU)
//             "eec.eaeunion.org", "rospotrebnadzor.ru",
//         // 🇮🇩 인도네시아
//             "setneg.go.id", "kemkes.go.id", "kemenkeu.go.id", "pom.go.id"
//     );

//     // API 요청에 도메인 제한 추가
//         body.put("include_domains", officialDomains);


//         HttpHeaders headers = new HttpHeaders();
//         headers.setContentType(MediaType.APPLICATION_JSON);

//         Map<String, Object> body = new HashMap<>();
//         body.put("api_key", apiKey);
//         body.put("query", query);
        
//         // [개선 1] 규제 검색은 깊이 있게 찾아야 하므로 advanced 권장
//         body.put("search_depth", "advanced"); 
        
//         // [개선 2] 답변 생성은 필요 없으므로 false (속도 향상)
//         body.put("include_answer", false);
        
//         // [개선 3] 날짜 필터링: DB 키워드에 년도를 넣지 않아도 최신글만 가져옴
//         body.put("days", days); 
        
//         body.put("max_results", 10);
        
//         // [개선 4] 본문 내용도 가져와야 나중에 내용 분석이 가능함
//         body.put("include_raw_content", false); // 필요시 true로 변경

//         HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

//         try {
//             ResponseEntity<JsonNode> response = restTemplate.postForEntity(TAVILY_URL, request, JsonNode.class);
            
//             // 응답이 없거나 실패했을 경우 처리
//             if (response.getBody() == null || !response.getBody().has("results")) {
//                 logger.warn("Tavily API response is empty for query: {}", query);
//                 return new ArrayList<>();
//             }

//             JsonNode resultsNode = response.getBody().get("results");
//             List<Map<String, String>> results = new ArrayList<>();

//             if (resultsNode.isArray()) {
//                 for (JsonNode node : resultsNode) {
//                     Map<String, String> item = new HashMap<>();
                    
//                     // null 체크를 하며 안전하게 데이터 추출
//                     item.put("title", node.has("title") ? node.get("title").asText() : "No Title");
//                     item.put("url", node.has("url") ? node.get("url").asText() : "");
                    
//                     // [개선 5] 내용과 날짜 정보 추가 수집
//                     item.put("content", node.has("content") ? node.get("content").asText() : "");
//                     item.put("published_date", node.has("published_date") ? node.get("published_date").asText() : "Unknown");

//                     results.add(item);
//                 }
//             }
//             return results;

//         } catch (Exception e) {
//             // [개선 6] 에러 로그를 남겨서 디버깅 용이하게 변경
//             logger.error("Error during Tavily search: {}", e.getMessage(), e);
//             return new ArrayList<>();
//         }
//     }
// }

// package com.global17.auth_service.util;

// import com.fasterxml.jackson.databind.JsonNode;
// import com.fasterxml.jackson.databind.ObjectMapper;
// import org.springframework.beans.factory.annotation.Value;
// import org.springframework.http.*;
// import org.springframework.stereotype.Component;
// import org.springframework.web.client.RestTemplate;

// import java.util.ArrayList;
// import java.util.HashMap;
// import java.util.List;
// import java.util.Map;

// @Component
// public class TavilyClient {

//     @Value("${tavily.api-key}")
//     private String apiKey;

//     private final RestTemplate restTemplate = new RestTemplate();
//     private final String TAVILY_URL = "https://api.tavily.com/search";

//     public List<Map<String, String>> search(String query) {
//         HttpHeaders headers = new HttpHeaders();
//         headers.setContentType(MediaType.APPLICATION_JSON);

//         Map<String, Object> body = new HashMap<>();
//         body.put("api_key", apiKey);
//         body.put("query", query);
//         body.put("search_depth", "basic");
//         body.put("include_answer", false);
//         body.put("max_results", 10);

//         HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

//         try {
//             ResponseEntity<JsonNode> response = restTemplate.postForEntity(TAVILY_URL, request, JsonNode.class);
//             JsonNode resultsNode = response.getBody().get("results");
            
//             List<Map<String, String>> results = new ArrayList<>();
//             if (resultsNode.isArray()) {
//                 for (JsonNode node : resultsNode) {
//                     Map<String, String> item = new HashMap<>();
//                     item.put("title", node.get("title").asText());
//                     item.put("url", node.get("url").asText());
//                     results.add(item);
//                 }
//             }
//             return results;
//         } catch (Exception e) {
//             e.printStackTrace();
//             return new ArrayList<>();
//         }
//     }
// }



