package com.global17.auth_service.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import java.util.List;
import java.util.ArrayList;
import java.time.LocalDate;

@Data
public class CrawlConfig {
    private List<Target> targets = new ArrayList<>();

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Target {
        private String title;       // 추가
        private String country;
        private String code;
        private boolean enabled;
        private String category;
        private String typeLabel;   // 추가
        private String targetDomain; // 추가
        private String documentFormat; // 추가
        private LocalDate baseDate;    // 추가
        private String targetUrl;      // 추가
        private List<String> keywords;
    }
}

