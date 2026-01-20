# hienfeld/services/interfaces/analysis_strategy_interface.py
"""
Abstract base class and context for analysis strategies.

The analysis pipeline uses a Strategy pattern where each step (Admin Check,
Custom Instructions, Clause Library, Conditions Match, Fallback) is
implemented as a separate strategy class.

This enables:
- Clean separation of concerns
- Easy addition of new steps
- Independent testing of each strategy
- Flexible ordering/skipping of steps
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hienfeld.config import AppConfig
    from hienfeld.domain.cluster import Cluster
    from hienfeld.domain.analysis import AnalysisAdvice
    from hienfeld.domain.policy_document import PolicyDocumentSection
    from hienfeld.services.interfaces.similarity_interface import (
        ISimilarityService,
        IHybridSimilarityService,
        ISemanticSimilarityService,
    )


@dataclass
class AnalysisContext:
    """
    Shared context passed to all analysis strategies.

    Contains all the data and services needed to analyze a cluster.
    Immutable after creation to ensure thread-safety.

    Attributes:
        config: Application configuration
        policy_sections: Parsed policy document sections (voorwaarden)
        policy_full_text: Concatenated text of all sections for substring search
        section_lookup: Dict mapping section ID -> PolicyDocumentSection

    Services:
        similarity_service: Base RapidFuzz service for text comparison
        hybrid_service: Multi-method hybrid similarity (optional)
        semantic_service: Embedding-based semantic similarity (optional)
        clause_library_service: Standard clause matching (optional)
        admin_check_service: Hygiene/admin checks (optional)
        custom_instructions_service: User-defined rules (optional)
        reference_service: Reference analysis comparison (optional)
        ai_analyzer: LLM-based analysis (optional)

    State:
        semantic_index_ready: True if semantic embeddings are indexed
    """

    # Configuration
    config: "AppConfig"

    # Policy data
    policy_sections: List["PolicyDocumentSection"] = field(default_factory=list)
    policy_full_text: str = ""
    section_lookup: Dict[str, "PolicyDocumentSection"] = field(default_factory=dict)

    # Core services
    similarity_service: Optional["ISimilarityService"] = None
    hybrid_service: Optional["IHybridSimilarityService"] = None
    semantic_service: Optional["ISemanticSimilarityService"] = None

    # Optional services
    clause_library_service: Optional[Any] = None
    admin_check_service: Optional[Any] = None
    custom_instructions_service: Optional[Any] = None
    reference_service: Optional[Any] = None
    ai_analyzer: Optional[Any] = None

    # State flags
    semantic_index_ready: bool = False

    # Caches (mutable, strategy can add cached results)
    reference_matches: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_conditions(self) -> bool:
        """Check if policy conditions are available."""
        return bool(self.policy_sections)

    @property
    def has_clause_library(self) -> bool:
        """Check if clause library is available."""
        return (
            self.clause_library_service is not None
            and getattr(self.clause_library_service, "is_loaded", False)
        )

    @property
    def has_custom_instructions(self) -> bool:
        """Check if custom instructions are available."""
        return (
            self.custom_instructions_service is not None
            and getattr(self.custom_instructions_service, "is_loaded", False)
        )

    @property
    def has_semantic(self) -> bool:
        """Check if semantic similarity is available."""
        return (
            self.semantic_service is not None
            and getattr(self.semantic_service, "is_available", False)
        )

    @property
    def has_hybrid(self) -> bool:
        """Check if hybrid similarity is available."""
        return self.hybrid_service is not None

    def find_matching_section(self, text: str) -> Optional["PolicyDocumentSection"]:
        """
        Find the first section where the given text appears (substring match).

        Args:
            text: Text to search for

        Returns:
            PolicyDocumentSection if found, None otherwise
        """
        for section in self.policy_sections:
            if section.simplified_text and text in section.simplified_text:
                return section
        return None


class IAnalysisStrategy(ABC):
    """
    Abstract base class for analysis strategies.

    Each strategy implements one step of the waterfall analysis pipeline.
    Strategies are executed in order until one returns a non-None result.

    The waterfall pipeline (v4.2):
    - Step 0: AdminCheckStrategy - Hygiene issues (empty, dates, placeholders)
    - Step 0.5: CustomInstructionsStrategy - User-defined rules
    - Step 1: ClauseLibraryStrategy - Standard clause matching
    - Step 2: ConditionsMatchStrategy - Policy conditions matching
    - Step 3: FallbackStrategy - Keywords, frequency, AI analysis

    Example implementation:
        class AdminCheckStrategy(IAnalysisStrategy):
            @property
            def step_name(self) -> str:
                return "Admin Check"

            @property
            def step_order(self) -> float:
                return 0.0

            def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
                return context.admin_check_service is not None

            def analyze(self, cluster: Cluster, context: AnalysisContext) -> Optional[AnalysisAdvice]:
                result, advice = context.admin_check_service.check_cluster(cluster)
                return advice if advice else None
    """

    @property
    @abstractmethod
    def step_name(self) -> str:
        """
        Human-readable name for this strategy step.

        Used in logging and debugging.

        Returns:
            Name like "Admin Check", "Clause Library", etc.
        """
        pass

    @property
    @abstractmethod
    def step_order(self) -> float:
        """
        Numeric order for pipeline execution.

        Strategies are sorted by this value before execution.
        Using floats allows insertion of steps (e.g., 0.5 between 0 and 1).

        Standard ordering:
        - 0.0: Admin Check
        - 0.5: Custom Instructions
        - 1.0: Clause Library
        - 2.0: Conditions Match
        - 3.0: Fallback

        Returns:
            Numeric order value
        """
        pass

    def can_handle(self, cluster: "Cluster", context: AnalysisContext) -> bool:
        """
        Check if this strategy can handle the given cluster.

        Override to add preconditions (e.g., service availability).
        Default implementation returns True.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with services

        Returns:
            True if this strategy should attempt analysis
        """
        return True

    @abstractmethod
    def analyze(
        self,
        cluster: "Cluster",
        context: AnalysisContext
    ) -> Optional["AnalysisAdvice"]:
        """
        Analyze a cluster and return advice if applicable.

        If this strategy matches, return an AnalysisAdvice.
        If this strategy doesn't match, return None to continue to next strategy.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with services and data

        Returns:
            AnalysisAdvice if this strategy matched, None otherwise
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step={self.step_order}, name='{self.step_name}')"


class AnalysisPipelineInterface(ABC):
    """
    Interface for the analysis pipeline that coordinates strategies.

    The pipeline executes strategies in order, stopping at the first
    that returns a non-None advice.
    """

    @abstractmethod
    def add_strategy(self, strategy: IAnalysisStrategy) -> None:
        """
        Add a strategy to the pipeline.

        Strategies are automatically sorted by step_order.

        Args:
            strategy: Strategy to add
        """
        pass

    @abstractmethod
    def analyze_cluster(
        self,
        cluster: "Cluster",
        context: AnalysisContext
    ) -> "AnalysisAdvice":
        """
        Analyze a single cluster using all strategies.

        Executes strategies in order until one returns advice.
        If no strategy matches, returns a fallback advice.

        Args:
            cluster: Cluster to analyze
            context: Analysis context

        Returns:
            AnalysisAdvice from first matching strategy or fallback
        """
        pass

    @abstractmethod
    def analyze_clusters(
        self,
        clusters: List["Cluster"],
        context: AnalysisContext,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, "AnalysisAdvice"]:
        """
        Analyze multiple clusters.

        Args:
            clusters: List of clusters to analyze
            context: Analysis context (shared)
            progress_callback: Optional progress callback (0-100)

        Returns:
            Dict mapping cluster_id -> AnalysisAdvice
        """
        pass
