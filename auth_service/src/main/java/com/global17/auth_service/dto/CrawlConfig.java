package com.global17.auth_service.dto;

import lombok.Data;
import java.util.List;

@Data
public class CrawlConfig {
    private List<Target> targets;

    @Data
    public static class Target {
        private String country;
        private String code;
        private boolean enabled;
        private String category;
        private List<String> keywords;
    }
}