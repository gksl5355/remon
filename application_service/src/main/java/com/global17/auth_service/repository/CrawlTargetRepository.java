package com.global17.auth_service.repository;

import com.global17.auth_service.entity.CrawlTarget;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface CrawlTargetRepository extends JpaRepository<CrawlTarget, Long> {
    // 활성화된 타겟만 가져오는 메서드
    List<CrawlTarget> findByEnabledTrue();
}