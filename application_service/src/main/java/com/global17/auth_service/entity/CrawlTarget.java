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