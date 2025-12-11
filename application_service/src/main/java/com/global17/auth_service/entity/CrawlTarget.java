// package com.global17.auth_service.entity;

// import jakarta.persistence.*;
// import lombok.*;
// import java.time.LocalDate;
// import java.util.List;

// @Entity
// @Table(name = "crawl_targets")
// @Getter @Setter
// @NoArgsConstructor @AllArgsConstructor
// @Builder
// public class CrawlTarget {

//     @Id
//     @GeneratedValue(strategy = GenerationType.IDENTITY)
//     private Long id;

//     // [신규 필드 추가] 프론트엔드 Title (예: US Regulation Crawler)
//     private String title;

//     @Column(nullable = false)
//     private String country; // 예: USA FDA

//     @Column(length = 10)
//     private String code;    // 예: US

//     private boolean enabled; // 활성화 여부

//     private String category; // regulation or news (type)
    
//     // [신규 필드 추가] 화면 표시용 라벨 (예: Regulation)
//     private String typeLabel; 

//     // [신규 필드 추가] 상세 검색 옵션
//     private String targetDomain;    // 예: govinfo.gov (site: 옵션용)
//     private String documentFormat;  // 예: pdf (filetype: 옵션용)
//     private LocalDate baseDate;     // 예: 2024-12-01 (after: 옵션용)
//     private String targetUrl;       // (프론트 데이터에 있어서 추가함)

//     // 키워드 리스트를 별도 테이블로 관리 (1:N)
//     @ElementCollection(fetch = FetchType.EAGER)
//     @CollectionTable(name = "crawl_target_keywords", joinColumns = @JoinColumn(name = "target_id"))
//     @Column(name = "keyword", columnDefinition = "TEXT")
//     private List<String> keywords;
// }

package com.global17.auth_service.entity;

import jakarta.persistence.*;
import lombok.*;
import java.util.List;

@Entity
@Table(name = "crawl_targets")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class CrawlTarget {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String country; // 예: USA FDA

    @Column(length = 10)
    private String code;    // 예: US

    private boolean enabled; // 활성화 여부

    private String category; // regulation or news

    // 키워드 리스트를 별도 테이블로 관리 (1:N)
    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "crawl_target_keywords", joinColumns = @JoinColumn(name = "target_id"))
    @Column(name = "keyword", columnDefinition = "TEXT")
    private List<String> keywords;
}