# hienfeld/services/analysis/strategies/clause_library_strategy.py
"""
Step 1: Clause Library Matching Strategy.

Matches cluster text against a library of standard clauses.
High similarity matches result in REPLACE recommendations,
medium matches result in CHECK recommendations.

Thresholds:
- >= 95%: REPLACE with standard clause code
- >= 85%: CHECK for possible replacement

SYNCED with AnalysisService._step1_clause_library_check (v4.5)
"""

from typing import Optional

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.clause_library")


class ClauseLibraryStrategy(IAnalysisStrategy):
    """
    Strategy for Step 1: Clause Library Matching.

    Compares cluster text against a library of standard clauses
    to identify texts that should be replaced or checked.

    Uses the ClauseLibraryService which returns ClauseMatch objects
    with is_replacement_candidate and is_review_candidate flags.
    """

    @property
    def step_name(self) -> str:
        return "Clause Library"

    @property
    def step_order(self) -> float:
        return 1.0

    def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
        """
        Only runs if clause library is loaded.

        Returns:
            True if clause library service is available and loaded
        """
        service = context.clause_library_service
        if service is None:
            return False

        is_loaded = getattr(service, "is_loaded", False)
        return is_loaded

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Match cluster against clause library.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with clause_library_service

        Returns:
            AnalysisAdvice if library match found, None otherwise
        """
        service = context.clause_library_service
        if not service:
            return None

        text = cluster.leader_text

        # Find best match in clause library
        match = service.find_match(text)

        if match is None:
            return None

        # High confidence match (>95%) -> REPLACE
        if match.is_replacement_candidate:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code="🔄 VERVANGEN",
                reason=f"Komt overeen met standaardclausule {match.clause.code} ({int(match.similarity_score*100)}% match). Vervang door deze standaardcode.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article=match.clause.code,
                category="LIBRARY_EXACT_MATCH",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        # Medium confidence match (85-95%) -> REVIEW
        if match.is_review_candidate:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code="🔍 CONTROLEER GELIJKENIS",
                reason=f"Lijkt sterk op standaardclausule {match.clause.code} ({int(match.similarity_score*100)}% match). Controleer of vervanging mogelijk is.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=match.clause.code,
                category="LIBRARY_HIGH_SIMILARITY",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        # Lower match - don't return advice, continue to step 2
        logger.debug(f"Clause library low match: {cluster.id} (score: {match.similarity_score:.0%})")
        return None
