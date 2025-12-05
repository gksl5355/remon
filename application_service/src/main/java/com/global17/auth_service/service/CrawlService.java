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


// package com.global17.auth_service.service;

// import com.global17.auth_service.entity.CrawlTarget;
// import com.global17.auth_service.repository.CrawlTargetRepository;
// import com.global17.auth_service.util.S3Uploader;
// import com.global17.auth_service.util.TavilyClient;
// import lombok.RequiredArgsConstructor;
// import org.jsoup.Jsoup;
// import org.jsoup.nodes.Document;
// import org.springframework.stereotype.Service;
// import org.springframework.web.client.RestTemplate;

// import java.nio.charset.StandardCharsets;
// import java.util.List;
// import java.util.Map;
// import java.util.UUID;

// @Service
// @RequiredArgsConstructor
// public class CrawlService {

//     private final TavilyClient tavilyClient;
//     private final S3Uploader s3Uploader;
//     private final CrawlTargetRepository targetRepository; // DB Repository 사용
//     private final RestTemplate restTemplate = new RestTemplate();

//     /**
//      * [배치 실행] DB에 저장된 활성 타겟들을 모두 크롤링
//      */
//     public void runBatchCrawling() {
//         System.out.println("🔄 [Batch] DB 기반 일괄 크롤링 시작...");
        
//         List<CrawlTarget> targets = targetRepository.findByEnabledTrue();
        
//         if (targets.isEmpty()) {
//             System.out.println("⚠️ DB에 활성화된 크롤링 타겟이 없습니다.");
//             return;
//         }

//         for (CrawlTarget target : targets) {
//             System.out.println("👉 Target: " + target.getCountry());
//             for (String keyword : target.getKeywords()) {
//                 processCrawling(target.getCountry(), target.getCode(), keyword, target.getCategory());
                
//                 // API 속도 조절
//                 try { Thread.sleep(1000); } catch (InterruptedException e) {}
//             }
//         }
//         System.out.println("🎉 [Batch] 완료!");
//     }

//     /**
//      * [단건 실행] 실제 크롤링 및 S3 업로드 로직
//      */
//     private void processCrawling(String country, String countryCode, String keyword, String category) {
//         System.out.println("   🚀 탐색: " + keyword);
        
//         String query = keyword;
//         if ("regulation".equalsIgnoreCase(category)) {
//              query += " filetype:pdf";
//         }

//         List<Map<String, String>> searchResults = tavilyClient.search(query);

//         if (searchResults.isEmpty()) {
//             System.out.println("      💨 결과 없음");
//             return;
//         }

//         for (Map<String, String> result : searchResults) {
//             String url = result.get("url");
//             String title = result.get("title");

//             try {
//                 byte[] fileContent = restTemplate.getForObject(url, byte[].class);
                
//                 if (fileContent != null && fileContent.length > 0) {
//                     boolean isPdf = isPdfContent(fileContent);
//                     String ext = isPdf ? ".pdf" : ".txt";
//                     byte[] finalContent = isPdf ? fileContent : cleanHtmlToText(fileContent);

//                     String fileName = UUID.randomUUID().toString() + ext;
                    
//                     // S3 업로드
//                     String s3Path = s3Uploader.uploadFile(finalContent, fileName, category);
                    
//                     if (s3Path != null) {
//                         System.out.println("      ✅ S3 업로드: " + title);
//                     }
//                 }
//             } catch (Exception e) {
//                 System.err.println("      ❌ 실패: " + url);
//             }
//         }
//     }

//     // --- 관리자 기능 (CRUD) ---

//     public List<CrawlTarget> getAllTargets() {
//         return targetRepository.findAll();
//     }

//     public CrawlTarget addTarget(CrawlTarget target) {
//         return targetRepository.save(target);
//     }

//     public void deleteTarget(Long id) {
//         targetRepository.deleteById(id);
//     }

//     // --- Utils ---
//     private boolean isPdfContent(byte[] data) {
//         if (data.length < 4) return false;
//         return data[0] == 0x25 && data[1] == 0x50 && data[2] == 0x44 && data[3] == 0x46;
//     }

//     private byte[] cleanHtmlToText(byte[] htmlBytes) {
//         try {
//             String htmlString = new String(htmlBytes, StandardCharsets.UTF_8);
//             Document doc = Jsoup.parse(htmlString);
//             doc.select("script, style, header, footer, nav, noscript, iframe").remove();
//             return doc.text().getBytes(StandardCharsets.UTF_8);
//         } catch (Exception e) {
//             return htmlBytes;
//         }
//     }
// }


// package com.global17.auth_service.service;

// import com.global17.auth_service.dto.CrawlConfig;
// import com.global17.auth_service.util.S3Uploader;
// import com.global17.auth_service.util.TavilyClient;
// import lombok.RequiredArgsConstructor;
// import org.jsoup.Jsoup;
// import org.jsoup.nodes.Document;
// import org.springframework.stereotype.Service;
// import org.springframework.web.client.RestTemplate;
// import org.yaml.snakeyaml.DumperOptions;
// import org.yaml.snakeyaml.Yaml;

// import java.io.*;
// import java.nio.charset.StandardCharsets;
// import java.nio.file.Files;
// import java.nio.file.Paths;
// import java.util.*;

// @Service
// @RequiredArgsConstructor
// public class CrawlService {

//     private final TavilyClient tavilyClient;
//     private final S3Uploader s3Uploader;
//     private final RestTemplate restTemplate = new RestTemplate();

//     // 설정 파일 경로 (프로젝트 루트 기준)
//     private final String CONFIG_FILE_PATH = "config.yaml";

//     /**
//      * [배치 실행] config.yaml 파일에 있는 모든 대상을 크롤링
//      */
//     public void runBatchCrawling() {
//         System.out.println("🔄 [Batch] 파일 기반 일괄 크롤링 시작...");
        
//         CrawlConfig config = loadConfig();
//         if (config == null || config.getTargets() == null) {
//             System.out.println("⚠️ 설정 파일이 비어있거나 없습니다.");
//             return;
//         }

//         for (CrawlConfig.Target target : config.getTargets()) {
//             if (target.isEnabled()) {
//                 for (String keyword : target.getKeywords()) {
//                     processCrawling(target.getCountry(), target.getCode(), keyword, target.getCategory());
                    
//                     // API 호출 제한 고려 (딜레이)
//                     try { Thread.sleep(1000); } catch (InterruptedException e) {}
//                 }
//             }
//         }
//         System.out.println("🎉 [Batch] 크롤링 및 S3 업로드 완료!");
//     }

//     /**
//      * [단건 실행] 특정 키워드 크롤링 수행
//      */
//     public void processCrawling(String country, String countryCode, String keyword, String category) {
//         System.out.println("🚀 [" + country + "] 탐색: " + keyword);
        
//         String query = keyword;
//         if ("regulation".equalsIgnoreCase(category)) {
//              query += " filetype:pdf";
//         }

//         List<Map<String, String>> searchResults = tavilyClient.search(query);

//         if (searchResults.isEmpty()) {
//             System.out.println("   💨 검색 결과 없음");
//             return;
//         }

//         for (Map<String, String> result : searchResults) {
//             String url = result.get("url");
//             String title = result.get("title");

//             try {
//                 // 1. 다운로드
//                 byte[] fileContent = restTemplate.getForObject(url, byte[].class);
                
//                 if (fileContent != null && fileContent.length > 0) {
//                     // 2. 파일 형식 처리 (PDF vs HTML)
//                     boolean isPdf = isPdfContent(fileContent);
//                     String ext = isPdf ? ".pdf" : ".txt";
//                     byte[] finalContent = isPdf ? fileContent : cleanHtmlToText(fileContent);

//                     // 3. 파일명 생성 (UUID)
//                     String fileName = UUID.randomUUID().toString() + ext;
                    
//                     // 4. S3 업로드 (DB 저장 X)
//                     String s3Path = s3Uploader.uploadFile(finalContent, fileName, category);
                    
//                     if (s3Path != null) {
//                         System.out.println("   ✅ S3 업로드 완료: " + title);
//                         // DB 저장 로직 삭제됨 (요청 반영)
//                     }
//                 }
//             } catch (Exception e) {
//                 System.err.println("   ❌ 실패 (" + url + "): " + e.getMessage());
//             }
//         }
//     }

//     /**
//      * [설정 추가] config.yaml 파일에 새로운 타겟 추가
//      */
//     public void addTarget(CrawlConfig.Target newTarget) {
//         CrawlConfig config = loadConfig();
//         if (config == null) config = new CrawlConfig();
//         if (config.getTargets() == null) config.setTargets(new ArrayList<>());

//         config.getTargets().add(newTarget);
//         saveConfig(config);
//         System.out.println("📝 설정 파일 업데이트 완료: " + newTarget.getCountry());
//     }

//     /**
//      * [설정 조회] 현재 설정 목록 반환
//      */
//     public List<CrawlConfig.Target> getTargets() {
//         CrawlConfig config = loadConfig();
//         return config != null ? config.getTargets() : new ArrayList<>();
//     }

//     // --- 내부 유틸 메서드 ---

//     private CrawlConfig loadConfig() {
//         try {
//             File file = new File(CONFIG_FILE_PATH);
//             // 루트에 파일이 없으면 resources 내부 파일 읽기 시도 (읽기 전용)
//             if (!file.exists()) {
//                 InputStream is = getClass().getClassLoader().getResourceAsStream(CONFIG_FILE_PATH);
//                 if (is != null) {
//                     return new Yaml().loadAs(is, CrawlConfig.class);
//                 }
//                 return new CrawlConfig();
//             }
//             return new Yaml().loadAs(new FileInputStream(file), CrawlConfig.class);
//         } catch (Exception e) {
//             System.err.println("⚠️ 설정 로드 실패: " + e.getMessage());
//             return new CrawlConfig();
//         }
//     }

//     private void saveConfig(CrawlConfig config) {
//         try {
//             DumperOptions options = new DumperOptions();
//             options.setDefaultFlowStyle(DumperOptions.FlowStyle.BLOCK);
//             options.setPrettyFlow(true);
//             Yaml yaml = new Yaml(options);
            
//             FileWriter writer = new FileWriter(CONFIG_FILE_PATH);
//             yaml.dump(config, writer);
//             writer.close();
//         } catch (IOException e) {
//             throw new RuntimeException("설정 파일 저장 실패", e);
//         }
//     }

//     private boolean isPdfContent(byte[] data) {
//         if (data.length < 4) return false;
//         return data[0] == 0x25 && data[1] == 0x50 && data[2] == 0x44 && data[3] == 0x46;
//     }

//     private byte[] cleanHtmlToText(byte[] htmlBytes) {
//         try {
//             String htmlString = new String(htmlBytes, StandardCharsets.UTF_8);
//             Document doc = Jsoup.parse(htmlString);
//             doc.select("script, style, header, footer, nav, noscript, iframe").remove();
//             return doc.text().getBytes(StandardCharsets.UTF_8);
//         } catch (Exception e) {
//             return htmlBytes;
//         }
//     }
// }

// package com.global17.auth_service.service;

// import com.global17.auth_service.dto.CrawlConfig;
// import com.global17.auth_service.entity.Regulation;
// import com.global17.auth_service.repository.RegulationRepository;
// import com.global17.auth_service.util.S3Uploader;
// import com.global17.auth_service.util.TavilyClient;
// import lombok.RequiredArgsConstructor;
// import org.jsoup.Jsoup;
// import org.jsoup.nodes.Document;
// import org.springframework.core.io.ClassPathResource;
// import org.springframework.stereotype.Service;
// import org.springframework.web.client.RestTemplate;
// import org.yaml.snakeyaml.Yaml;

// import java.io.InputStream;
// import java.nio.charset.StandardCharsets;
// import java.time.LocalDate;
// import java.util.List;
// import java.util.Map;
// import java.util.UUID;

// @Service
// @RequiredArgsConstructor
// public class CrawlService {

//     private final TavilyClient tavilyClient;
//     private final S3Uploader s3Uploader;
//     private final RegulationRepository regulationRepository;
//     private final RestTemplate restTemplate = new RestTemplate();

//     // ... (runCrawling, runBatchCrawling 메서드는 기존과 동일하므로 생략) ...

//         // [기존] 단건 실행 메서드
//     public void runCrawling(String country, String countryCode, String keyword) {
//         // ... (기존 코드 유지) ...
//         System.out.println("🚀 [" + country + "] 단건 크롤링 시작: " + keyword);
//         processCrawling(country, countryCode, keyword, "regulation"); // 로직 분리
//     }

//     // [신규] 일괄 실행 메서드 (config.yaml 읽기)
//     public void runBatchCrawling() {
//         System.out.println("🔄 [Batch] config.yaml 기반 일괄 크롤링 시작...");

//         try {
//             // 1. resources/config.yaml 읽기
//             Yaml yaml = new Yaml();
//             ClassPathResource resource = new ClassPathResource("config.yaml");
//             InputStream inputStream = resource.getInputStream();
            
//             // 2. 객체로 변환
//             CrawlConfig config = yaml.loadAs(inputStream, CrawlConfig.class);

//             // 3. 반복문 실행
//             if (config != null && config.getTargets() != null) {
//                 for (CrawlConfig.Target target : config.getTargets()) {
//                     if (target.isEnabled()) {
//                         String country = target.getCountry();
//                         String code = target.getCode();
//                         String category = target.getCategory();

//                         for (String keyword : target.getKeywords()) {
//                             // 실제 크롤링 로직 호출
//                             processCrawling(country, code, keyword, category);
                            
//                             // 매너 딜레이 (2초)
//                             Thread.sleep(2000);
//                         }
//                     }
//                 }
//             }
//             System.out.println("🎉 [Batch] 모든 일괄 작업 완료!");

//         } catch (Exception e) {
//             System.err.println("❌ 설정 파일 로드 실패: " + e.getMessage());
//             e.printStackTrace();
//         }
//     }

//     // ... (processCrawling 메서드만 아래 내용으로 교체하세요) ...

//     private void processCrawling(String country, String countryCode, String keyword, String category) {
//         String query = keyword;
//         if ("regulation".equalsIgnoreCase(category)) {
//              query += " filetype:pdf";
//         }

//         List<Map<String, String>> searchResults = tavilyClient.search(query);

//         if (searchResults.isEmpty()) {
//             System.out.println("   💨 [" + country + "] 검색 결과 없음 (" + keyword + ")");
//             return;
//         }

//         for (Map<String, String> result : searchResults) {
//             String url = result.get("url");
//             String title = result.get("title");

//             try {
//                 // 1. 파일 다운로드 (바이너리)
//                 byte[] fileContent = restTemplate.getForObject(url, byte[].class);
                
//                 if (fileContent != null && fileContent.length > 0) {
                    
//                     // 2. 파일 형식 판별 (Magic Bytes & Parsing)
//                     boolean isPdf = isPdfContent(fileContent);
//                     String fileExtension;
//                     byte[] finalContent;

//                     if (isPdf) {
//                         // PDF는 그대로 저장
//                         fileExtension = ".pdf";
//                         finalContent = fileContent;
//                     } else {
//                         // HTML/Text는 정제(Cleaning) 후 저장
//                         fileExtension = ".txt";
//                         finalContent = cleanHtmlToText(fileContent); // [핵심 기능]
//                     }

//                     // 3. 파일명 생성
//                     String fileName = UUID.randomUUID().toString() + fileExtension;
                    
//                     // 4. S3 업로드
//                     String s3Path = s3Uploader.uploadFile(finalContent, fileName, category);

//                     // 5. DB 저장
//                     if (s3Path != null) {
//                         Regulation regulation = Regulation.builder()
//                                 .countryCode(countryCode)
//                                 .title(title)
//                                 .sourceId(99)
//                                 .status("active")
//                                 .createdAt(LocalDate.now())
//                                 .build();
                        
//                         regulationRepository.save(regulation);
//                         System.out.println("   ✅ 저장 완료(" + fileExtension + "): " + title);
//                     }
//                 }
//             } catch (Exception e) {
//                 System.err.println("   ❌ 실패: " + url + " (" + e.getMessage() + ")");
//             }
//         }
//     }

//     /**
//      * PDF 파일 시그니처(%PDF-) 확인
//      */
//     private boolean isPdfContent(byte[] data) {
//         if (data.length < 4) return false;
//         // %PDF (Hex: 25 50 44 46)
//         return data[0] == 0x25 && data[1] == 0x50 && data[2] == 0x44 && data[3] == 0x46;
//     }

//     /**
//      * HTML 바이트 배열을 받아서 깔끔한 텍스트 바이트 배열로 변환
//      */
//     private byte[] cleanHtmlToText(byte[] htmlBytes) {
//         try {
//             // 1. 바이트 -> 문자열 변환 (UTF-8 가정)
//             String htmlString = new String(htmlBytes, StandardCharsets.UTF_8);
            
//             // 2. Jsoup 파싱
//             Document doc = Jsoup.parse(htmlString);
            
//             // 3. 불필요한 요소 제거 (Script, Style, Nav, Footer 등)
//             doc.select("script, style, header, footer, nav, noscript, iframe").remove();
            
//             // 4. 순수 텍스트 추출 (줄바꿈 유지)
//             String cleanText = doc.text(); 
            
//             // 5. 텍스트 -> 바이트 변환
//             return cleanText.getBytes(StandardCharsets.UTF_8);
            
//         } catch (Exception e) {
//             System.err.println("⚠️ HTML 파싱 실패, 원본 저장: " + e.getMessage());
//             return htmlBytes; // 실패 시 원본 반환
//         }
//     }
// }

