package com.global17.auth_service.controller;

import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.service.CrawlService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/targets")
@RequiredArgsConstructor
public class TargetController {

    private final CrawlService crawlService;

    // 조회: GET /api/targets
    @GetMapping
    public List<CrawlTarget> getTargets() {
        return crawlService.getAllTargets();
    }

    // 추가: POST /api/targets
    @PostMapping
    public CrawlTarget addTarget(@RequestBody CrawlTarget target) {
        return crawlService.addTarget(target);
    }

    // 삭제: DELETE /api/targets/{id}
    @DeleteMapping("/{id}")
    public String deleteTarget(@PathVariable Long id) {
        crawlService.deleteTarget(id);
        return "✅ 삭제되었습니다.";
    }
}
// ```

// ---

// ### 2. 🎨 프론트엔드 (Vue.js) 연동 가이드

// 관리자 페이지에 **[국가/키워드 관리]** 탭을 만들고 아래 API를 연결하면 됩니다.

// #### 1) 타겟 목록 조회 (GET)
// * **API:** `GET /api/targets`
// * **응답 예시:**
//     ```json
//     [
//       {
//         "targetId": 1,
//         "country": "USA FDA Official",
//         "code": "US",
//         "enabled": true,
//         "category": "regulation",
//         "keywords": ["site:fda.gov ...", "..."]
//       }
//     ]
//     ```
// * **화면:** 테이블 형태로 보여줍니다. (국가, 코드, 카테고리, 키워드, 삭제 버튼)

// #### 2) 타겟 추가 (POST)
// * **API:** `POST /api/targets`
// * **전송 Body (JSON):**
//     ```json
//     {
//       "country": "Vietnam Ministry of Health",
//       "code": "VN",
//       "enabled": true,
//       "category": "regulation",
//       "keywords": ["Vietnam e-cigarette ban pdf", "tobacco law"]
//     }

// package com.global17.auth_service.controller;

// import com.global17.auth_service.entity.CrawlTarget;
// import com.global17.auth_service.service.CrawlService;
// import lombok.RequiredArgsConstructor;
// import org.springframework.web.bind.annotation.*;

// import java.util.List;

// @RestController
// @RequestMapping("/api/targets")
// @RequiredArgsConstructor
// public class TargetController {

//     private final CrawlService crawlService;

//     // 조회
//     @GetMapping
//     public List<CrawlTarget> getTargets() {
//         return crawlService.getAllTargets();
//     }

//     // 추가
//     @PostMapping
//     public CrawlTarget addTarget(@RequestBody CrawlTarget target) {
//         return crawlService.addTarget(target);
//     }

//     // 삭제
//     @DeleteMapping("/{id}")
//     public String deleteTarget(@PathVariable Long id) {
//         crawlService.deleteTarget(id);
//         return "✅ 삭제되었습니다.";
//     }
// }


// ### 2. 🎨 프론트엔드 (Vue.js) 연동 가이드

// 관리자 페이지에 [국가/키워드 관리] 탭을 만들고 아래 API를 연결

// #### 1) 타겟 목록 조회 (GET)
// API: `GET /api/targets`
// 화면: 테이블 형태 (국가, 코드, 카테고리, 키워드, 삭제 버튼)

// #### 2) 타겟 추가 (POST)
// * API: `POST /api/targets`
// * Body (JSON):
//     ```json
//     {
//       "country": "Vietnam Ministry of Health",
//       "code": "VN",
//       "enabled": true,
//       "category": "regulation",
//       "keywords": ["Vietnam e-cigarette ban pdf", "tobacco law"]