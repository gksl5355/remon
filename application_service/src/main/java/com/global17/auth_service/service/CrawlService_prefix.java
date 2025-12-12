package com.global17.auth_service.service;

import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.ListObjectsV2Request;
import com.amazonaws.services.s3.model.ListObjectsV2Result;
import com.amazonaws.services.s3.model.ObjectMetadata;
import com.amazonaws.services.s3.model.S3ObjectSummary;
import com.global17.auth_service.entity.CrawlTarget;
import com.global17.auth_service.repository.CrawlTargetRepository;
import com.global17.auth_service.util.TavilyClient;
import lombok.RequiredArgsConstructor;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class CrawlService_prefix {

    private final TavilyClient tavilyClient;
    private final AmazonS3 amazonS3; 
    private final CrawlTargetRepository targetRepository;
    
    private final RestTemplate restTemplate = new RestTemplate();
    private final Random random = new Random();

    @Value("${aws.s3.target-arn}")
    private String bucket;

    @Value("${aws.s3.base-prefix}")
    private String basePrefix;

    @Value("${aws.s3.app-prefix}")
    private String appPrefix;

    // ==========================================
    // 1. 크롤링 실행 로직 (Main)
    // ==========================================
    public void runBatchCrawling() {
        System.out.println("🔄 [Versioning Mode] S3 버저닝 기반 크롤링 시작 (FDA 패치 + 옵션 적용)...");
        List<CrawlTarget> targets = targetRepository.findByEnabledTrue();
        
        if (targets.isEmpty()) {
            System.out.println("⚠️ 활성화된 타겟이 없습니다.");
            return;
        }

        for (CrawlTarget target : targets) {
            String label = (target.getTitle() != null) ? target.getTitle() : target.getCountry();
            System.out.println("👉 Target: " + label);
            
            for (String keyword : target.getKeywords()) {
                // 개별 키워드 검색 수행
                processCrawling(target, keyword);
                
                // [속도 조절] Tavily API Rate Limit 방지 (15초 이상)
                randomSleep(15000, 20000);
            }
        }
        System.out.println("🎉 [Batch] 완료!");
    }

    private void processCrawling(CrawlTarget target, String keyword) {
        System.out.println("   🚀 탐색: " + keyword);
        
        // --- 1. 검색어 동적 조립 (프론트엔드 연동) ---
        StringBuilder queryBuilder = new StringBuilder(keyword);

        // (A) 도메인 필터 (site:govinfo.gov)
        if (target.getTargetDomain() != null && !target.getTargetDomain().isEmpty()) {
            queryBuilder.append(" site:").append(target.getTargetDomain());
        }

        // (B) 날짜 필터 (after:YYYY-MM-DD)
        if (target.getBaseDate() != null) {
            queryBuilder.append(" after:").append(target.getBaseDate().toString());
        } else {
            // 기본값: 100일 전
            String defaultDate = LocalDate.now().minusDays(100).toString();
            queryBuilder.append(" after:").append(defaultDate);
        }

        // (C) 파일 포맷
        String format = "pdf"; // 기본값
        if (target.getDocumentFormat() != null && !target.getDocumentFormat().isEmpty()) {
            format = target.getDocumentFormat();
        }
        if (isRegulation(target.getCategory()) || target.getDocumentFormat() != null) {
             queryBuilder.append(" filetype:").append(format);
        }

        String query = queryBuilder.toString();
        // System.out.println("      🔎 Query: " + query);

        // --- 2. API 호출 ---
        List<Map<String, String>> searchResults = tavilyClient.search(query);
        if (searchResults.isEmpty()) {
            System.out.println("      💨 결과 없음");
            return;
        }

        // --- 3. 다운로드 및 처리 ---
        for (Map<String, String> result : searchResults) {
            String rawUrl = result.get("url");
            String title = result.get("title"); 

            // 사람처럼 보이기 위한 딜레이 (FDA 보안 우회용)
            randomSleep(3000, 6000); 

            try {
                URI safeUri = encodeUrl(rawUrl);
                
                // [중요] FDA 접속을 위한 강력한 헤더 및 쿠키 적용
                HttpHeaders requestHeaders = createBrowserHeaders();
                HttpEntity<String> entity = new HttpEntity<>(requestHeaders);

                ResponseEntity<byte[]> response = restTemplate.exchange(
                        safeUri, HttpMethod.GET, entity, byte[].class
                );
                
                byte[] fileContent = response.getBody();
                HttpHeaders responseHeaders = response.getHeaders();

                if (fileContent != null && fileContent.length > 2000) {
                    boolean isPdf = isPdfContent(fileContent);
                    String ext = isPdf ? ".pdf" : "." + format;

                    // 실제 파일명 추출 (헤더 -> URL -> 제목 순)
                    String realFileName = extractRealFileName(responseHeaders, rawUrl, title, ext);
                    
                    // 경로 조립
                    String fullKey = buildFullPath(target.getCategory(), target.getCode(), realFileName);

                    // 중복 체크 (ETag 비교)
                    if (isSameContentExists(fullKey, fileContent)) {
                        System.out.println("      ⏭️ 변경 없음(Skip): " + realFileName);
                        continue;
                    }
                    
                    byte[] finalContent = isPdf ? fileContent : cleanHtmlToText(fileContent);
                    // 5단계 날짜 추출 로직 적용
                    String publishDate = resolvePublishDate(result, rawUrl, finalContent, isPdf, responseHeaders);

                    uploadToS3(fullKey, fileContent, isPdf, publishDate, rawUrl);
                    System.out.println("      ✅ S3 업데이트: " + fullKey);

                } else {
                    System.out.println("      ⚠️ 파일 작음/차단 -> Skip");
                }

            } catch (org.springframework.web.client.HttpClientErrorException.NotFound e) {
                System.out.println("      ⚠️ 페이지 없음(404 Fake) - FDA 등 보안 사이트일 가능성: " + rawUrl);
            } catch (org.springframework.web.client.HttpClientErrorException.Forbidden e) {
                System.err.println("      ⛔ 접근 차단(403) - 헤더/쿠키 보완 필요: " + rawUrl);
            } catch (Exception e) {
                System.err.println("      ❌ 실패: " + rawUrl + " -> " + e.toString());
            }
        }
    }

    // ==========================================
    // 2. [핵심] 보안 헤더 및 쿠키 설정 (FDA 대응)
    // ==========================================
    private HttpHeaders createBrowserHeaders() {
        HttpHeaders headers = new HttpHeaders();
        
        // 1. 최신 크롬 User-Agent
        headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36");
        
        // 2. Accept
        headers.set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7");
        
        // 3. 언어
        headers.set("Accept-Language", "en-US,en;q=0.9,ko;q=0.8");
        headers.set("Accept-Encoding", "gzip, deflate, br"); 
        
        // 4. Client Hints (봇 탐지 회피 필수)
        headers.set("Sec-Ch-Ua", "\"Chromium\";v=\"122\", \"Not(A:Brand\";v=\"24\", \"Google Chrome\";v=\"122\"");
        headers.set("Sec-Ch-Ua-Mobile", "?0");
        headers.set("Sec-Ch-Ua-Platform", "\"Windows\"");
        headers.set("Sec-Fetch-Dest", "document");
        headers.set("Sec-Fetch-Mode", "navigate");
        headers.set("Sec-Fetch-Site", "none"); 
        headers.set("Sec-Fetch-User", "?1");
        headers.set("Upgrade-Insecure-Requests", "1");
        headers.set("Connection", "keep-alive");
        
        // 5. [필수] Referer & Cookie (FDA 접속 성공의 열쇠)
        headers.set("Referer", "https://www.google.com/");
        
        // ★★★ 여기에 브라우저에서 딴 쿠키를 넣으세요 ★★★
        headers.set("Cookie", "SSESS...=...; TS01...=..."); 

        return headers;
    }

    // ==========================================
    // 3. 데이터 관리 (CRUD) - 프론트엔드 연동
    // ==========================================

    public List<CrawlTarget> getAllTargets() { 
        return targetRepository.findAll(); 
    }

    public CrawlTarget addTarget(CrawlTarget target) {
        normalizeTargetData(target);
        return targetRepository.save(target);
    }

    @Transactional
    public CrawlTarget patchTarget(Long id, CrawlTarget source) {
        CrawlTarget target = targetRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Target ID not found: " + id));

        if (source.getTitle() != null) target.setTitle(source.getTitle());
        if (source.getCountry() != null) target.setCountry(source.getCountry());
        if (source.getCode() != null) target.setCode(source.getCode());
        if (source.getCategory() != null) target.setCategory(source.getCategory());
        if (source.getTypeLabel() != null) target.setTypeLabel(source.getTypeLabel());
        target.setEnabled(source.isEnabled()); 
        
        if (source.getTargetDomain() != null) target.setTargetDomain(source.getTargetDomain());
        if (source.getDocumentFormat() != null) target.setDocumentFormat(source.getDocumentFormat());
        if (source.getBaseDate() != null) target.setBaseDate(source.getBaseDate());
        if (source.getTargetUrl() != null) target.setTargetUrl(source.getTargetUrl());

        if (source.getKeywords() != null) {
            target.getKeywords().clear();
            target.getKeywords().addAll(source.getKeywords());
        }
        normalizeTargetData(target);
        return target;
    }

    public void deleteTarget(Long id) { targetRepository.deleteById(id); }
    public CrawlTarget updateTarget(Long id, CrawlTarget updatedInfo) { return patchTarget(id, updatedInfo); }
    public void updateTargetStatus(Long id, boolean enabled) {
        CrawlTarget target = targetRepository.findById(id).orElseThrow();
        target.setEnabled(enabled);
        targetRepository.save(target);
    }

    private void normalizeTargetData(CrawlTarget target) {
        if (target.getCode() == null || target.getCode().isEmpty()) target.setCode(target.getCountry());
        if ("reg".equalsIgnoreCase(target.getCategory())) target.setCategory("regulation");
        if (target.getTitle() == null || target.getTitle().isEmpty()) {
            String type = (target.getTypeLabel() != null) ? target.getTypeLabel() : target.getCategory();
            target.setTitle(target.getCountry() + " " + type + " Crawler");
        }
    }
    
    private boolean isRegulation(String category) {
        return "regulation".equalsIgnoreCase(category) || "reg".equalsIgnoreCase(category);
    }

    // ==========================================
    // 4. 유틸리티 (S3, 파일명, 날짜 등)
    // ==========================================

    private boolean isSameContentExists(String key, byte[] newContent) {
        try {
            if (!amazonS3.doesObjectExist(bucket, key)) return false;
            ObjectMetadata metadata = amazonS3.getObjectMetadata(bucket, key);
            String existingETag = metadata.getETag().replace("\"", "");
            String newMD5 = calculateMD5(newContent);
            return existingETag.equalsIgnoreCase(newMD5);
        } catch (Exception e) { return false; }
    }

    private void uploadToS3(String key, byte[] content, boolean isPdf, String date, String url) {
        ObjectMetadata metadata = new ObjectMetadata();
        metadata.setContentLength(content.length);
        metadata.setContentType(isPdf ? "application/pdf" : "text/plain");
        metadata.addUserMetadata("original-date", date);
        metadata.addUserMetadata("source-url", url);
        amazonS3.putObject(bucket, key, new ByteArrayInputStream(content), metadata);
    }

    private String calculateMD5(byte[] content) {
        try {
            StringBuilder sb = new StringBuilder();
            for (byte b : MessageDigest.getInstance("MD5").digest(content)) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    private String buildFullPath(String category, String countryCode, String fileName) {
        StringBuilder path = new StringBuilder();
        if (basePrefix != null && !basePrefix.isEmpty()) path.append(basePrefix).append("/");
        if (appPrefix != null && !appPrefix.isEmpty()) path.append(appPrefix).append("/");
        path.append(category).append("/").append(countryCode).append("/").append(fileName);
        return path.toString();
    }

    private String extractRealFileName(HttpHeaders headers, String fileUrl, String fallbackTitle, String defaultExt) {
        String filename = null;
        try {
            ContentDisposition contentDisposition = headers.getContentDisposition();
            if (contentDisposition != null && contentDisposition.getFilename() != null) filename = contentDisposition.getFilename();
        } catch (Exception ignored) {}
        if (filename == null || filename.isEmpty()) {
            try {
                String path = new URL(fileUrl).getPath();
                if (path != null && path.contains("/")) {
                    filename = path.substring(path.lastIndexOf("/") + 1);
                    filename = URLDecoder.decode(filename, StandardCharsets.UTF_8.name());
                }
            } catch (Exception ignored) {}
        }
        if (filename == null || filename.trim().length() < 3) filename = cleanFileName(fallbackTitle);
        filename = sanitizeFileName(filename);
        if (!filename.toLowerCase().endsWith(defaultExt)) filename += defaultExt;
        return filename;
    }

    private String sanitizeFileName(String name) {
        String safeName = name.replaceAll("[\\\\/:*?\"<>|]", "_").trim().replaceAll("\\s+", "_");
        if (safeName.length() > 200) safeName = safeName.substring(0, 200);
        return safeName;
    }
    private String cleanFileName(String title) { return sanitizeFileName(title); }
    private void randomSleep(int min, int max) { try { Thread.sleep(random.nextInt(max - min + 1) + min); } catch (Exception e) {} }
    private URI encodeUrl(String urlStr) throws Exception {
        String decoded = URLDecoder.decode(urlStr, StandardCharsets.UTF_8.name());
        URL url = new URL(decoded);
        return new URI(url.getProtocol(), url.getUserInfo(), url.getHost(), url.getPort(), url.getPath(), url.getQuery(), null);
    }
    private boolean isPdfContent(byte[] data) { return data.length > 4 && data[0]==0x25 && data[1]==0x50 && data[2]==0x44; }
    private byte[] cleanHtmlToText(byte[] b) { try { return Jsoup.parse(new String(b, StandardCharsets.UTF_8)).text().getBytes(StandardCharsets.UTF_8); } catch(Exception e){return b;} }

    // 날짜 추출 5단계 방어 로직
    private String resolvePublishDate(Map<String, String> searchResult, String url, byte[] fileContent, boolean isPdf, HttpHeaders headers) {
        String foundDate = extractDateFromUrl(url);
        if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
        if (searchResult.get("published_date") != null) foundDate = searchResult.get("published_date");
        if (foundDate == null && searchResult.get("date") != null) foundDate = searchResult.get("date");
        if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
        if (!isPdf) {
            try {
                String html = new String(fileContent, StandardCharsets.UTF_8);
                Document doc = Jsoup.parse(html);
                foundDate = extractDateFromJsonLd(doc);
                if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
                foundDate = extractDateFromMetaTags(doc);
                if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
                foundDate = extractDateFromDomElements(doc);
                if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
                foundDate = findDatePatternInText(doc.text().substring(0, Math.min(doc.text().length(), 3000)));
                if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
            } catch (Exception ignored) {}
        }
        if (headers.getLastModified() > 0) {
            try {
                foundDate = java.time.Instant.ofEpochMilli(headers.getLastModified()).atZone(ZoneId.of("UTC")).toLocalDate().format(DateTimeFormatter.ISO_DATE);
                if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
            } catch (Exception ignored) {}
        }
        if (searchResult.get("content") != null) foundDate = findDatePatternInText(searchResult.get("content"));
        return formatDateToYYYYMMDD(foundDate);
    }
    private String extractDateFromJsonLd(Document doc) {
        Elements scripts = doc.select("script[type=application/ld+json]");
        for (Element script : scripts) {
            String json = script.html();
            Pattern p = Pattern.compile("\"datePublished\"\\s*:\\s*\"([^\"]+)\"");
            Matcher m = p.matcher(json); if (m.find()) return m.group(1);
            Pattern p2 = Pattern.compile("\"dateModified\"\\s*:\\s*\"([^\"]+)\"");
            Matcher m2 = p2.matcher(json); if (m2.find()) return m2.group(1);
        }
        return null;
    }
    private String extractDateFromMetaTags(Document doc) {
        String[] metaNames = { "article:published_time", "article:modified_time", "date", "pubdate", "publish_date", "created_at", "og:updated_time", "regDate" };
        for (String name : metaNames) {
            Element meta = doc.selectFirst("meta[name='" + name + "']");
            if (meta == null) meta = doc.selectFirst("meta[property='" + name + "']");
            if (meta != null && !meta.attr("content").isEmpty()) return meta.attr("content");
        }
        return null;
    }
    private String extractDateFromDomElements(Document doc) {
        String[] selectors = { ".date", ".pubDate", ".published", ".time", "#date", ".reg-date" };
        for (String selector : selectors) {
            Elements elements = doc.select(selector);
            for (Element el : elements) {
                String date = findDatePatternInText(el.text());
                if (date != null) return date;
            }
        }
        return null;
    }
    private String extractDateFromUrl(String url) {
        if (url == null) return null;
        try { url = URLDecoder.decode(url, StandardCharsets.UTF_8.name()); } catch(Exception e) {}
        Pattern pattern = Pattern.compile("(20\\d{2})[-./]?(0[1-9]|1[0-2])[-./]?(0[1-9]|[12]\\d|3[01])");
        Matcher matcher = pattern.matcher(url);
        if (matcher.find()) return matcher.group(0);
        return null;
    }
    private String findDatePatternInText(String text) {
        if (text == null) return null;
        Pattern p1 = Pattern.compile("20\\d{2}[-./](0[1-9]|1[0-2])[-./](0[1-9]|[12]\\d|3[01])");
        Matcher m1 = p1.matcher(text);
        if (m1.find()) return m1.group(0);
        Pattern p2 = Pattern.compile("20\\d{2}년\\s*(0?[1-9]|1[0-2])월\\s*(0?[1-9]|[12]\\d|3[01])일");
        Matcher m2 = p2.matcher(text);
        if (m2.find()) return m2.group(0);
        return null;
    }
    private String formatDateToYYYYMMDD(String rawDate) {
        if (rawDate == null || rawDate.trim().isEmpty()) return LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
        try {
            String cleanDate = rawDate.replaceAll("[^0-9]", " ").trim();
            String[] parts = cleanDate.split("\\s+");
            if (parts.length >= 3) {
                int y = Integer.parseInt(parts[0]);
                int m = Integer.parseInt(parts[1]);
                int d = Integer.parseInt(parts[2]);
                if (y < 100) y += 2000;
                return String.format("%04d%02d%02d", y, m, d);
            }
            String numbersOnly = rawDate.replaceAll("[^0-9]", "");
            if (numbersOnly.length() >= 8) return numbersOnly.substring(0, 8);
            return LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
        } catch (Exception e) {
            return LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
        }
    }
}

