# hienfeld/services/interfaces/__init__.py
"""
Service interfaces for dependency injection and testability.

This package defines Protocol/ABC interfaces for the core services,
enabling:
- Clean dependency injection
- Easy mocking in tests
- Clear contracts between services
"""

from .similarity_interface import (
    ISimilarityService,
    IBatchSimilarityService,
    ISemanticSimilarityService,
)
from .analysis_strategy_interface import (
    IAnalysisStrategy,
    AnalysisContext,
)

__all__ = [
    # Similarity interfaces
    "ISimilarityService",
    "IBatchSimilarityService",
    "ISemanticSimilarityService",
    # Analysis strategy interfaces
    "IAnalysisStrategy",
    "AnalysisContext",
]
