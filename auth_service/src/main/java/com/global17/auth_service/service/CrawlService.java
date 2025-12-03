package com.global17.auth_service.service;

import com.global17.auth_service.dto.CrawlConfig;
import com.global17.auth_service.entity.Regulation;
import com.global17.auth_service.repository.RegulationRepository;
import com.global17.auth_service.util.S3Uploader;
import com.global17.auth_service.util.TavilyClient;
import lombok.RequiredArgsConstructor;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class CrawlService {

    private final TavilyClient tavilyClient;
    private final S3Uploader s3Uploader;
    private final RegulationRepository regulationRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    // ... (runCrawling, runBatchCrawling 메서드는 기존과 동일하므로 생략) ...

        // [기존] 단건 실행 메서드
    public void runCrawling(String country, String countryCode, String keyword) {
        // ... (기존 코드 유지) ...
        System.out.println("🚀 [" + country + "] 단건 크롤링 시작: " + keyword);
        processCrawling(country, countryCode, keyword, "regulation"); // 로직 분리
    }

    // [신규] 일괄 실행 메서드 (config.yaml 읽기)
    public void runBatchCrawling() {
        System.out.println("🔄 [Batch] config.yaml 기반 일괄 크롤링 시작...");

        try {
            // 1. resources/config.yaml 읽기
            Yaml yaml = new Yaml();
            ClassPathResource resource = new ClassPathResource("config.yaml");
            InputStream inputStream = resource.getInputStream();
            
            // 2. 객체로 변환
            CrawlConfig config = yaml.loadAs(inputStream, CrawlConfig.class);

            // 3. 반복문 실행
            if (config != null && config.getTargets() != null) {
                for (CrawlConfig.Target target : config.getTargets()) {
                    if (target.isEnabled()) {
                        String country = target.getCountry();
                        String code = target.getCode();
                        String category = target.getCategory();

                        for (String keyword : target.getKeywords()) {
                            // 실제 크롤링 로직 호출
                            processCrawling(country, code, keyword, category);
                            
                            // 매너 딜레이 (2초)
                            Thread.sleep(2000);
                        }
                    }
                }
            }
            System.out.println("🎉 [Batch] 모든 일괄 작업 완료!");

        } catch (Exception e) {
            System.err.println("❌ 설정 파일 로드 실패: " + e.getMessage());
            e.printStackTrace();
        }
    }

    // ... (processCrawling 메서드만 아래 내용으로 교체하세요) ...

    private void processCrawling(String country, String countryCode, String keyword, String category) {
        String query = keyword;
        if ("regulation".equalsIgnoreCase(category)) {
             query += " filetype:pdf";
        }

        List<Map<String, String>> searchResults = tavilyClient.search(query);

        if (searchResults.isEmpty()) {
            System.out.println("   💨 [" + country + "] 검색 결과 없음 (" + keyword + ")");
            return;
        }

        for (Map<String, String> result : searchResults) {
            String url = result.get("url");
            String title = result.get("title");

            try {
                // 1. 파일 다운로드 (바이너리)
                byte[] fileContent = restTemplate.getForObject(url, byte[].class);
                
                if (fileContent != null && fileContent.length > 0) {
                    
                    // 2. 파일 형식 판별 (Magic Bytes & Parsing)
                    boolean isPdf = isPdfContent(fileContent);
                    String fileExtension;
                    byte[] finalContent;

                    if (isPdf) {
                        // PDF는 그대로 저장
                        fileExtension = ".pdf";
                        finalContent = fileContent;
                    } else {
                        // HTML/Text는 정제(Cleaning) 후 저장
                        fileExtension = ".txt";
                        finalContent = cleanHtmlToText(fileContent); // [핵심 기능]
                    }

                    // 3. 파일명 생성
                    String fileName = UUID.randomUUID().toString() + fileExtension;
                    
                    // 4. S3 업로드
                    String s3Path = s3Uploader.uploadFile(finalContent, fileName, category);

                    // 5. DB 저장
                    if (s3Path != null) {
                        Regulation regulation = Regulation.builder()
                                .countryCode(countryCode)
                                .title(title)
                                .sourceId(99)
                                .status("active")
                                .createdAt(LocalDate.now())
                                .build();
                        
                        regulationRepository.save(regulation);
                        System.out.println("   ✅ 저장 완료(" + fileExtension + "): " + title);
                    }
                }
            } catch (Exception e) {
                System.err.println("   ❌ 실패: " + url + " (" + e.getMessage() + ")");
            }
        }
    }

    /**
     * PDF 파일 시그니처(%PDF-) 확인
     */
    private boolean isPdfContent(byte[] data) {
        if (data.length < 4) return false;
        // %PDF (Hex: 25 50 44 46)
        return data[0] == 0x25 && data[1] == 0x50 && data[2] == 0x44 && data[3] == 0x46;
    }

    /**
     * HTML 바이트 배열을 받아서 깔끔한 텍스트 바이트 배열로 변환
     */
    private byte[] cleanHtmlToText(byte[] htmlBytes) {
        try {
            // 1. 바이트 -> 문자열 변환 (UTF-8 가정)
            String htmlString = new String(htmlBytes, StandardCharsets.UTF_8);
            
            // 2. Jsoup 파싱
            Document doc = Jsoup.parse(htmlString);
            
            // 3. 불필요한 요소 제거 (Script, Style, Nav, Footer 등)
            doc.select("script, style, header, footer, nav, noscript, iframe").remove();
            
            // 4. 순수 텍스트 추출 (줄바꿈 유지)
            String cleanText = doc.text(); 
            
            // 5. 텍스트 -> 바이트 변환
            return cleanText.getBytes(StandardCharsets.UTF_8);
            
        } catch (Exception e) {
            System.err.println("⚠️ HTML 파싱 실패, 원본 저장: " + e.getMessage());
            return htmlBytes; // 실패 시 원본 반환
        }
    }
}

