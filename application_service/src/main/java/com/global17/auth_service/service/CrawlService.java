// package com.global17.auth_service.service;

// import com.amazonaws.services.s3.AmazonS3;
// import com.amazonaws.services.s3.model.ListObjectsV2Request;
// import com.amazonaws.services.s3.model.ListObjectsV2Result;
// import com.amazonaws.services.s3.model.S3ObjectSummary;
// import com.global17.auth_service.entity.CrawlTarget;
// import com.global17.auth_service.repository.CrawlTargetRepository;
// import com.global17.auth_service.util.S3Uploader;
// import com.global17.auth_service.util.TavilyClient;
// import lombok.RequiredArgsConstructor;
// import org.jsoup.Jsoup;
// import org.jsoup.nodes.Document;
// import org.jsoup.nodes.Element;
// import org.jsoup.select.Elements;
// import org.springframework.beans.factory.annotation.Value;
// import org.springframework.http.HttpEntity;
// import org.springframework.http.HttpHeaders;
// import org.springframework.http.HttpMethod;
// import org.springframework.http.ResponseEntity;
// import org.springframework.stereotype.Service;
// import org.springframework.web.client.RestTemplate;

// import java.net.URI;
// import java.net.URL;
// import java.net.URLDecoder;
// import java.nio.charset.StandardCharsets;
// import java.security.MessageDigest;
// import java.time.LocalDate;
// import java.time.ZoneId;
// import java.time.format.DateTimeFormatter;
// import java.util.List;
// import java.util.Map;
// import java.util.Random;
// import java.util.regex.Matcher;
// import java.util.regex.Pattern;

// @Service
// @RequiredArgsConstructor
// public class CrawlService {

//     private final TavilyClient tavilyClient;
//     private final S3Uploader s3Uploader;
//     private final CrawlTargetRepository targetRepository;
//     private final AmazonS3 amazonS3; 
    
//     private final RestTemplate restTemplate = new RestTemplate();
//     private final Random random = new Random();

//     @Value("${aws.s3.target-arn}")
//     private String bucket;

//     // --- 실행 로직 ---

//     public void runBatchCrawling() {
//         System.out.println("🔄 [Normal Mode] DB 기반 일괄 크롤링 시작...");
//         List<CrawlTarget> targets = targetRepository.findByEnabledTrue();
//         if (targets.isEmpty()) {
//             System.out.println("⚠️ 활성화된 타겟이 없습니다.");
//             return;
//         }

//         for (CrawlTarget target : targets) {
//             System.out.println("👉 Target: " + target.getCountry());
//             for (String keyword : target.getKeywords()) {
//                 processCrawling(target.getCountry(), target.getCode(), keyword, target.getCategory());
//                 randomSleep(3000, 5000);
//             }
//         }
//         System.out.println("🎉 [Batch] 완료!");
//     }

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
//             String rawUrl = result.get("url");
//             String title = result.get("title");

//             randomSleep(2000, 4000);

//             try {
//                 // 1. URL 안전 인코딩
//                 URI safeUri = encodeUrl(rawUrl);

//                 // 2. 브라우저 헤더 위장
//                 HttpHeaders requestHeaders = createBrowserHeaders();
//                 HttpEntity<String> entity = new HttpEntity<>(requestHeaders);

//                 // 3. 파일 다운로드
//                 ResponseEntity<byte[]> response = restTemplate.exchange(
//                         safeUri, HttpMethod.GET, entity, byte[].class
//                 );
                
//                 byte[] fileContent = response.getBody();
//                 HttpHeaders responseHeaders = response.getHeaders();
                
//                 if (fileContent != null && fileContent.length > 2000) {
//                     // 해시 계산 (8자리)
//                     String contentHash = calculateHash(fileContent).substring(0, 8);
                    
//                     // [수정] 경로: category/countryCode (예: regulation/US)
//                     // country(국가명)는 경로에서 제외
//                     String folderPath = String.format("%s/%s", category, countryCode);

//                     // 4. [수정] S3 전체 스캔 중복 체크 (Pagination 적용)
//                     if (isHashExistsInS3(folderPath, contentHash)) {
//                         System.out.println("      ⏭️ 중복 발견(Skip): " + contentHash);
//                         continue;
//                     }

//                     boolean isPdf = isPdfContent(fileContent);
//                     String ext = isPdf ? ".pdf" : ".txt";
//                     byte[] finalContent = isPdf ? fileContent : cleanHtmlToText(fileContent);

//                     // 5. 날짜 추출
//                     String publishDate = resolvePublishDate(result, rawUrl, finalContent, isPdf, responseHeaders);

//                     // 파일명: TITLE_날짜_해시.pdf
//                     String fileName = generateVersionedFileName(title, publishDate, contentHash, ext);
                    
//                     // 업로드
//                     s3Uploader.uploadFile(finalContent, fileName, folderPath);
//                     System.out.println("      ✅ S3 신규 업로드: " + folderPath + "/" + fileName);

//                 } else {
//                     System.out.println("      ⚠️ 파일 크기 작음/차단됨 -> Skip");
//                 }
//             } catch (Exception e) {
//                 System.err.println("      ❌ 실패: " + rawUrl + " -> " + e.toString());
//             }
//         }
//     }

//     // --- [핵심 수정] S3 전체 목록 조회 (Pagination) ---
//     private boolean isHashExistsInS3(String folderPath, String targetHash) {
//         try {
//             ListObjectsV2Request req = new ListObjectsV2Request()
//                     .withBucketName(bucket)
//                     .withPrefix(folderPath); // 예: regulation/US
            
//             ListObjectsV2Result result;

//             // 파일이 1000개가 넘어도 페이지를 넘겨가며(do-while) 끝까지 조회
//             do {
//                 result = amazonS3.listObjectsV2(req);

//                 for (S3ObjectSummary objectSummary : result.getObjectSummaries()) {
//                     // 해시값이 파일명에 포함되어 있는지 확인
//                     if (objectSummary.getKey().contains("_" + targetHash + ".")) {
//                         return true; // 중복 발견
//                     }
//                 }
                
//                 // 다음 페이지 토큰 설정
//                 req.setContinuationToken(result.getNextContinuationToken());
                
//             } while (result.isTruncated()); // 더 가져올 게 있는 동안 반복

//         } catch (Exception e) {
//             System.err.println("      ⚠️ S3 목록 조회 실패(무시하고 업로드 진행): " + e.getMessage());
//             // 조회 실패 시 안전하게 '중복 아님'으로 처리하여 업로드 시도
//         }
//         return false; 
//     }

//     // --- 날짜 추출 5단계 방어 로직 ---
//     private String resolvePublishDate(Map<String, String> searchResult, String url, byte[] fileContent, boolean isPdf, HttpHeaders headers) {
//         String foundDate = null;
//         foundDate = extractDateFromUrl(url);
//         if (foundDate != null) return formatDateToYYYYMMDD(foundDate);

//         if (searchResult.get("published_date") != null) foundDate = searchResult.get("published_date");
//         if (foundDate == null && searchResult.get("date") != null) foundDate = searchResult.get("date");
//         if (foundDate != null) return formatDateToYYYYMMDD(foundDate);

//         if (!isPdf) {
//             try {
//                 String html = new String(fileContent, StandardCharsets.UTF_8);
//                 Document doc = Jsoup.parse(html);
//                 foundDate = extractDateFromJsonLd(doc);
//                 if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
//                 foundDate = extractDateFromMetaTags(doc);
//                 if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
//                 foundDate = extractDateFromDomElements(doc);
//                 if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
//                 foundDate = findDatePatternInText(doc.text().substring(0, Math.min(doc.text().length(), 3000)));
//                 if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
//             } catch (Exception ignored) {}
//         }

//         if (headers.getLastModified() > 0) {
//             try {
//                 foundDate = java.time.Instant.ofEpochMilli(headers.getLastModified())
//                             .atZone(ZoneId.of("UTC"))
//                             .toLocalDate()
//                             .format(DateTimeFormatter.ISO_DATE);
//                 if (foundDate != null) return formatDateToYYYYMMDD(foundDate);
//             } catch (Exception ignored) {}
//         }

//         if (searchResult.get("content") != null) {
//             foundDate = findDatePatternInText(searchResult.get("content"));
//         }
//         return formatDateToYYYYMMDD(foundDate);
//     }

//     // --- 유틸 메서드 ---

//     private String extractDateFromJsonLd(Document doc) {
//         Elements scripts = doc.select("script[type=application/ld+json]");
//         for (Element script : scripts) {
//             String json = script.html();
//             Pattern p = Pattern.compile("\"datePublished\"\\s*:\\s*\"([^\"]+)\"");
//             Matcher m = p.matcher(json);
//             if (m.find()) return m.group(1);
//             Pattern p2 = Pattern.compile("\"dateModified\"\\s*:\\s*\"([^\"]+)\"");
//             Matcher m2 = p2.matcher(json);
//             if (m2.find()) return m2.group(1);
//         }
//         return null;
//     }

//     private String extractDateFromMetaTags(Document doc) {
//         String[] metaNames = { "article:published_time", "article:modified_time", "date", "pubdate", "publish_date", "created_at", "og:updated_time", "regDate" };
//         for (String name : metaNames) {
//             Element meta = doc.selectFirst("meta[name='" + name + "']");
//             if (meta == null) meta = doc.selectFirst("meta[property='" + name + "']");
//             if (meta != null && !meta.attr("content").isEmpty()) return meta.attr("content");
//         }
//         return null;
//     }

//     private String extractDateFromDomElements(Document doc) {
//         String[] selectors = { ".date", ".pubDate", ".published", ".time", "#date", ".reg-date" };
//         for (String selector : selectors) {
//             Elements elements = doc.select(selector);
//             for (Element el : elements) {
//                 String date = findDatePatternInText(el.text());
//                 if (date != null) return date;
//             }
//         }
//         return null;
//     }

//     private String extractDateFromUrl(String url) {
//         if (url == null) return null;
//         try { url = URLDecoder.decode(url, StandardCharsets.UTF_8.name()); } catch(Exception e) {}
//         Pattern pattern = Pattern.compile("(20\\d{2})[-./]?(0[1-9]|1[0-2])[-./]?(0[1-9]|[12]\\d|3[01])");
//         Matcher matcher = pattern.matcher(url);
//         if (matcher.find()) return matcher.group(0);
//         return null;
//     }

//     private String findDatePatternInText(String text) {
//         if (text == null) return null;
//         Pattern p1 = Pattern.compile("20\\d{2}[-./](0[1-9]|1[0-2])[-./](0[1-9]|[12]\\d|3[01])");
//         Matcher m1 = p1.matcher(text);
//         if (m1.find()) return m1.group(0);
//         Pattern p2 = Pattern.compile("20\\d{2}년\\s*(0?[1-9]|1[0-2])월\\s*(0?[1-9]|[12]\\d|3[01])일");
//         Matcher m2 = p2.matcher(text);
//         if (m2.find()) return m2.group(0);
//         return null;
//     }

//     private String formatDateToYYYYMMDD(String rawDate) {
//         if (rawDate == null || rawDate.trim().isEmpty()) return LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
//         try {
//             String cleanDate = rawDate.replaceAll("[^0-9]", " ").trim();
//             String[] parts = cleanDate.split("\\s+");
//             if (parts.length >= 3) {
//                 int y = Integer.parseInt(parts[0]);
//                 int m = Integer.parseInt(parts[1]);
//                 int d = Integer.parseInt(parts[2]);
//                 if (y < 100) y += 2000;
//                 return String.format("%04d%02d%02d", y, m, d);
//             }
//             String numbersOnly = rawDate.replaceAll("[^0-9]", "");
//             if (numbersOnly.length() >= 8) return numbersOnly.substring(0, 8);
//             return LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
//         } catch (Exception e) {
//             return LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
//         }
//     }

//     private URI encodeUrl(String urlStr) throws Exception {
//         if (urlStr == null) return null;
//         String decodedUrl = URLDecoder.decode(urlStr, StandardCharsets.UTF_8.name());
//         URL url = new URL(decodedUrl);
//         return new URI(url.getProtocol(), url.getUserInfo(), url.getHost(), 
//                        url.getPort(), url.getPath(), url.getQuery(), null);
//     }

//     private HttpHeaders createBrowserHeaders() {
//         HttpHeaders headers = new HttpHeaders();
//         headers.set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
//         headers.set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8");
//         headers.set("Accept-Language", "en-US,en;q=0.9,ko;q=0.8");
//         headers.set("Referer", "https://www.google.com/");
//         headers.set("Connection", "keep-alive");
//         return headers;
//     }

//     private String generateVersionedFileName(String title, String publishDate, String contentHash, String ext) {
//         String safeTitle = title.replaceAll("[\\\\/:*?\"<>|]", ""); 
//         safeTitle = safeTitle.trim().replaceAll("\\s+", "_");
//         if (safeTitle.length() > 100) safeTitle = safeTitle.substring(0, 100);
//         return String.format("%s_%s_%s%s", safeTitle, publishDate, contentHash, ext);
//     }

//     private String calculateHash(byte[] content) {
//         try {
//             StringBuilder sb = new StringBuilder();
//             for (byte b : MessageDigest.getInstance("SHA-256").digest(content)) {
//                 sb.append(String.format("%02x", b));
//             }
//             return sb.toString();
//         } catch (Exception e) {
//             return String.valueOf(System.currentTimeMillis());
//         }
//     }

//     private void randomSleep(int minMillis, int maxMillis) {
//         try {
//             int delay = random.nextInt(maxMillis - minMillis + 1) + minMillis;
//             Thread.sleep(delay);
//         } catch (InterruptedException e) {
//             Thread.currentThread().interrupt();
//         }
//     }

//     // Repository 및 기타 메서드 유지
//     public List<CrawlTarget> getAllTargets() { return targetRepository.findAll(); }
//     public CrawlTarget addTarget(CrawlTarget target) { return targetRepository.save(target); }
//     public void deleteTarget(Long id) { targetRepository.deleteById(id); }
//     public CrawlTarget updateTarget(Long id, CrawlTarget updatedInfo) {
//         CrawlTarget target = targetRepository.findById(id).orElseThrow();
//         target.setCountry(updatedInfo.getCountry());
//         target.setCode(updatedInfo.getCode());
//         target.setCategory(updatedInfo.getCategory());
//         target.setEnabled(updatedInfo.isEnabled());
//         if (target.getKeywords() != null) target.getKeywords().clear();
//         if (updatedInfo.getKeywords() != null) target.getKeywords().addAll(updatedInfo.getKeywords());
//         return targetRepository.save(target);
//     }
//     public void updateTargetStatus(Long id, boolean enabled) {
//         CrawlTarget target = targetRepository.findById(id).orElseThrow();
//         target.setEnabled(enabled);
//         targetRepository.save(target);
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



