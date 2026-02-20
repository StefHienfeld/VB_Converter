# hienfeld/services/analysis/strategies/conditions_match_strategy.py
"""
Step 2: Policy Conditions Matching Strategy.

Matches cluster text against parsed policy conditions (voorwaarden).
This is the main analysis step that uses multiple strategies to find
matching policy sections and generate appropriate recommendations.

Strategies (in order):
1. Exact substring match - checks if text appears verbatim in conditions
2. Fuzzy match per section - uses hybrid similarity with thresholds
3. Fragment matching - checks significant phrases against conditions
4. Semantic matching - uses embeddings to find same-meaning text

Uses HybridSimilarityService for multi-method matching:
- RapidFuzz (fuzzy string matching)
- Lemmatized text (NLP normalization)
- TF-IDF (document similarity)
- Synonyms (domain-specific term matching)
- Embeddings (semantic similarity)

SYNCED with AnalysisService._step2_conditions_check (v4.5)
"""

from typing import Optional, Tuple, List, Dict, Any

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.services.analysis.formatters.reference_formatter import ReferenceFormatter
from hienfeld.logging_config import get_logger

logger = get_logger("strategy.conditions_match")

# Thresholds (should match config.analysis_rules.conditions_match)
EXACT_MATCH_THRESHOLD = 0.95
HIGH_SIMILARITY_THRESHOLD = 0.85
MEDIUM_SIMILARITY_THRESHOLD = 0.75
SEMANTIC_MATCH_THRESHOLD = 0.70
SEMANTIC_HIGH_THRESHOLD = 0.85


class ConditionsMatchStrategy(IAnalysisStrategy):
    """
    Strategy for Step 2: Policy Conditions Matching.

    Compares cluster text against policy conditions using multiple
    strategies to find the best matching section.

    Thresholds:
    - >= 95%: VERWIJDEREN (exact match, high confidence)
    - >= 85%: VERWIJDEREN (high similarity, medium confidence)
    - >= 75%: HANDMATIG CHECKEN (medium similarity)
    - >= 50%: HANDMATIG CHECKEN (semantic possible match)
    - < 50%: No match (continue to fallback)
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
        Match cluster against policy conditions using 4 strategies.

        Args:
            cluster: Cluster to analyze
            context: Analysis context with policy_sections

        Returns:
            AnalysisAdvice if conditions match found, None otherwise
        """
        if not context.policy_sections:
            return None

        simple_text = cluster.leader_text
        if not simple_text or len(simple_text) < 20:
            return None

        # Strategy 1: Exact substring match
        advice = self._strategy1_exact_substring(cluster, simple_text, context)
        if advice:
            return advice

        # Strategy 2: Fuzzy match per section
        advice = self._strategy2_fuzzy_match(cluster, simple_text, context)
        if advice:
            return advice

        # Strategy 3: Fragment matching
        advice = self._strategy3_fragment_match(cluster, simple_text, context)
        if advice:
            return advice

        # Strategy 4: Semantic matching
        advice = self._strategy4_semantic_match(cluster, simple_text, context)
        if advice:
            return advice

        return None

    def _strategy1_exact_substring(
        self,
        cluster: Cluster,
        text: str,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Strategy 1: Check if text appears exactly in conditions.

        This is the fastest check - if the exact text appears somewhere
        in the policy conditions, it's definitely covered.
        """
        if not context.policy_full_text:
            return None

        if text not in context.policy_full_text:
            return None

        # Find which section contains this text
        matching_section = self._find_section_containing_text(text, context)

        if not matching_section:
            # Text spans section boundaries, fall back to fuzzy match
            return None

        reference = self._reference_formatter.format_reference(matching_section)

        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.VERWIJDEREN.value,
            reason="Tekst komt EXACT voor in de voorwaarden. Kan verwijderd worden.",
            confidence=ConfidenceLevel.HOOG.value,
            reference_article=reference,
            category="CONDITIONS_EXACT",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )

    def _strategy2_fuzzy_match(
        self,
        cluster: Cluster,
        text: str,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Strategy 2: Fuzzy match against each section.

        Uses hybrid similarity (if available) or base similarity
        to find the best matching section.
        """
        best_match = self._find_best_section_match(text, context)

        if not best_match:
            return None

        score, section = best_match
        reference = self._reference_formatter.format_reference(section)

        # Get thresholds from config
        config = context.config
        exact_threshold = getattr(
            config.conditions_match, 'exact_match_threshold', EXACT_MATCH_THRESHOLD
        )
        high_threshold = getattr(
            config.conditions_match, 'high_similarity_threshold', HIGH_SIMILARITY_THRESHOLD
        )
        medium_threshold = getattr(
            config.conditions_match, 'medium_similarity_threshold', MEDIUM_SIMILARITY_THRESHOLD
        )

        if score >= exact_threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Tekst komt bijna letterlijk voor in voorwaarden ({int(score*100)}% match). Kan verwijderd worden.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article=reference,
                category="CONDITIONS_NEAR_EXACT",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        if score >= high_threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Tekst lijkt sterk op {reference} ({int(score*100)}% match). Controleer en verwijder indien identiek.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=reference,
                category="CONDITIONS_HIGH_SIMILARITY",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        if score >= medium_threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"Vertoont gelijkenis met {reference} ({int(score*100)}% match). Controleer of dit een variant is.",
                confidence=ConfidenceLevel.LAAG.value,
                reference_article=reference,
                category="CONDITIONS_MEDIUM_SIMILARITY",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        if score >= 0.50:
            # Lower threshold for hybrid similarity (paraphrases)
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"Mogelijke overlap met {reference} ({int(score*100)}% semantische match). Controleer of betekenis identiek is.",
                confidence=ConfidenceLevel.LAAG.value,
                reference_article=reference,
                category="CONDITIONS_SEMANTIC_MATCH",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        return None

    def _strategy3_fragment_match(
        self,
        cluster: Cluster,
        text: str,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Strategy 3: Check significant fragments against conditions.

        Looks for important phrases (e.g., coverage terms, exclusions)
        that appear in both the text and conditions.
        """
        # Get significant fragments from the text
        fragments = self._extract_significant_fragments(text)

        if not fragments:
            return None

        # Check each fragment against conditions
        for fragment in fragments:
            if len(fragment) < 15:
                continue

            if context.policy_full_text and fragment.lower() in context.policy_full_text.lower():
                # Find which section contains this fragment
                section = self._find_section_containing_text(fragment.lower(), context)
                reference = self._reference_formatter.format_reference(section) if section else "Voorwaarden"

                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Belangrijke passage '{fragment[:50]}...' komt voor in {reference}.",
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=reference,
                    category="CONDITIONS_FRAGMENTS",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )

        return None

    def _strategy4_semantic_match(
        self,
        cluster: Cluster,
        text: str,
        context: AnalysisContext
    ) -> Optional[AnalysisAdvice]:
        """
        Strategy 4: Semantic similarity check using embeddings.

        Uses embeddings to find policy sections with the same MEANING,
        even when the text is written differently.
        """
        if not context.semantic_service:
            return None

        if not context.semantic_index_ready:
            return None

        # Find semantically similar sections
        try:
            matches = context.semantic_service.find_similar(
                text,
                top_k=3,
                min_score=SEMANTIC_MATCH_THRESHOLD
            )
        except Exception as e:
            logger.debug(f"Semantic search failed: {e}")
            return None

        if not matches:
            return None

        best_match = matches[0]
        logger.debug(
            f"Semantic match found for cluster {cluster.id}: "
            f"{best_match.text_id} (score: {best_match.score:.2f})"
        )

        # Look up section for reference
        section = context.section_lookup.get(best_match.text_id) if context.section_lookup else None
        reference = self._reference_formatter.format_reference(section) if section else best_match.text_id

        if best_match.score >= SEMANTIC_HIGH_THRESHOLD:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Semantisch identiek aan {reference} ({int(best_match.score*100)}% betekenis-match). Tekst heeft dezelfde betekenis als de voorwaarden.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=reference,
                category="CONDITIONS_SEMANTIC_MATCH",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        # Lower semantic scores - suggest manual review
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason=f"Mogelijke semantische overlap met {reference} ({int(best_match.score*100)}% betekenis-match). Controleer of de betekenis identiek is.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article=reference,
            category="CONDITIONS_SEMANTIC_POSSIBLE",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )

    def _find_section_containing_text(
        self,
        text: str,
        context: AnalysisContext
    ) -> Optional[PolicyDocumentSection]:
        """Find the section that contains the given text."""
        text_lower = text.lower()

        for section in context.policy_sections:
            if section.simplified_text and text_lower in section.simplified_text.lower():
                return section

        return None

    def _find_best_section_match(
        self,
        text: str,
        context: AnalysisContext
    ) -> Optional[Tuple[float, PolicyDocumentSection]]:
        """
        Find the best matching policy section using similarity services.

        Returns:
            Tuple of (score, section) or None if no match found
        """
        best_section: Optional[PolicyDocumentSection] = None
        best_score: float = 0.0

        # Get similarity service (prefer hybrid, fall back to base)
        similarity_service = context.hybrid_service or context.similarity_service

        if similarity_service is None:
            return None

        # Compare against each section
        for section in context.policy_sections:
            if not section.simplified_text:
                continue

            try:
                score = similarity_service.similarity(text, section.simplified_text)
            except Exception:
                continue

            if score > best_score:
                best_score = score
                best_section = section

        if best_section is None or best_score < 0.50:
            return None

        return best_score, best_section

    def _extract_significant_fragments(self, text: str) -> List[str]:
        """
        Extract significant phrases from text that might appear in conditions.

        Looks for:
        - Sentences with coverage keywords
        - Exclusion phrases
        - Amount/limit specifications
        """
        fragments: List[str] = []

        # Split into sentences
        import re
        sentences = re.split(r'[.!?]+', text)

        coverage_keywords = [
            'dekking', 'verzeker', 'uitsluit', 'niet gedekt',
            'geen dekking', 'eigen risico', 'maximum', 'limiet'
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue

            # Check for coverage keywords
            sentence_lower = sentence.lower()
            if any(kw in sentence_lower for kw in coverage_keywords):
                fragments.append(sentence)

        return fragments[:5]  # Limit to 5 most relevant
