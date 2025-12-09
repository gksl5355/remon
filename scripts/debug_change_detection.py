"""
scripts/debug_change_detection.py
변경 감지 노드만 실행해 키워드/수치/섹션 등을 빠르게 확인하는 디버그 스크립트.

실행 예:
    PYTHONPATH=. uv run scripts/debug_change_detection.py --new 123 --legacy 45
"""

import asyncio
import argparse
from dotenv import load_dotenv
from typing import Any, Optional

from app.ai_pipeline.nodes.change_detection import ChangeDetectionNode
from app.ai_pipeline.state import AppState
from app.core.repositories.regulation_repository import RegulationRepository
from app.core.database import AsyncSessionLocal


async def resolve_regulation_ids(use_latest: bool, new_id: Optional[int], legacy_id: Optional[int]):
    """DB에서 최신 regulation_id 쌍을 찾아 반환한다."""
    if not use_latest:
        return new_id, legacy_id

    async with AsyncSessionLocal() as session:
        repo = RegulationRepository()
        new_reg = await repo.get_latest_regulation(session)
        legacy_reg = await repo.get_latest_regulation(session, exclude_id=new_reg.regulation_id if new_reg else None)

    resolved_new = new_reg.regulation_id if new_reg else None
    resolved_legacy = legacy_reg.regulation_id if legacy_reg else None
    return resolved_new, resolved_legacy


async def main(args: Any):
    # 환경변수(.env) 로드
    load_dotenv()
    new_id, legacy_id = await resolve_regulation_ids(args.use_latest, args.new, args.legacy)
    if not new_id:
        raise SystemExit("신규 regulation_id를 찾을 수 없습니다. --new 또는 --use-latest를 확인하세요.")

    state: AppState = {
        "change_context": {
            "new_regulation_id": new_id,
            "legacy_regulation_id": legacy_id,
        }
    }
    node = ChangeDetectionNode()
    new_state = await node.run(state)

    results = new_state.get("change_detection_results", []) or []
    print(f"Total results: {len(results)} (new_id={new_id}, legacy_id={legacy_id})")
    for r in results[: args.limit]:
        print("-" * 60)
        print("section_ref:", r.get("section_ref"))
        print("change_detected:", r.get("change_detected"))
        print("change_type:", r.get("change_type"))
        print("confidence_score:", r.get("confidence_score"))
        print("keywords:", r.get("keywords"))
        print("numerical_changes:", r.get("numerical_changes"))
        print("new_snippet:", (r.get("new_snippet") or r.get("new_text") or "")[:200])
        print("legacy_snippet:", (r.get("legacy_snippet") or r.get("legacy_text") or "")[:200])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", type=int, help="신규 regulation_id (미지정 시 --use-latest 우선)")
    parser.add_argument("--legacy", type=int, help="레거시 regulation_id (선택)")
    parser.add_argument("--use-latest", action="store_true", help="DB에서 최신 regulation 쌍을 자동 선택")
    parser.add_argument("--limit", type=int, default=10, help="출력할 결과 개수")
    args = parser.parse_args()
    asyncio.run(main(args))
