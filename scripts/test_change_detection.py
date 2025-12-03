"""
module: test_change_detection.py
description: 규제 변경 감지 노드 테스트 스크립트
author: AI Agent
created: 2025-01-18
"""

import asyncio
import json
from pathlib import Path

from app.ai_pipeline.preprocess import preprocess_node
from app.ai_pipeline.state import AppState


async def test_change_detection():
    """변경 감지 노드 테스트."""
    
    # 테스트 PDF 경로
    pdf_path = "/home/minje/remon/data/test_regulation.pdf"
    
    # AppState 초기화
    state: AppState = {
        "preprocess_request": {
            "pdf_paths": [pdf_path],
            "use_vision_pipeline": True,
            "enable_change_detection": True,  # 변경 감지 활성화
            "vision_config": {
                "api_key": None,  # 환경변수에서 로드
                "max_concurrency": 3
            }
        },
        "change_context": {
            "legacy_regulation_id": "FDA-2024-001"  # Legacy 규제 ID
        }
    }
    
    # 전처리 + 변경 감지 실행
    print("=== 전처리 + 변경 감지 시작 ===")
    result_state = await preprocess_node(state)
    
    # 결과 출력
    print("\n=== 전처리 결과 ===")
    print(json.dumps(result_state.get("preprocess_summary"), indent=2, ensure_ascii=False))
    
    print("\n=== 변경 감지 요약 ===")
    change_summary = result_state.get("change_summary", {})
    print(json.dumps(change_summary, indent=2, ensure_ascii=False))
    
    print("\n=== 변경 감지 상세 결과 ===")
    change_results = result_state.get("change_detection_results", [])
    
    for i, result in enumerate(change_results, 1):
        if result.get("change_detected"):
            print(f"\n[변경 {i}] Section {result.get('section_ref')}")
            print(f"  변경 유형: {result.get('change_type')}")
            print(f"  신뢰도: {result.get('confidence_score'):.2f} ({result.get('confidence_level')})")
            print(f"  기존: {result.get('legacy_snippet', '')[:100]}...")
            print(f"  신규: {result.get('new_snippet', '')[:100]}...")
            
            # Chain of Thought 출력
            reasoning = result.get("reasoning", {})
            print(f"\n  판단 근거:")
            print(f"    Step 1: {reasoning.get('step1_section_comparison', '')}")
            print(f"    Step 2: {reasoning.get('step2_term_comparison', '')}")
            print(f"    Step 3: {reasoning.get('step3_semantic_evaluation', '')}")
            print(f"    Step 4: {reasoning.get('step4_final_judgment', '')}")
            
            # Adversarial Check 출력
            adversarial = result.get("adversarial_check", {})
            if adversarial:
                print(f"\n  자체 검증:")
                print(f"    반박: {adversarial.get('counter_argument', '')}")
                print(f"    재반박: {adversarial.get('rebuttal', '')}")
                print(f"    조정된 신뢰도: {adversarial.get('adjusted_confidence', 0):.2f}")
            
            # 수치 변경 출력
            numerical_changes = result.get("numerical_changes", [])
            if numerical_changes:
                print(f"\n  수치 변경:")
                for nc in numerical_changes:
                    print(f"    - {nc.get('field')}: {nc.get('legacy_value')} → {nc.get('new_value')}")
                    print(f"      맥락: {nc.get('context')}")
                    print(f"      영향도: {nc.get('impact')}")


if __name__ == "__main__":
    asyncio.run(test_change_detection())
