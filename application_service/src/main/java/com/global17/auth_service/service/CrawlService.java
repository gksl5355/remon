package com.global17.auth_service.service;

import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.repository.CrawlTargetRepository;
import com.global17.auth_service.util.S3Uploader;
import com.global17.auth_service.util.TavilyClient;
import lombok.RequiredArgsConstructor;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class CrawlService {

    private final TavilyClient tavilyClient;
    private final S3Uploader s3Uploader;
    private final CrawlTargetRepository targetRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * [배치 실행] DB에 저장된 활성 타겟들을 모두 크롤링
     */
    public void runBatchCrawling() {
        System.out.println("🔄 [Batch] DB 기반 일괄 크롤링 시작...");
        
        List<CrawlTarget> targets = targetRepository.findByEnabledTrue();
        
        if (targets.isEmpty()) {
            System.out.println("⚠️ 활성화된 타겟이 없습니다.");
            return;
        }

        for (CrawlTarget target : targets) {
            System.out.println("👉 Target: " + target.getCountry());
            for (String keyword : target.getKeywords()) {
                processCrawling(target.getCountry(), target.getCode(), keyword, target.getCategory());
                try { Thread.sleep(1000); } catch (InterruptedException e) {}
            }
        }
        System.out.println("🎉 [Batch] 완료!");
    }

    /**
     * [단건 실행] 실제 크롤링 및 S3 업로드 로직
     */
    private void processCrawling(String country, String countryCode, String keyword, String category) {
        System.out.println("   🚀 탐색: " + keyword);
        
        String query = keyword;
        if ("regulation".equalsIgnoreCase(category)) {
             query += " filetype:pdf";
        }

        List<Map<String, String>> searchResults = tavilyClient.search(query);

        if (searchResults.isEmpty()) {
            System.out.println("      💨 결과 없음");
            return;
        }

        for (Map<String, String> result : searchResults) {
            String url = result.get("url");
            String title = result.get("title");

            try {
                byte[] fileContent = restTemplate.getForObject(url, byte[].class);
                
                if (fileContent != null && fileContent.length > 0) {
                    boolean isPdf = isPdfContent(fileContent);
                    String ext = isPdf ? ".pdf" : ".txt";
                    byte[] finalContent = isPdf ? fileContent : cleanHtmlToText(fileContent);

                    // [수정] 파일명 생성 (제목 + 내용해시)
                    String fileName = generateVersionedFileName(title, finalContent, ext);
                    
                    // S3 업로드
                    String s3Path = s3Uploader.uploadFile(finalContent, fileName, category);
                    
                    if (s3Path != null) {
                        System.out.println("      ✅ S3 업로드: " + fileName);
                    }
                }
            } catch (Exception e) {
                System.err.println("      ❌ 실패: " + url + " -> " + e.getMessage());
            }
        }
    }

     public CrawlTarget updateTarget(Long id, CrawlTarget updatedInfo) {
        CrawlTarget target = targetRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("ID가 " + id + "인 타겟을 찾을 수 없습니다."));

        // 내용 덮어쓰기
        target.setCountry(updatedInfo.getCountry());
        target.setCode(updatedInfo.getCode());
        target.setCategory(updatedInfo.getCategory());
        target.setEnabled(updatedInfo.isEnabled());
        
        // 키워드 리스트 교체 (기존 것 비우고 새로 채움)
        if (target.getKeywords() != null) {
            target.getKeywords().clear();
        }
        if (updatedInfo.getKeywords() != null) {
            target.getKeywords().addAll(updatedInfo.getKeywords());
        }

        return targetRepository.save(target);
    }

    /**
     * [신규] 활성/비활성 상태만 변경 (PATCH)
     */
    public void updateTargetStatus(Long id, boolean enabled) {
        CrawlTarget target = targetRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Target not found"));
        target.setEnabled(enabled);
        targetRepository.save(target);
        System.out.println("🔄 타겟 상태 변경: " + target.getCountry() + " -> " + enabled);
    }

    // --- 유틸 메서드 ---

    /**
     * [버전 관리형 파일명 생성]
     * 규칙: {정제된제목}_{내용해시8자리}.확장자
     */
    private String generateVersionedFileName(String title, byte[] content, String ext) {
        // 1. 제목 정제
        String safeTitle = title.replaceAll("[\\\\/:*?\"<>|]", ""); 
        safeTitle = safeTitle.trim().replaceAll("\\s+", "_");
        
        // 길이 제한
        if (safeTitle.length() > 100) {
            safeTitle = safeTitle.substring(0, 100);
        }
        
        // 2. 내용 기반 해시 생성
        String contentHash = calculateHash(content).substring(0, 8);
        
        // 3. 조합
        return String.format("%s_%s%s", safeTitle, contentHash, ext);
    }

    /**
     * 바이트 배열의 SHA-256 해시 계산
     */
    private String calculateHash(byte[] content) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(content);
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (Exception e) {
            // [오타 수정] returnString -> return String
            return String.valueOf(System.currentTimeMillis());
        }
    }

    // --- 관리자 기능 ---
    public List<CrawlTarget> getAllTargets() {
        return targetRepository.findAll();
    }

    public CrawlTarget addTarget(CrawlTarget target) {
        return targetRepository.save(target);
    }

    public void deleteTarget(Long id) {
        targetRepository.deleteById(id);
    }

    // --- 내부 판별 로직 ---
    private boolean isPdfContent(byte[] data) {
        if (data.length < 4) return false;
        return data[0] == 0x25 && data[1] == 0x50 && data[2] == 0x44 && data[3] == 0x46;
    }

    private byte[] cleanHtmlToText(byte[] htmlBytes) {
        try {
            String htmlString = new String(htmlBytes, StandardCharsets.UTF_8);
            Document doc = Jsoup.parse(htmlString);
            doc.select("script, style, header, footer, nav, noscript, iframe").remove();
            return doc.text().getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            return htmlBytes;
        }
    }
}

