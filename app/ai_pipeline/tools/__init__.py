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
    "RegulationRetrievalTool",
    "RetrievalInput",
    "RetrievalOutput",
    "get_retrieval_tool",
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
