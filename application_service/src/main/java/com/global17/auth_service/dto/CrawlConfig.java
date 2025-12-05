package com.global17.auth_service.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import java.util.List;
import java.util.ArrayList;

@Data
public class CrawlConfig {
    private List<Target> targets = new ArrayList<>();

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Target {
        private String country;
        private String code;
        private boolean enabled;
        private String category;
        private List<String> keywords;
    }
}
