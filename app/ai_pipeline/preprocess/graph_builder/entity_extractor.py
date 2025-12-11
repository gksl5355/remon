"""
module: entity_extractor.py
description: 페이지별 엔티티를 통합하여 지식 그래프 구축
author: AI Agent
created: 2025-01-14
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class EntityExtractor:
    """엔티티 및 관계 추출."""

    def extract_from_pages(self, page_structures: List[Any]) -> Dict[str, Any]:
        """
        페이지별 구조에서 엔티티 통합.

        Args:
            page_structures: List[PageStructure]

        Returns:
            Dict: {"nodes": [...], "edges": [...]}
        """
        all_entities = []

        for page_struct in page_structures:
            all_entities.extend(page_struct.entities)

        # 엔티티 중복 제거 및 정규화
        unique_entities = self._deduplicate_entities(all_entities)

        # 노드 생성
        nodes = [
            {"id": entity.name, "type": entity.type, "context": entity.context}
            for entity in unique_entities
        ]

        # 엣지 생성 (간단한 휴리스틱)
        edges = self._infer_relationships(unique_entities)

        logger.info(f"엔티티 추출 완료: {len(nodes)}개 노드, {len(edges)}개 엣지")

        return {"nodes": nodes, "edges": edges}

    def _deduplicate_entities(self, entities: List[Any]) -> List[Any]:
        """엔티티 중복 제거."""
        seen = {}
        unique = []

        for entity in entities:
            key = (entity.name.lower(), entity.type)
            if key not in seen:
                seen[key] = True
                unique.append(entity)

        return unique

    def _infer_relationships(self, entities: List[Any]) -> List[Dict[str, Any]]:
        """간단한 관계 추론 (휴리스틱)."""
        edges = []

        # 타입별 그룹화
        by_type = {}
        for e in entities:
            by_type.setdefault(e.type, []).append(e)

        # Organization → Regulation
        for org in by_type.get("Organization", []):
            for reg in by_type.get("Regulation", []):
                edges.append(
                    {"source": org.name, "target": reg.name, "relation": "enforces"}
                )

        # Regulation → Chemical
        for reg in by_type.get("Regulation", []):
            for chem in by_type.get("Chemical", []):
                edges.append(
                    {"source": reg.name, "target": chem.name, "relation": "regulates"}
                )

        # 같은 컨텍스트 내 엔티티 연결 (페이지 기반)
        context_groups = {}
        for e in entities:
            ctx = e.context or "unknown"
            context_groups.setdefault(ctx, []).append(e)

        for ctx, group in context_groups.items():
            if len(group) >= 2:
                for i in range(len(group) - 1):
                    edges.append(
                        {
                            "source": group[i].name,
                            "target": group[i + 1].name,
                            "relation": "related_to",
                        }
                    )

        return edges
