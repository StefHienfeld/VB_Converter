# hienfeld/services/analysis/strategies/fallback_strategy.py
"""
Step 3: Fallback Strategy.

Handles clusters that didn't match any previous strategy.
Applies keyword rules, frequency analysis, and length checks.

This is the final strategy and always returns an advice.
"""

from typing import Optional

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.fallback")


class FallbackStrategy(IAnalysisStrategy):
    """
    Strategy for Step 3: Fallback Rules.

    Applies when no other strategy matched:
    - Keyword-based rules (config.analysis_rules.keyword_rules)
    - Frequency-based standardization
    - Length-based manual check
    - Default: HANDMATIG CHECKEN

    This strategy always returns an advice (never None).
    """

    @property
    def step_name(self) -> str:
        return "Fallback"

    @property
    def step_order(self) -> float:
        return 3.0

    def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
        """
        Fallback always runs if no previous strategy matched.

        Returns:
            Always True
        """
        return True

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Apply fallback rules to generate advice.

        Order of checks:
        1. Keyword rules (from config)
        2. Frequency-based standardization
        3. Length-based manual check
        4. Default manual check

        Args:
            cluster: Cluster to analyze
            context: Analysis context

        Returns:
            AnalysisAdvice (always returns, never None)
        """
        config = context.config
        text = cluster.leader_text.lower()

        # 1. Check keyword rules
        keyword_advice = self._check_keyword_rules(cluster, text, config)
        if keyword_advice:
            return keyword_advice

        # 2. Check frequency-based standardization
        frequency_advice = self._check_frequency_rules(cluster, config)
        if frequency_advice:
            return frequency_advice

        # 3. Check text length (long texts need manual review)
        length_advice = self._check_length_rules(cluster, config)
        if length_advice:
            return length_advice

        # 4. Default: Manual check
        return self._create_default_advice(cluster, context)

    def _check_keyword_rules(
        self,
        cluster: Cluster,
        text_lower: str,
        config
    ) -> Optional[AnalysisAdvice]:
        """
        Check if any keyword rules match.

        Args:
            cluster: Cluster being analyzed
            text_lower: Lowercase cluster text
            config: Application config with keyword_rules

        Returns:
            AnalysisAdvice if keyword matched, None otherwise
        """
        keyword_rules = getattr(config.analysis_rules, "keyword_rules", {})

        for rule_name, rule_config in keyword_rules.items():
            keywords = rule_config.get("keywords", [])

            # Check if any keyword matches
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    advice_code = rule_config.get("advice", AdviceCode.HANDMATIG_CHECKEN.value)
                    reason = rule_config.get("reason", f"Bevat keyword: {keyword}")
                    confidence = rule_config.get("confidence", ConfidenceLevel.MIDDEN.value)

                    advice = AnalysisAdvice(
                        cluster_id=cluster.id,
                        advice_code=advice_code,
                        reason=reason,
                        confidence=confidence,
                        reference_article="-",
                        category=rule_name.upper(),
                        cluster_name=cluster.name,
                        frequency=cluster.frequency,
                    )

                    logger.debug(f"Keyword match: {cluster.id} -> {rule_name} ('{keyword}')")
                    return advice

        return None

    def _check_frequency_rules(
        self,
        cluster: Cluster,
        config
    ) -> Optional[AnalysisAdvice]:
        """
        Check frequency-based standardization.

        High-frequency clusters may be candidates for standardization.

        Args:
            cluster: Cluster being analyzed
            config: Application config

        Returns:
            AnalysisAdvice if frequency rule applies, None otherwise
        """
        threshold = config.analysis_rules.frequency_standardize_threshold

        if cluster.frequency >= threshold:
            advice = AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.STANDAARDISEREN.value,
                reason=f"Komt {cluster.frequency}x voor - kandidaat voor standaardisatie",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="FREQUENTIE",
                cluster_name=cluster.name,
                frequency=cluster.frequency,
            )

            logger.debug(f"Frequency rule: {cluster.id} -> STANDAARDISEREN ({cluster.frequency}x)")
            return advice

        return None

    def _check_length_rules(
        self,
        cluster: Cluster,
        config
    ) -> Optional[AnalysisAdvice]:
        """
        Check length-based rules.

        Very long texts need manual review as they may contain
        multiple clauses or complex conditions.

        Args:
            cluster: Cluster being analyzed
            config: Application config

        Returns:
            AnalysisAdvice if length rule applies, None otherwise
        """
        max_length = getattr(config.analysis_rules, "max_text_length", 800)
        text = cluster.leader_text

        if len(text) > max_length:
            advice = AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"Lange tekst ({len(text)} tekens) - handmatige controle vereist",
                confidence=ConfidenceLevel.LAAG.value,
                reference_article="-",
                category="LENGTE",
                cluster_name=cluster.name,
                frequency=cluster.frequency,
            )

            logger.debug(f"Length rule: {cluster.id} -> HANDMATIG CHECKEN ({len(text)} chars)")
            return advice

        return None

    def _create_default_advice(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> AnalysisAdvice:
        """
        Create default manual check advice.

        Used when no other rule applies.

        Args:
            cluster: Cluster being analyzed
            context: Analysis context

        Returns:
            Default AnalysisAdvice
        """
        # Determine reason based on context
        if context.has_conditions:
            reason = "Geen overeenkomst met voorwaarden gevonden"
        else:
            reason = "Interne analyse - handmatige controle aanbevolen"

        advice = AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason=reason,
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="ONBEKEND",
            cluster_name=cluster.name,
            frequency=cluster.frequency,
        )

        logger.debug(f"Default fallback: {cluster.id} -> HANDMATIG CHECKEN")
        return advice
