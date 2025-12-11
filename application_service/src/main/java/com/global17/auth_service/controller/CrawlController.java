// CrawlService_prefix.java 컨트롤러 코드

package com.global17.auth_service.controller;

import java.util.List;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.service.CrawlService_prefix;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/crawl")
@RequiredArgsConstructor
public class CrawlController {

    // [수정] 오직 prefix 서비스만 주입받습니다.
    private final CrawlService_prefix crawlServicePrefix;

    @PostMapping("/run-batch")
    public String runBatch() {
        // [수정] crawlServicePrefix 사용
        new Thread(() -> crawlServicePrefix.runBatchCrawling()).start();
        return "🚀 [버저닝 모드] 크롤링 작업이 시작되었습니다.";
    }

    @GetMapping("/targets")
    public List<CrawlTarget> getTargets() {
        // [수정] crawlServicePrefix 사용
        return crawlServicePrefix.getAllTargets();
    }

    @PostMapping("/targets")
    public CrawlTarget addTarget(@RequestBody CrawlTarget target) {
        return crawlServicePrefix.addTarget(target);
    }

    @DeleteMapping("/targets/{id}")
    public String deleteTarget(@PathVariable Long id) {
        crawlServicePrefix.deleteTarget(id);
        return "✅ 삭제되었습니다.";
    }

    @PutMapping("/targets/{id}")
    public CrawlTarget updateTarget(@PathVariable Long id, @RequestBody CrawlTarget target) {
        System.out.println("🔄 타겟 수정 요청: ID=" + id);
        return crawlServicePrefix.updateTarget(id, target);
    }

    @PatchMapping("/targets/{id}/status")
    public String updateStatus(@PathVariable Long id, @RequestParam boolean enabled) {
        crawlServicePrefix.updateTargetStatus(id, enabled);
        return "✅ 상태가 변경되었습니다.";
    }
}
