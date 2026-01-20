# hienfeld/services/analysis/strategies/__init__.py
"""
Analysis strategies implementing the waterfall pipeline steps.

Each strategy implements one step of the analysis pipeline.
Strategies are executed in order until one returns a non-None result.
"""

from .admin_check_strategy import AdminCheckStrategy
from .custom_instructions_strategy import CustomInstructionsStrategy
from .clause_library_strategy import ClauseLibraryStrategy
from .conditions_match_strategy import ConditionsMatchStrategy
from .fallback_strategy import FallbackStrategy

__all__ = [
    "AdminCheckStrategy",
    "CustomInstructionsStrategy",
    "ClauseLibraryStrategy",
    "ConditionsMatchStrategy",
    "FallbackStrategy",
]
