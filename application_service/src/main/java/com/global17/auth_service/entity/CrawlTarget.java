package com.global17.auth_service.entity;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDate;
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

    // 프론트엔드 Title
    private String title;

    @Column(nullable = false)
    private String country; // "US"

    @Column(length = 10)
    private String code;    // "US"

    private boolean enabled = true;

    // [매핑] 프론트엔드 "type": "reg" -> 백엔드 category
    @JsonProperty("type")
    private String category;
    
    // [매핑] 화면 표시용 라벨 "typeLabel": "Regulation"
    @JsonProperty("typeLabel")
    private String typeLabel; 

    // [매핑] "domain": "govinfo.gov" -> targetDomain
    @JsonProperty("domain")
    private String targetDomain;    

    // [매핑] "format": "pdf" -> documentFormat
    @JsonProperty("format")
    private String documentFormat;  

    // [매핑] "date": "2024-12-01" -> baseDate
    @JsonProperty("date")
    private LocalDate baseDate;     

    private String targetUrl;       

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "crawl_target_keywords", joinColumns = @JoinColumn(name = "target_id"))
    @Column(name = "keyword", columnDefinition = "TEXT")
    private List<String> keywords;
}
