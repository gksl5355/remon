package com.global17.auth_service.controller;

import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.service.CrawlService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/crawl")
@RequiredArgsConstructor
// CORS 설정 (프론트엔드 연동 시 필요할 수 있음)
@CrossOrigin(origins = "*") 
public class CrawlController {

    private final CrawlService crawlService;

    // 1. 크롤링 실행 (비동기)
    @PostMapping("/run-batch")
    public String runBatch() {
        new Thread(() -> crawlService.runBatchCrawling()).start();
        return "🚀 크롤링 작업이 시작되었습니다.";
    }

    // 2. 타겟 목록 조회 (관리자 페이지용)
    @GetMapping("/targets")
    public List<CrawlTarget> getTargets() {
        return crawlService.getAllTargets();
    }

    // 3. 타겟 추가 (관리자 페이지용)
    @PostMapping("/targets")
    public CrawlTarget addTarget(@RequestBody CrawlTarget target) {
        return crawlService.addTarget(target);
    }

    // 4. 타겟 삭제 (관리자 페이지용)
    @DeleteMapping("/targets/{id}")
    public String deleteTarget(@PathVariable Long id) {
        crawlService.deleteTarget(id);
        return "✅ 삭제되었습니다.";
    }

    // 5. 타겟 수정 (전체 정보)
    @PutMapping("/targets/{id}")
    public CrawlTarget updateTarget(@PathVariable Long id, @RequestBody CrawlTarget target) {
        System.out.println("🔄 타겟 수정 요청: ID=" + id);
        return crawlService.updateTarget(id, target);
    }

    // 6. 상태 변경 (활성/비활성 토글)
    @PatchMapping("/targets/{id}/status")
    public String updateStatus(@PathVariable Long id, @RequestParam boolean enabled) {
        crawlService.updateTargetStatus(id, enabled);
        return "✅ 상태가 변경되었습니다.";
    }
}

