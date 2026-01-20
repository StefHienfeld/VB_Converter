# hienfeld/services/analysis/strategies/clause_library_strategy.py
"""
Step 1: Clause Library Matching Strategy.

Matches cluster text against a library of standard clauses.
High similarity matches result in REPLACE recommendations,
medium matches result in CHECK recommendations.

Thresholds:
- >= 95%: VERWIJDEREN (exact match to standard clause)
- >= 85%: HANDMATIG CHECKEN (similar to standard clause)
"""

from typing import Optional

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.clause_library")


class ClauseLibraryStrategy(IAnalysisStrategy):
    """
    Strategy for Step 1: Clause Library Matching.

    Compares cluster text against a library of standard clauses
    to identify texts that should be replaced or checked.
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
        config = context.config

        # Get thresholds from config
        exact_threshold = config.conditions_match.exact_match_threshold  # 0.95
        check_threshold = config.conditions_match.high_similarity_threshold  # 0.85

        # Find best match in library
        match_result = service.find_best_match(text)

        if match_result is None:
            return None

        matched_clause, score = match_result

        if score < check_threshold:
            # Below threshold, no match
            return None

        # Determine advice based on score
        if score >= exact_threshold:
            # Exact match - replace with standard
            advice_code = AdviceCode.VERWIJDEREN.value
            confidence = ConfidenceLevel.HOOG.value
            reason = f"Exact match met standaardclausule ({score:.0%}): {matched_clause.code}"
        else:
            # Medium match - manual check needed
            advice_code = AdviceCode.HANDMATIG_CHECKEN.value
            confidence = ConfidenceLevel.MIDDEN.value
            reason = f"Vergelijkbaar met standaardclausule ({score:.0%}): {matched_clause.code}"

        # Get category from matched clause
        category = getattr(matched_clause, "category", None) or "LIBRARY"

        advice = AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=advice_code,
            reason=reason,
            confidence=confidence,
            reference_article=matched_clause.code if matched_clause else "-",
            category=category,
            cluster_name=cluster.name,
            frequency=cluster.frequency,
        )

        logger.debug(f"Clause library match: {cluster.id} -> {matched_clause.code} ({score:.0%})")
        return advice
