// CrawlService_prefix.java 컨트롤러 코드

package com.global17.auth_service.controller;

import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.service.CrawlService_prefix;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/crawl")
@RequiredArgsConstructor
@CrossOrigin(origins = "*") 
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



// 기존 CrawlService.java 컨트롤러 코드 --- IGNORE ---

// package com.global17.auth_service.controller;

// import com.global17.auth_service.entity.CrawlTarget;
// import com.global17.auth_service.service.CrawlService_prefix;      // 수정
// import lombok.RequiredArgsConstructor;
// import org.springframework.web.bind.annotation.*;

// import java.util.List;

// @RestController
// @RequestMapping("/api/crawl")
// @RequiredArgsConstructor
// // CORS 설정 (프론트엔드 연동 시 필요할 수 있음)
// @CrossOrigin(origins = "*") 
// public class CrawlController {

//     private final CrawlService_prefix crawlServicePrefix;

//     // 1. 크롤링 실행 (비동기)
//     @PostMapping("/run-batch")
//     public String runBatch() {
//         new Thread(() -> crawlServicePrefix.runBatchCrawling()).start();
//         return "🚀 크롤링 작업이 시작되었습니다.";
//     }

//     // 2. 타겟 목록 조회 (관리자 페이지용)
//     @GetMapping("/targets")
//     public List<CrawlTarget> getTargets() {
//         return crawlServicePrefix.getAllTargets();
//     }

//     // 3. 타겟 추가 (관리자 페이지용)
//     @PostMapping("/targets")
//     public CrawlTarget addTarget(@RequestBody CrawlTarget target) {
//         return crawlServicePrefix.addTarget(target);
//     }

//     // 4. 타겟 삭제 (관리자 페이지용)
//     @DeleteMapping("/targets/{id}")
//     public String deleteTarget(@PathVariable Long id) {
//         crawlServicePrefix.deleteTarget(id);
//         return "✅ 삭제되었습니다.";
//     }

//     // 5. 타겟 수정 (전체 정보)
//     @PutMapping("/targets/{id}")
//     public CrawlTarget updateTarget(@PathVariable Long id, @RequestBody CrawlTarget target) {
//         System.out.println("🔄 타겟 수정 요청: ID=" + id);
//         return crawlServicePrefix.updateTarget(id, target);
//     }

//     // 6. 상태 변경 (활성/비활성 토글)
//     @PatchMapping("/targets/{id}/status")
//     public String updateStatus(@PathVariable Long id, @RequestParam boolean enabled) {
//         crawlServicePrefix.updateTargetStatus(id, enabled);
//         return "✅ 상태가 변경되었습니다.";
//     }
// }

