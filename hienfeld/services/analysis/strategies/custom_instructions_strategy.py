# hienfeld/services/analysis/strategies/custom_instructions_strategy.py
"""
Step 0.5: Custom Instructions Strategy.

Matches cluster text against user-defined custom instructions.
This step runs before standard analysis to allow users to override
the default analysis behavior for specific text patterns.
"""

from typing import Optional

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.custom_instructions")


class CustomInstructionsStrategy(IAnalysisStrategy):
    """
    Strategy for Step 0.5: Custom Instructions.

    Matches cluster text against user-provided instructions.
    Uses contains matching (primary) with fuzzy/semantic fallback.

    Custom instructions format:
    - TSV: "zoektekst<TAB>actie"
    - Arrow: "zoektekst\n-> actie"
    """

    @property
    def step_name(self) -> str:
        return "Custom Instructions"

    @property
    def step_order(self) -> float:
        return 0.5

    def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
        """
        Only runs if custom instructions are loaded.

        Returns:
            True if custom instructions service is available and has instructions
        """
        service = context.custom_instructions_service
        if service is None:
            return False

        # Check if service has instructions loaded
        is_loaded = getattr(service, "is_loaded", False)
        return is_loaded

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Match cluster against custom instructions.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with custom_instructions_service

        Returns:
            AnalysisAdvice if instruction matches, None otherwise
        """
        service = context.custom_instructions_service
        if not service:
            return None

        text = cluster.leader_text

        # Find matching instruction
        match_result = service.find_match(text)

        if match_result is None:
            return None

        # Build advice from match
        instruction = match_result.instruction
        score = match_result.score
        action = instruction.action

        # Add emoji prefix to indicate custom instruction match
        advice_code = f"📋 {action}"

        # Build reason with match details
        search_text = instruction.search_text
        if score >= 1.0:
            reason = f"Komt overeen met instructie: '{search_text}' (100% match)"
        else:
            reason = f"Komt overeen met instructie: '{search_text}' ({score:.0%} match)"

        advice = AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=advice_code,
            reason=reason,
            confidence=ConfidenceLevel.HOOG.value if score >= 0.9 else ConfidenceLevel.MIDDEN.value,
            reference_article="-",
            category="CUSTOM",
            cluster_name=cluster.name,
            frequency=cluster.frequency,
        )

        logger.debug(f"Custom instruction match: {cluster.id} -> {action} ({score:.0%})")
        return advice
