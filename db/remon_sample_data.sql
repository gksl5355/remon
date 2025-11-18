-- 데미데이터 모음 (위에서 순차적으로 실행할것을 권장)
---- 1. 국가 데이터
INSERT INTO countries (country_code, country_name) VALUES
--('KR', 'South Korea'),
('US', 'United States');
--('JP', 'Japan'),
--('CN', 'China'),
--('GB', 'United Kingdom'),
--('DE', 'Germany'),
--('FR', 'France'),
--('AU', 'Australia'),
--('CA', 'Canada'),
--('RU', 'Russia');

-- 2. 
INSERT INTO data_sources (source_id, source_name) VALUES (1, 'Manual Upload');
--
--3. regulations
INSERT INTO regulations (regulation_id, source_id, country_code, title, status) 
VALUES 
  (1, 1, 'US', 'US 니코틴 규제', 'active'),
  (2, 1, 'US', 'US 광고 규제', 'active');
--
-- 4. regulation_versions (regulations의 버전)
INSERT INTO regulation_versions (regulation_version_id, regulation_id, version_number)
VALUES (1, 1, 1),
(2, 1, 1);
--

-- 5. regulation_translations (번역본)
INSERT INTO regulation_translations (translation_id, regulation_version_id, language_code, translated_text, created_at)
VALUES 
  (1, 1, 'KO', 'US 니코틴 함량 표기 기준 강화 번역본', NOW()),
  (2, 2, 'KO', 'US 전자담배 광고 규제 완화 번역본', NOW());

-- 6. regulation_change_history (변경 이력)
INSERT INTO regulation_change_history (change_id, regulation_version_id, change_type, change_summary)
VALUES (1, 1, 'new', '신규 규제');
--
-- 7. products (제품)
INSERT INTO products 
(product_name, product_category, manufactured_at, nicotin, tarr, menthol, incense, battery, label_size, image, security_auth, Revenue)
VALUES
('Marlboro Red', 'combustible', now(), '0.8mg', '8.0mg', false, false, 'N/A', '50x70mm', 'text', true,200),
('Camel Blue', 'combustible', now(), '0.7mg', '7.0mg', false, false, 'N/A', '50x65mm', 'text', true,150),
('IQOS Iluma One', 'htp', now(), '1.0mg', 'N/A', true, false, '18650', '40x50mm', 'text', true,250),
('Glo Hyper X2', 'htp', now(), '1.2mg', 'N/A', true, false, '18650', '38x48mm', 'text', true,180),
('Elf Bar 5000', 'e_cigarette', now(), '5%', 'N/A', false, true, 'built-in', '30x40mm', 'text', false,220);
--
-- 8. reports (리포트)
INSERT INTO reports (report_id, translation_id, change_id, product_id, country_code, created_reason)
VALUES (1, 1, 1, 1, 'US', 'change_detected');

-- 9.impact_scores (영향도 점수)
INSERT INTO impact_scores (impact_score_id, translation_id, product_id, impact_score, risk_level, evaluated_at)
VALUES 
  (1, 1, 1, 0.850, 'HIGH', NOW()),
  (2, 2, 1, 0.500, 'MEDIUM', NOW());
--  (3, 3, 1, 0.300, 'low', NOW());

-- 10. regulation_change_keynotes
INSERT INTO regulation_change_keynotes (
  keynote_id, 
  product_id, 
  country_code, 
  regulation_version_id, 
  impact_score_id, 
  translation_id, 
  title, 
  regulation_type, 
  generated_at
)
values
  (1, 1, 'US', 1, 1, 1, 'US 광고 규제 완화', '광고 규제', NOW()),
  (2, 1, 'US', 2, 2, 2, 'US 니코틴 규제 강화', '라벨 표시', NOW());