# hienfeld/services/analysis/strategies/fallback_strategy.py
"""
Step 3: Fallback Analysis Strategy.

Final step when no library or conditions match is found.
Uses keyword rules, frequency analysis, reference analysis,
or AI analysis to generate recommendations.

SYNCED with AnalysisService._step3_fallback_analysis (v4.5)
"""

from typing import Optional, Dict, Any

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.fallback")


class FallbackStrategy(IAnalysisStrategy):
    """
    Strategy for Step 3: Fallback Analysis.

    This is always the last strategy in the pipeline. It handles
    clusters that weren't matched by library or conditions checks.

    Analysis methods (in order):
    1. Keyword rules - matches specific terms to advice codes
    2. Reference analysis - checks previous analysis results
    3. Frequency analysis - standardize high-frequency clauses
    4. AI analysis - optional LLM-based analysis
    5. Internal fallback - frequency-based advice when no conditions
    """

    @property
    def step_name(self) -> str:
        return "Fallback"

    @property
    def step_order(self) -> float:
        return 3.0

    def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
        """
        Fallback always runs as last resort.

        Returns:
            True always - this is the catch-all strategy
        """
        return True

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Perform fallback analysis using multiple methods.

        Args:
            cluster: Cluster to analyze
            context: Analysis context

        Returns:
            AnalysisAdvice (never returns None - always provides advice)
        """
        text = cluster.original_text
        simple_text = cluster.leader_text
        frequency = cluster.frequency

        # Method 1: Keyword-based rules
        advice = self._check_keyword_rules(cluster, simple_text, context)
        if advice:
            return advice

        # Method 2: Reference analysis (if reference file was provided)
        advice = self._check_reference_analysis(cluster, simple_text, context)
        if advice:
            return advice

        # Method 3: Frequency-based standardization
        advice = self._check_frequency_standardization(cluster, frequency, context)
        if advice:
            return advice

        # Method 4: AI analysis (if available)
        advice = self._try_ai_analysis(cluster, context)
        if advice:
            return advice

        # Method 5: Final fallback based on mode
        if not context.policy_sections:
            return self._internal_analysis_fallback(cluster, frequency, context)

        # Default: manual check
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason="Geen automatische match gevonden. Beoordeel handmatig of dit maatwerk is.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="NO_MATCH",
            cluster_name=cluster.name,
            frequency=frequency
        )

    def _check_keyword_rules(
        self,
        cluster: Cluster,
        simple_text: str,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Check keyword-based rules from configuration.

        Rules are defined in config.analysis_rules.keyword_rules
        and map specific terms to advice codes.
        """
        config = context.config
        rules = getattr(config.analysis_rules, 'keyword_rules', {})

        for rule_name, rule_config in rules.items():
            keywords = rule_config.get('keywords', [])

            # Check if any keyword matches
            if not any(kw in simple_text for kw in keywords):
                continue

            # Check inclusion keywords (if specified, at least one must match)
            inclusion_keywords = rule_config.get('inclusion_keywords')
            if inclusion_keywords:
                if not any(kw in simple_text for kw in inclusion_keywords):
                    continue

            # Check max length constraint
            max_length = rule_config.get('max_length')
            if max_length and len(simple_text) > max_length:
                continue

            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=rule_config.get('advice', 'HANDMATIG CHECKEN'),
                reason=rule_config.get('reason', 'Keyword match'),
                confidence=rule_config.get('confidence', 'Midden'),
                reference_article=rule_config.get('article', '-'),
                category=f"KEYWORD_{rule_name.upper()}",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        return None

    def _check_reference_analysis(
        self,
        cluster: Cluster,
        simple_text: str,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Check reference analysis for frequency inheritance.

        If a reference file was provided and the same clause had high
        frequency in the reference, recommend standardization.
        """
        if not context.reference_service:
            return None

        try:
            ref_match = context.reference_service.find_match(simple_text)
        except Exception:
            return None

        if not ref_match:
            return None

        threshold = context.config.analysis_rules.frequency_standardize_threshold
        ref_freq = ref_match.reference_clause.frequency

        if ref_freq >= threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.STANDAARDISEREN.value,
                reason=f"Komt {cluster.frequency}x voor (jaaroverzicht: {ref_freq}x). "
                       f"Volgens referentie-analyse standaardiseren.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="Ref: Standaardiseren",
                category="FREQUENT_REF",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        return None

    def _check_frequency_standardization(
        self,
        cluster: Cluster,
        frequency: int,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Check if cluster should be standardized based on frequency.

        High-frequency clauses (>= threshold) should become standard
        clause codes for consistency.
        """
        threshold = context.config.analysis_rules.frequency_standardize_threshold

        if frequency >= threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.STANDAARDISEREN.value,
                reason=f"Komt vaak voor ({frequency}x). Maak hiervan een standaard clausulecode.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="Nieuw",
                category="FREQUENT",
                cluster_name=cluster.name,
                frequency=frequency
            )

        return None

    def _try_ai_analysis(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Try AI-enhanced analysis if available.

        Uses the LLM analyzer to understand the clause semantically
        and provide a recommendation.
        """
        if not context.ai_analyzer:
            return None

        try:
            return context.ai_analyzer.analyze_cluster_with_context(
                cluster,
                context.policy_sections
            )
        except Exception as e:
            logger.warning(f"AI analysis failed for cluster {cluster.id}: {e}")
            return None

    def _internal_analysis_fallback(
        self,
        cluster: Cluster,
        frequency: int,
        context: AnalysisContext
    ) -> AnalysisAdvice:
        """
        Provide useful analysis when no conditions are uploaded.

        This mode is useful for internal analysis where we only
        want to understand clause frequency distribution.
        """
        if frequency == 1:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.UNIEK.value,
                reason="Komt slechts 1x voor. Mogelijk maatwerk of eenmalige afwijking.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="UNIQUE",
                cluster_name=cluster.name,
                frequency=frequency
            )

        if frequency <= 5:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.CONSISTENTIE_CHECK.value,
                reason=f"Komt {frequency}x voor. Controleer of dit varianten zijn van dezelfde clausule.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="LOW_FREQUENCY",
                cluster_name=cluster.name,
                frequency=frequency
            )

        threshold = context.config.analysis_rules.frequency_standardize_threshold

        if frequency < threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.FREQUENTIE_INFO.value,
                reason=f"Komt {frequency}x voor. Onder standaardisatie-drempel ({threshold}).",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="MEDIUM_FREQUENCY",
                cluster_name=cluster.name,
                frequency=frequency
            )

        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.FREQUENTIE_INFO.value,
            reason=f"Komt {frequency}x voor.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="FREQUENCY_INFO",
            cluster_name=cluster.name,
            frequency=frequency
        )
