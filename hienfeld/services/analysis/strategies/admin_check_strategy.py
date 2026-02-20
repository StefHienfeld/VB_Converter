# hienfeld/services/analysis/strategies/admin_check_strategy.py
"""
Step 0: Administrative/Hygiene Check Strategy.

Checks for administrative issues before content analysis:
- Empty or whitespace-only text
- Text too short to analyze (<10 chars)
- Text too long (>max_text_length)
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

# Minimum text length for analysis
MIN_TEXT_LENGTH = 10


class AdminCheckStrategy(IAnalysisStrategy):
    """
    Strategy for Step 0: Administrative/Hygiene Check.

    Identifies texts that have administrative issues and should not
    proceed through content analysis:
    - Too short (<10 chars) -> HANDMATIG CHECKEN
    - Too long (>max_text_length) -> HANDMATIG CHECKEN
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
        Always runs - basic length checks apply even without AdminCheckService.

        Returns:
            True always (basic checks always run)
        """
        return True

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Perform administrative/hygiene checks on the cluster.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with optional admin_check_service

        Returns:
            AnalysisAdvice if admin issue found, None otherwise
        """
        text = cluster.original_text
        simple_text = cluster.leader_text

        # PRE-CHECK 1: Text too short
        if len(simple_text) < MIN_TEXT_LENGTH:
            logger.debug(f"Admin check: {cluster.id} -> text too short ({len(simple_text)} chars)")
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason="Tekst te kort voor automatische analyse.",
                confidence=ConfidenceLevel.LAAG.value,
                reference_article="-",
                category="SHORT_TEXT",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        # PRE-CHECK 2: Text too long
        max_length = context.config.analysis_rules.max_text_length
        if len(text) > max_length:
            logger.debug(f"Admin check: {cluster.id} -> text too long ({len(text)} chars)")
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"Tekst te lang voor automatische analyse ({len(text)} karakters, max {max_length})",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="-",
                category="LONG_TEXT",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        # Use AdminCheckService for additional checks if available
        if context.admin_check_service:
            result, advice = context.admin_check_service.check_cluster(cluster)
            if advice is not None:
                logger.debug(f"Admin check: {cluster.id} -> {advice.advice_code}")
                return advice

        return None
