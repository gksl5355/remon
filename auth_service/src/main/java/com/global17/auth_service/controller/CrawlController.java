package com.global17.auth_service.controller;

import com.global17.auth_service.service.CrawlService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/crawl")
@RequiredArgsConstructor
public class CrawlController {

    private final CrawlService crawlService;

    // 1. [기존] 수동 실행 (테스트용)
    // POST /api/crawl/run?country=USA&code=US&keyword=tobacco
    @PostMapping("/run")
    public String startCrawling(
            @RequestParam String country,
            @RequestParam String code,
            @RequestParam String keyword) {
        
        crawlService.runCrawling(country, code, keyword);
        return "✅ 단건 크롤링 작업이 완료되었습니다.";
    }

    // 2. [신규] 일괄 실행 (config.yaml 기반)
    // POST /api/crawl/run-batch
    @PostMapping("/run-batch")
    public String startBatchCrawling() {
        // 실제로는 비동기(@Async)로 돌리는 게 좋지만, 확인을 위해 동기로 실행
        crawlService.runBatchCrawling();
        return "🚀 config.yaml 기반 일괄 크롤링이 시작되었습니다. 로그를 확인하세요.";
    }
}

