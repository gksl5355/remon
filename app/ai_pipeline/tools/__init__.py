"""RAG Retrieval Tools for REMON AI Pipeline (lazy imports)."""

from importlib import import_module
from typing import Any

__all__ = [
    "RetrievalConfig",
    "RegulationRetrievalTool",
    "RetrievalInput",
    "RetrievalOutput",
    "get_retrieval_tool",
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
