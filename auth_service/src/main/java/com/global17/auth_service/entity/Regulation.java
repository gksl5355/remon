package com.global17.auth_service.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDate;

@Entity
@Table(name = "regulations")
@Getter @Setter
@NoArgsConstructor @AllArgsConstructor
@Builder
public class Regulation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "regulation_id")
    private Long regulationId;

    @Column(name = "source_id")
    private Integer sourceId;

    @Column(name = "country_code", length = 2)
    private String countryCode;

    @Column(columnDefinition = "TEXT")
    private String title;

    @Column(length = 50)
    private String status;

    @Column(name = "created_at")
    private LocalDate createdAt;
    
    // 필요 시 Version 등 연관 관계 추가 가능
}


// package com.global17.auth_service.entity;

// import jakarta.persistence.*;
// import lombok.*;
// import java.time.LocalDate;

// @Entity
// @Table(name = "regulations")
// @Getter @Setter
// @NoArgsConstructor @AllArgsConstructor
// @Builder
// public class Regulation {

//     @Id
//     @GeneratedValue(strategy = GenerationType.IDENTITY)
//     private Long regulationId;

//     @Column(name = "source_id")
//     private Integer sourceId;

//     @Column(name = "country_code", length = 2)
//     private String countryCode;

//     private String title;

//     @Column(name = "status")
//     private String status;

//     @Column(name = "created_at")
//     private LocalDate createdAt;
// }