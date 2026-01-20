# hienfeld/services/analysis/strategies/admin_check_strategy.py
"""
Step 0: Administrative/Hygiene Check Strategy.

Checks for administrative issues before content analysis:
- Empty or whitespace-only text
- Text too short to analyze
- Dates in the past (expired clauses)
- Placeholder text ([INVULLEN], XXX, etc.)
- Encoding problems
"""

from typing import Optional

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.admin_check")


class AdminCheckStrategy(IAnalysisStrategy):
    """
    Strategy for Step 0: Administrative/Hygiene Check.

    Identifies texts that have administrative issues and should not
    proceed through content analysis:
    - Empty text -> LEEG
    - Expired dates -> VERWIJDEREN (VERLOPEN)
    - Placeholders -> AANVULLEN
    - Corrupt/unreadable -> ONLEESBAAR
    """

    @property
    def step_name(self) -> str:
        return "Admin Check"

    @property
    def step_order(self) -> float:
        return 0.0

    def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
        """
        Always runs - admin checks apply to all clusters.

        Returns:
            True if admin check service is available
        """
        return context.admin_check_service is not None

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Perform administrative/hygiene checks on the cluster.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with admin_check_service

        Returns:
            AnalysisAdvice if admin issue found, None otherwise
        """
        if not context.admin_check_service:
            return None

        text = cluster.leader_text

        # Perform admin check
        result = context.admin_check_service.check_text(text)

        if not result.has_issues:
            return None

        # Map admin issue to advice
        recommendation = result.recommendation
        if recommendation is None:
            return None

        # Get the primary issue description
        primary_issue = result.primary_issue
        reason = primary_issue.description if primary_issue else "Administratief probleem gedetecteerd"

        advice = AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=recommendation.value,
            reason=reason,
            confidence=ConfidenceLevel.HOOG.value,
            reference_article="-",
            category="ADMIN",
            cluster_name=cluster.name,
            frequency=cluster.frequency,
        )

        logger.debug(f"Admin check: {cluster.id} -> {recommendation.value}")
        return advice
