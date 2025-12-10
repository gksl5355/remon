package com.global17.auth_service.service;

import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.ObjectMetadata;
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

    // --- 실행 로직 ---

    public void runBatchCrawling() {
        System.out.println("🔄 [Versioning Mode] S3 버저닝 기반 크롤링 시작...");
        List<CrawlTarget> targets = targetRepository.findByEnabledTrue();
        if (targets.isEmpty()) {
            System.out.println("⚠️ 활성화된 타겟이 없습니다.");
            return;
        }

        for (CrawlTarget target : targets) {
            System.out.println("👉 Target: " + target.getCountry());
            for (String keyword : target.getKeywords()) {
                processCrawling(target.getCountry(), target.getCode(), keyword, target.getCategory());
                randomSleep(3000, 5000);
            }
        }
        System.out.println("🎉 [Batch] 완료!");
    }

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
            String rawUrl = result.get("url");
            String title = result.get("title"); // 검색 제목 (Fallback용)

            randomSleep(2000, 4000);

            try {
                URI safeUri = encodeUrl(rawUrl);
                HttpHeaders requestHeaders = createBrowserHeaders();
                HttpEntity<String> entity = new HttpEntity<>(requestHeaders);

                ResponseEntity<byte[]> response = restTemplate.exchange(
                        safeUri, HttpMethod.GET, entity, byte[].class
                );
                
                byte[] fileContent = response.getBody();
                HttpHeaders responseHeaders = response.getHeaders();

                if (fileContent != null && fileContent.length > 2000) {
                    boolean isPdf = isPdfContent(fileContent);
                    String ext = isPdf ? ".pdf" : ".txt";

                    // [핵심 수정] 실제 파일명 추출 (Header -> URL -> Title 순서)
                    String realFileName = extractRealFileName(responseHeaders, rawUrl, title, ext);

                    // S3 전체 경로 조립
                    String fullKey = buildFullPath(category, countryCode, realFileName);

                    // [중복 체크]
                    if (isSameContentExists(fullKey, fileContent)) {
                        System.out.println("      ⏭️ 변경 없음(Skip): " + realFileName + " [URL: " + rawUrl + "]");
                        continue;
                    }
                    
                    byte[] finalContent = isPdf ? fileContent : cleanHtmlToText(fileContent);
                    String publishDate = resolvePublishDate(result, rawUrl, finalContent, isPdf, responseHeaders);

                    uploadToS3(fullKey, fileContent, isPdf, publishDate, rawUrl);
                    
                    System.out.println("      ✅ S3 업데이트: " + fullKey + " [URL: " + rawUrl + "]");

                } else {
                    System.out.println("      ⚠️ 파일 작음/차단 -> Skip [URL: " + rawUrl + "]");
                }
            } catch (Exception e) {
                System.err.println("      ❌ 실패: " + rawUrl + " -> " + e.toString());
            }
        }
    }

    // --- [신규 메서드] 실제 파일명 추출 로직 ---
    private String extractRealFileName(HttpHeaders headers, String fileUrl, String fallbackTitle, String defaultExt) {
        String filename = null;

        // 1. Content-Disposition 헤더 확인 (가장 정확)
        try {
            ContentDisposition contentDisposition = headers.getContentDisposition();
            if (contentDisposition != null && contentDisposition.getFilename() != null) {
                filename = contentDisposition.getFilename();
                // 인코딩된 파일명이 있을 경우 디코딩 시도 (UTF-8 등)
                if (contentDisposition.getFilename() == null && headers.getFirst("Content-Disposition") != null) {
                     String rawHeader = headers.getFirst("Content-Disposition");
                     // 단순 정규식으로 filename="abc.pdf" 추출 시도
                     Pattern p = Pattern.compile("filename=\"?([^;\"]+)\"?");
                     Matcher m = p.matcher(rawHeader);
                     if (m.find()) filename = m.group(1);
                }
            }
        } catch (Exception ignored) {}

        // 2. URL 경로에서 추출 (http://site.com/data/report_2024.pdf -> report_2024.pdf)
        if (filename == null || filename.isEmpty()) {
            try {
                String path = new URL(fileUrl).getPath();
                if (path != null && path.contains("/")) {
                    filename = path.substring(path.lastIndexOf("/") + 1);
                    // URL 디코딩 (%20 -> 공백)
                    filename = URLDecoder.decode(filename, StandardCharsets.UTF_8.name());
                }
            } catch (Exception ignored) {}
        }

        // 3. 파일명이 너무 짧거나 없으면 제목(Fallback) 사용
        if (filename == null || filename.trim().length() < 3) {
            filename = cleanFileName(fallbackTitle);
        }

        // 4. 최종 정제 (확장자 처리 및 특수문자 제거)
        filename = sanitizeFileName(filename);

        // 확장자가 없으면 붙여줌
        if (!filename.toLowerCase().endsWith(defaultExt)) {
            filename += defaultExt;
        }

        return filename;
    }

    // 파일명 특수문자 제거 및 길이 제한
    private String sanitizeFileName(String name) {
        // 윈도우/리눅스 파일명 금지 문자 제거
        String safeName = name.replaceAll("[\\\\/:*?\"<>|]", "_");
        // 공백을 언더바로
        safeName = safeName.trim().replaceAll("\\s+", "_");
        
        // 길이가 너무 길면 자름 (S3 제한 고려)
        if (safeName.length() > 200) {
            String ext = "";
            int dotIndex = safeName.lastIndexOf(".");
            if (dotIndex > 0) {
                ext = safeName.substring(dotIndex);
                safeName = safeName.substring(0, 200) + ext;
            } else {
                safeName = safeName.substring(0, 200);
            }
        }
        return safeName;
    }

    // --- 경로 조립기 ---
    private String buildFullPath(String category, String countryCode, String fileName) {
        StringBuilder path = new StringBuilder();
        if (basePrefix != null && !basePrefix.isEmpty()) path.append(basePrefix).append("/");
        if (appPrefix != null && !appPrefix.isEmpty()) path.append(appPrefix).append("/");
        path.append(category).append("/").append(countryCode).append("/").append(fileName);
        return path.toString();
    }

    // --- S3 관련 핵심 로직 ---

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
            for (byte b : MessageDigest.getInstance("MD5").digest(content)) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    // --- 유틸 메서드 ---
    
    // (기존 cleanFileName은 sanitizeFileName으로 대체됨, 제목 폴백용으로 유지)
    private String cleanFileName(String title) {
        return sanitizeFileName(title);
    }

    private HttpHeaders createBrowserHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
        headers.set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8");
        headers.set("Accept-Language", "en-US,en;q=0.9,ko;q=0.8");
        headers.set("Referer", "https://www.google.com/");
        headers.set("Connection", "keep-alive");
        return headers;
    }
    
    private void randomSleep(int min, int max) {
        try { Thread.sleep(random.nextInt(max - min + 1) + min); } catch (Exception e) {}
    }
    
    private URI encodeUrl(String urlStr) throws Exception {
        String decoded = URLDecoder.decode(urlStr, StandardCharsets.UTF_8.name());
        URL url = new URL(decoded);
        return new URI(url.getProtocol(), url.getUserInfo(), url.getHost(), url.getPort(), url.getPath(), url.getQuery(), null);
    }
    
    private boolean isPdfContent(byte[] data) {
        return data.length > 4 && data[0]==0x25 && data[1]==0x50 && data[2]==0x44;
    }

    // 날짜 추출 메서드
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
    
    // 날짜 세부 추출기
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
    private byte[] cleanHtmlToText(byte[] b) { try { return Jsoup.parse(new String(b, StandardCharsets.UTF_8)).text().getBytes(StandardCharsets.UTF_8); } catch(Exception e){return b;} }

    // CRUD 메서드 (TargetController 호환용)
    public List<CrawlTarget> getAllTargets() { return targetRepository.findAll(); }
    public CrawlTarget addTarget(CrawlTarget target) { return targetRepository.save(target); }
    public void deleteTarget(Long id) { targetRepository.deleteById(id); }
    public CrawlTarget updateTarget(Long id, CrawlTarget updatedInfo) {
        CrawlTarget target = targetRepository.findById(id).orElseThrow();
        target.setCountry(updatedInfo.getCountry());
        target.setCode(updatedInfo.getCode());
        target.setCategory(updatedInfo.getCategory());
        target.setEnabled(updatedInfo.isEnabled());
        if (target.getKeywords() != null) target.getKeywords().clear();
        if (updatedInfo.getKeywords() != null) target.getKeywords().addAll(updatedInfo.getKeywords());
        return targetRepository.save(target);
    }
    public void updateTargetStatus(Long id, boolean enabled) {
        CrawlTarget target = targetRepository.findById(id).orElseThrow();
        target.setEnabled(enabled);
        targetRepository.save(target);
    }
}

