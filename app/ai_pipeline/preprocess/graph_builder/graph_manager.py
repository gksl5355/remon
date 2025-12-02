"""
module: graph_manager.py
description: NetworkX 기반 인메모리 그래프 관리
author: AI Agent
created: 2025-01-14
dependencies: networkx
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class GraphManager:
    """NetworkX 그래프 관리."""
    
    def __init__(self):
        try:
            import networkx as nx
            self.nx = nx
            self.graph = nx.DiGraph()
        except ImportError:
            raise ImportError("networkx가 설치되지 않았습니다: pip install networkx")
    
    def build_graph(self, graph_data: Dict[str, Any]) -> None:
        """
        그래프 데이터를 NetworkX로 구축.
        
        Args:
            graph_data: {"nodes": [...], "edges": [...]}
        """
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        # 노드 추가
        for node in nodes:
            self.graph.add_node(
                node["id"],
                node_type=node.get("type"),
                context=node.get("context")
            )
        
        # 엣지 추가
        for edge in edges:
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                relation=edge.get("relation")
            )
        
        logger.info(f"그래프 구축 완료: {len(nodes)}개 노드, {len(edges)}개 엣지")
    
    def get_summary(self) -> Dict[str, Any]:
        """그래프 요약 정보."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "density": self.nx.density(self.graph)
        }
