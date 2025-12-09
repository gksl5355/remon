package com.global17.auth_service.controller;

import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.service.CrawlService_prefix;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/targets")
@RequiredArgsConstructor
public class TargetController {

    //private final CrawlService crawlService; 또는 private final CrawlService_prefix crawlServicePrefix;

    private final CrawlService_prefix crawlServicePrefix;

    // 조회: GET /api/targets
    @GetMapping
    public List<CrawlTarget> getTargets() {
        return crawlServicePrefix.getAllTargets();
    }

    // 추가: POST /api/targets
    @PostMapping
    public CrawlTarget addTarget(@RequestBody CrawlTarget target) {
        return crawlServicePrefix.addTarget(target);
    }

    // 삭제: DELETE /api/targets/{id}
    @DeleteMapping("/{id}")
    public String deleteTarget(@PathVariable Long id) {
        crawlServicePrefix.deleteTarget(id);
        return "✅ 삭제되었습니다.";
    }
}
