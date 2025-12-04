package com.global17.auth_service.repository;

import com.global17.auth_service.entity.Regulation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface RegulationRepository extends JpaRepository<Regulation, Long> {
    // 필요한 경우 findByTitle 등의 메서드 추가
}