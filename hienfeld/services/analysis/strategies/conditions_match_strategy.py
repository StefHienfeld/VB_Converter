# hienfeld/services/analysis/strategies/conditions_match_strategy.py
"""
Step 2: Policy Conditions Matching Strategy.

Matches cluster text against parsed policy conditions (voorwaarden).
This is the main analysis step that uses hybrid similarity to find
matching policy sections and generate appropriate recommendations.

Uses HybridSimilarityService for multi-method matching:
- RapidFuzz (fuzzy string matching)
- Lemmatized text (NLP normalization)
- TF-IDF (document similarity)
- Synonyms (domain-specific term matching)
- Embeddings (semantic similarity)
"""

from typing import Optional, Tuple, List

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.services.analysis.formatters.reference_formatter import ReferenceFormatter
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.conditions_match")


class ConditionsMatchStrategy(IAnalysisStrategy):
    """
    Strategy for Step 2: Policy Conditions Matching.

    Compares cluster text against policy conditions using hybrid
    similarity to find the best matching section.

    Thresholds (from config):
    - >= 95%: VERWIJDEREN (exact match)
    - >= 85%: VERWIJDEREN + check (high similarity)
    - >= 75%: HANDMATIG CHECKEN (medium similarity)
    - < 75%: No match (continue to fallback)
    """

    def __init__(self) -> None:
        self._reference_formatter = ReferenceFormatter()

    @property
    def step_name(self) -> str:
        return "Conditions Match"

    @property
    def step_order(self) -> float:
        return 2.0

    def can_handle(self, cluster: Cluster, context: AnalysisContext) -> bool:
        """
        Only runs if policy conditions are available.

        Returns:
            True if policy sections exist
        """
        return context.has_conditions

    def analyze(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Match cluster against policy conditions.

        Uses hybrid similarity to find the best matching policy section.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with policy_sections

        Returns:
            AnalysisAdvice if conditions match found, None otherwise
        """
        if not context.policy_sections:
            return None

        text = cluster.leader_text
        config = context.config

        # Get thresholds
        exact_threshold = config.conditions_match.exact_match_threshold  # 0.95
        high_threshold = config.conditions_match.high_similarity_threshold  # 0.85
        medium_threshold = config.conditions_match.medium_similarity_threshold  # 0.75

        # Find best matching section
        best_match, score = self._find_best_match(text, context)

        if best_match is None or score < medium_threshold:
            # No match above threshold
            return None

        # Determine advice based on score
        if score >= exact_threshold:
            advice_code = AdviceCode.VERWIJDEREN.value
            confidence = ConfidenceLevel.HOOG.value
            reason_prefix = "Exacte match"
        elif score >= high_threshold:
            advice_code = AdviceCode.VERWIJDEREN.value
            confidence = ConfidenceLevel.MIDDEN.value
            reason_prefix = "Hoge overeenkomst"
        else:
            # Medium similarity
            advice_code = AdviceCode.HANDMATIG_CHECKEN.value
            confidence = ConfidenceLevel.LAAG.value
            reason_prefix = "Gedeeltelijke overeenkomst"

        # Format reference
        reference = self._reference_formatter.format_reference(best_match)
        category = self._extract_category(best_match)

        # Build reason
        reason = f"{reason_prefix} ({score:.0%}) met {reference}"

        advice = AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=advice_code,
            reason=reason,
            confidence=confidence,
            reference_article=reference,
            category=category,
            cluster_name=cluster.name,
            frequency=cluster.frequency,
        )

        logger.debug(f"Conditions match: {cluster.id} -> {reference} ({score:.0%})")
        return advice

    def _find_best_match(
        self,
        text: str,
        context: AnalysisContext
    ) -> Tuple[Optional[PolicyDocumentSection], float]:
        """
        Find the best matching policy section using available similarity services.

        Args:
            text: Text to match
            context: Analysis context with similarity services

        Returns:
            Tuple of (best_section, score) or (None, 0.0)
        """
        best_section: Optional[PolicyDocumentSection] = None
        best_score: float = 0.0

        # Get similarity service (prefer hybrid, fall back to base)
        similarity_service = context.hybrid_service or context.similarity_service

        if similarity_service is None:
            return None, 0.0

        # Compare against each section
        for section in context.policy_sections:
            if not section.simplified_text:
                continue

            score = similarity_service.similarity(text, section.simplified_text)

            if score > best_score:
                best_score = score
                best_section = section

        return best_section, best_score

    def _extract_category(self, section: PolicyDocumentSection) -> str:
        """
        Extract category from the matched section.

        Looks for category hints in section title, source file, or metadata.

        Args:
            section: Matched policy section

        Returns:
            Category string or "VOORWAARDEN"
        """
        if section.source_file:
            # Try to extract category from filename
            source = section.source_file.lower()
            if "brand" in source:
                return "BRAND"
            if "aansprak" in source:
                return "AANSPRAKELIJKHEID"
            if "diefstal" in source:
                return "DIEFSTAL"
            if "molest" in source:
                return "MOLEST"
            if "fraude" in source:
                return "FRAUDE"

        if section.article_title:
            # Try to extract from title
            title = section.article_title.lower()
            if "uitsluit" in title or "geen dekking" in title:
                return "UITSLUITINGEN"
            if "dekking" in title:
                return "DEKKING"

        return "VOORWAARDEN"
