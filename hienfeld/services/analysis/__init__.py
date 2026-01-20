# hienfeld/services/analysis/__init__.py
"""
Analysis package implementing the Strategy pattern for the waterfall pipeline.

The analysis pipeline uses a Strategy pattern where each step is implemented
as a separate strategy class, enabling:
- Clean separation of concerns
- Easy addition of new steps
- Independent testing of each strategy
- Flexible ordering/skipping of steps

Strategies (in execution order):
- Step 0: AdminCheckStrategy - Hygiene issues (empty, dates, placeholders)
- Step 0.5: CustomInstructionsStrategy - User-defined rules
- Step 1: ClauseLibraryStrategy - Standard clause matching
- Step 2: ConditionsMatchStrategy - Policy conditions matching
- Step 3: FallbackStrategy - Keywords, frequency, AI analysis
"""

from .analysis_pipeline import AnalysisPipeline
from .analysis_context import AnalysisContextBuilder

# Import strategies
from .strategies import (
    AdminCheckStrategy,
    CustomInstructionsStrategy,
    ClauseLibraryStrategy,
    ConditionsMatchStrategy,
    FallbackStrategy,
)

__all__ = [
    "AnalysisPipeline",
    "AnalysisContextBuilder",
    # Strategies
    "AdminCheckStrategy",
    "CustomInstructionsStrategy",
    "ClauseLibraryStrategy",
    "ConditionsMatchStrategy",
    "FallbackStrategy",
]
