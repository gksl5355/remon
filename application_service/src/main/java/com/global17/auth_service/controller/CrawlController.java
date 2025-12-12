package com.global17.auth_service.controller;

import java.util.List;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
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

    private final CrawlService_prefix crawlServicePrefix;

    // 크롤링 실행
    @PostMapping("/run-batch")
    public String runBatch() {
        new Thread(() -> crawlServicePrefix.runBatchCrawling()).start();
        return "🚀 [버저닝 모드] 크롤링 작업이 시작되었습니다.";
    }

    // --- 타겟 관리 API ---

    @GetMapping("/targets")
    public List<CrawlTarget> getTargets() {
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

    // [신규] 부분 수정 (PATCH)
    // URL: PATCH /api/crawl/targets/{id}
    @PatchMapping("/targets/{id}")
    public CrawlTarget patchTarget(@PathVariable Long id, @RequestBody CrawlTarget target) {
        System.out.println("🔄 타겟 부분 수정 요청: ID=" + id);
        return crawlServicePrefix.patchTarget(id, target);
    }

    @PatchMapping("/targets/{id}/status")
    public String updateStatus(@PathVariable Long id, @RequestParam boolean enabled) {
        crawlServicePrefix.updateTargetStatus(id, enabled);
        return "✅ 상태가 변경되었습니다.";
    }
}
