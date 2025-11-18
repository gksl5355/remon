"""RAG Retrieval Tools for REMON AI Pipeline."""

from app.ai_pipeline.tools.retrieval_config import (
    MetadataFilter,
    RetrievalConfig
)
from app.ai_pipeline.tools.retrieval_strategies import (
    RetrievalStrategy,
    RetrievalResult,
    DenseStrategy,
    HybridStrategy,
    MetadataFirstStrategy,
    ParentChildStrategy,
    HierarchicalStrategy,
    StrategyFactory
)
from app.ai_pipeline.tools.retrieval_tool import (
    RegulationRetrievalTool,
    RetrievalInput,
    RetrievalOutput,
    get_retrieval_tool
)
from app.ai_pipeline.tools.retrieval_utils import (
    build_product_filters,
    map_category_to_regulation_type,
    calculate_retrieval_metadata,
    format_retrieval_result_for_state
)
from app.ai_pipeline.tools.filter_builder import (
    FilterBuilder,
    ProductFilterBuilder,
    AdvancedFilterBuilder,
    create_filter_from_state
)
from app.ai_pipeline.tools.retrieval_optimizer import (
    QueryCache,
    BatchRetriever,
    EmbeddingBatcher,
    optimize_filters
)

__all__ = [
    # Config
    "MetadataFilter",
    "RetrievalConfig",
    # Strategies
    "RetrievalStrategy",
    "RetrievalResult",
    "DenseStrategy",
    "HybridStrategy",
    "MetadataFirstStrategy",
    "ParentChildStrategy",
    "HierarchicalStrategy",
    "StrategyFactory",
    # Tool
"""RAG Retrieval Tools for REMON AI Pipeline (lazy imports)."""

from importlib import import_module
from typing import Any

__all__ = [
    "RetrievalConfig",
    "RegulationRetrievalTool",
    "RetrievalInput",
    "RetrievalOutput",
    "get_retrieval_tool",
<<<<<<< HEAD
    # Utils
    "build_product_filters",
    "map_category_to_regulation_type",
    "calculate_retrieval_metadata",
    "format_retrieval_result_for_state",
    # Filter Builder
    "FilterBuilder",
    "ProductFilterBuilder",
    "AdvancedFilterBuilder",
    "create_filter_from_state",
    # Optimizer
    "QueryCache",
    "BatchRetriever",
    "EmbeddingBatcher",
    "optimize_filters"
]
=======
    "build_product_filters",
]

_ATTR_TO_MODULE = {
    "RetrievalConfig": "app.ai_pipeline.tools.retrieval_config",
    "RegulationRetrievalTool": "app.ai_pipeline.tools.retrieval_tool",
    "RetrievalInput": "app.ai_pipeline.tools.retrieval_tool",
    "RetrievalOutput": "app.ai_pipeline.tools.retrieval_tool",
    "get_retrieval_tool": "app.ai_pipeline.tools.retrieval_tool",
    "build_product_filters": "app.ai_pipeline.tools.retrieval_utils",
}


def __getattr__(name: str) -> Any:
    """Lazily import heavy modules when attributes are accessed."""
    if name not in _ATTR_TO_MODULE:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(_ATTR_TO_MODULE[name])
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(__all__) + list(globals().keys()))
>>>>>>> 9c8d2e5de60743a693e60af5e8d67ba0c3fc7bc2
