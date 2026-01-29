# hienfeld/services/reference_analysis_service.py
"""
Service for loading, parsing, and comparing reference analysis data.

Enables comparison between current (monthly) analysis and a previous
(yearly) reference analysis to maintain frequency-based recommendations.
"""
from typing import Optional, List, Dict, Tuple
from io import BytesIO
import pandas as pd
from rapidfuzz import process, fuzz

from ..config import AppConfig
from ..domain.reference import (
    ReferenceClause,
    ReferenceMatch,
    ReferenceData,
    ComparisonStatus,
    get_comparison_status,
)
from ..logging_config import get_logger
from .similarity_service import SimilarityService

logger = get_logger('reference_analysis_service')


class ReferenceAnalysisService:
    """
    Service for loading, parsing, and comparing reference analysis data.

    Responsibilities:
    - Parse VB Converter Excel output files
    - Match current clauses to reference clauses
    - Calculate combined frequency recommendations
    - Track "verdwenen teksten" (gone texts)

    Usage:
        service = ReferenceAnalysisService(config, similarity_service)
        service.load_reference_file(file_bytes, filename)
        match = service.find_match("some text")
        gone = service.get_gone_texts()
    """

    # Expected column names in VB Converter output
    COLUMN_MAPPINGS = {
        'text': ['Tekst', 'tekst', 'Text', 'text', 'Vrije Tekst', 'vrije tekst'],
        'frequency': ['Frequentie', 'frequentie', 'Frequency', 'frequency', 'Freq', 'freq'],
        'orig_frequency': ['Orig. Frequentie', 'orig. frequentie', 'Original Frequency', 'OrigFrequentie'],
        'advice': ['Advies', 'advies', 'Advice', 'advice'],
        'cluster_name': ['Cluster_Naam', 'cluster_naam', 'Cluster Naam', 'ClusterNaam', 'Cluster_ID'],
        'confidence': ['Vertrouwen', 'vertrouwen', 'Confidence', 'confidence'],
        'reason': ['Reden', 'reden', 'Reason', 'reason'],
        'article': ['Artikel', 'artikel', 'Article', 'article'],
        'policy_number': ['Polisnummer', 'polisnummer', 'Polis', 'polis', 'Policy', 'policy', 'PolicyNumber'],
        'status': ['Status', 'status', 'Actie Gedaan', 'ActieGedaan'],
    }

    def __init__(
        self,
        config: AppConfig,
        similarity_service: SimilarityService,
        hybrid_similarity_service: Optional['HybridSimilarityService'] = None
    ):
        """
        Initialize the reference analysis service.

        Args:
            config: Application configuration
            similarity_service: Service for fuzzy text matching
            hybrid_similarity_service: Optional hybrid service for semantic matching
        """
        self.config = config
        self.similarity_service = similarity_service
        self.hybrid_similarity_service = hybrid_similarity_service

        self._reference_data: Optional[ReferenceData] = None
        self._match_cache: Dict[str, Optional[ReferenceMatch]] = {}
        self._fuzzy_choices: Optional[Dict[str, ReferenceClause]] = None
        self._fuzzy_choices_list: Optional[List[str]] = None  # FIX: Cache the list too

    @property
    def is_loaded(self) -> bool:
        """Check if reference data is loaded."""
        return self._reference_data is not None and len(self._reference_data.clauses) > 0

    def load_reference_file(
        self,
        file_bytes: bytes,
        filename: str
    ) -> ReferenceData:
        """
        Load and parse a VB Converter Excel output file.

        Expected columns (from ExportService output):
        - Tekst (or Cluster_Naam for matching)
        - Frequentie
        - Advies
        - Vertrouwen (optional)
        - Reden (optional)
        - Artikel (optional)

        Args:
            file_bytes: Raw file content
            filename: Original filename

        Returns:
            ReferenceData with parsed clauses
        """
        logger.info(f"Loading reference file: {filename}")

        try:
            # Read Excel file
            df = pd.read_excel(BytesIO(file_bytes), sheet_name=0)
            logger.info(f"Reference file columns: {list(df.columns)}")

            # Find required columns
            text_col = self._find_column(df, 'text')
            freq_col = self._find_column(df, 'frequency')
            advice_col = self._find_column(df, 'advice')

            if not text_col:
                raise ValueError("Geen 'Tekst' kolom gevonden in referentie bestand")
            if not advice_col:
                raise ValueError("Geen 'Advies' kolom gevonden in referentie bestand")

            # Find optional columns
            cluster_col = self._find_column(df, 'cluster_name')
            confidence_col = self._find_column(df, 'confidence')
            reason_col = self._find_column(df, 'reason')
            article_col = self._find_column(df, 'article')
            policy_col = self._find_column(df, 'policy_number')
            orig_freq_col = self._find_column(df, 'orig_frequency')
            status_col = self._find_column(df, 'status')

            if policy_col:
                logger.info(f"Found policy number column: {policy_col}")
            if orig_freq_col:
                logger.info(f"Found original frequency column: {orig_freq_col} (will use for UNIEK clusters)")

            # Parse rows into ReferenceClause objects
            clauses = []
            seen_keys = set()  # Track unique text+policy combinations to avoid duplicates

            for idx, row in df.iterrows():
                text = str(row.get(text_col, "")).strip()

                # Skip empty rows
                if not text or text == "nan":
                    continue

                simplified = self._simplify_text(text)
                policy_number = ""
                if policy_col and pd.notna(row.get(policy_col)):
                    policy_number = str(row[policy_col]).strip()

                # Skip duplicates (use text + policy_number for deduplication)
                # This allows same text on different policies to be stored separately
                dedup_key = f"{simplified}|{policy_number}" if policy_number else simplified
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                # Parse frequency (default to 1 if missing)
                # IMPORTANT: Prefer orig_frequency over frequency for UNIEK clusters
                # This ensures we get the real frequency (1) instead of cluster size (625)
                frequency = 1
                if orig_freq_col and pd.notna(row.get(orig_freq_col)):
                    # Use original frequency (pre-grouping) if available
                    try:
                        frequency = int(row[orig_freq_col])
                    except (ValueError, TypeError):
                        frequency = 1
                elif freq_col and pd.notna(row.get(freq_col)):
                    try:
                        frequency = int(row[freq_col])
                    except (ValueError, TypeError):
                        frequency = 1

                # Parse advice
                advice = str(row.get(advice_col, "")).strip()

                # Create clause
                clause = ReferenceClause(
                    text=text,
                    simplified_text=simplified,
                    frequency=frequency,
                    advice_code=advice,
                    cluster_name=str(row.get(cluster_col, "")).strip() if cluster_col else "",
                    confidence=str(row.get(confidence_col, "")).strip() if confidence_col else "",
                    reason=str(row.get(reason_col, "")).strip() if reason_col else "",
                    reference_article=str(row.get(article_col, "")).strip() if article_col else "",
                    policy_number=policy_number,
                    status=str(row.get(status_col, "")).strip() if status_col else "",
                )
                clauses.append(clause)

            # Create reference data
            self._reference_data = ReferenceData(
                clauses=clauses,
                source_filename=filename,
                total_rows=len(df),
            )
            self._reference_data.build_indexes()

            # Clear caches
            self._match_cache = {}
            self._fuzzy_choices = None  # Will be rebuilt on first find_match call
            self._fuzzy_choices_list = None  # FIX: Also clear the cached list

            logger.info(
                f"Reference loaded: {len(clauses)} unique texts from {len(df)} rows"
            )

            return self._reference_data

        except Exception as e:
            logger.error(f"Failed to load reference file: {e}")
            raise ValueError(f"Kon referentie bestand niet laden: {e}")

    def find_match(
        self,
        text: str,
        policy_number: Optional[str] = None,
        min_score: float = 0.90
    ) -> Optional[ReferenceMatch]:
        """
        Find the best matching reference clause for a given text.

        Matching strategy (in order of speed):
        0. Exact match on simplified_text + policy_number (O(1) hash lookup) - NEW
        1. Exact match on simplified_text only (O(1) hash lookup)
        2. Fuzzy match via RapidFuzz (threshold: min_score)
        3. Semantic match via hybrid service (if available, for borderline cases)

        Args:
            text: Text to match
            policy_number: Optional policy number for per-policy matching
            min_score: Minimum similarity score (default: 0.90)

        Returns:
            ReferenceMatch if found, None otherwise
        """
        if not self.is_loaded:
            return None

        simplified = self._simplify_text(text)

        # Build cache key including policy number for per-policy caching
        cache_key = f"{simplified}|{policy_number}" if policy_number else simplified
        if cache_key in self._match_cache:
            return self._match_cache[cache_key]

        # TIER 0: Exact match on text + policy_number (O(1)) - NEW
        if policy_number:
            policy_match = self._reference_data.get_by_text_and_policy(simplified, policy_number)
            if policy_match:
                policy_match.mark_matched()
                result = ReferenceMatch(
                    reference_clause=policy_match,
                    match_type="exact_policy",
                    match_score=1.0,
                )
                self._match_cache[cache_key] = result
                return result

        # TIER 1: Exact match on text only (O(1))
        exact_match = self._reference_data.get_by_text(simplified)
        if exact_match:
            exact_match.mark_matched()
            result = ReferenceMatch(
                reference_clause=exact_match,
                match_type="exact",
                match_score=1.0,
            )
            self._match_cache[cache_key] = result
            return result

        # TIER 2: Fast fuzzy match using RapidFuzz extractOne (optimized C implementation)
        # Build choices dict for fast lookup: {simplified_text: clause}
        if self._fuzzy_choices is None:
            self._fuzzy_choices = {c.simplified_text: c for c in self._reference_data.clauses}
            # FIX: Cache the list once instead of creating it every call (was O(n) overhead per call!)
            self._fuzzy_choices_list = list(self._fuzzy_choices.keys())

        # Use RapidFuzz's extractOne - much faster than manual iteration
        # FIX: Use cached list instead of creating new list each call
        if self._fuzzy_choices_list:
            match_result = process.extractOne(
                simplified,
                self._fuzzy_choices_list,
                scorer=fuzz.ratio,
                score_cutoff=min_score * 100  # RapidFuzz uses 0-100 scale
            )

            if match_result:
                matched_text, score, _ = match_result
                ref_clause = self._fuzzy_choices[matched_text]

                # FIX: Mark as matched for gone_texts tracking, but ALWAYS return the match!
                # Previous bug: if is_matched was True, returned None instead of match
                if not ref_clause.is_matched:
                    ref_clause.mark_matched()

                # Always create and cache the result (even if ref_clause was already matched)
                result = ReferenceMatch(
                    reference_clause=ref_clause,
                    match_type="fuzzy",
                    match_score=score / 100.0,  # Convert back to 0-1 scale
                )
                self._match_cache[cache_key] = result
                return result

        # No match found
        self._match_cache[cache_key] = None
        return None

    def get_combined_frequency(
        self,
        current_frequency: int,
        reference_match: Optional[ReferenceMatch]
    ) -> int:
        """
        Calculate the effective frequency considering reference data.

        Logic:
        - If no reference: return current_frequency
        - If reference exists: return max(current, reference.frequency)

        This ensures that if a text was frequent enough to standardize
        in the yearly analysis, it's still recommended in monthly analyses.

        Args:
            current_frequency: Frequency in current analysis
            reference_match: Reference match result

        Returns:
            Combined frequency (max of current and reference)
        """
        if reference_match is None:
            return current_frequency

        ref_freq = reference_match.reference_clause.frequency
        return max(current_frequency, ref_freq)

    def should_standardize_from_reference(
        self,
        reference_match: Optional[ReferenceMatch],
        threshold: int
    ) -> bool:
        """
        Check if reference frequency meets standardization threshold.

        Used to override current frequency check in Step 3.

        Args:
            reference_match: Reference match result
            threshold: Standardization threshold (e.g., 20)

        Returns:
            True if reference frequency >= threshold
        """
        if reference_match is None:
            return False

        return reference_match.reference_clause.frequency >= threshold

    def get_comparison_status(
        self,
        current_advice: str,
        reference_match: Optional[ReferenceMatch]
    ) -> ComparisonStatus:
        """
        Determine comparison status between current and reference.

        Args:
            current_advice: Current analysis advice code
            reference_match: Reference match result

        Returns:
            ComparisonStatus enum value
        """
        return get_comparison_status(current_advice, reference_match)

    def get_gone_texts(self) -> List[ReferenceClause]:
        """
        Get all reference clauses that were not matched to current data.

        These are "verdwenen teksten" - texts that existed in reference
        but not in current analysis (possibly due to policy mutations,
        cancellations, or text changes).

        Returns:
            List of unmatched reference clauses
        """
        if not self.is_loaded:
            return []

        return self._reference_data.get_unmatched()

    def get_statistics(self) -> Dict[str, any]:
        """
        Get statistics about reference matching.

        Returns:
            Dictionary with stats
        """
        if not self.is_loaded:
            return {"loaded": False}

        stats = self._reference_data.get_match_stats()
        stats["loaded"] = True
        stats["source_file"] = self._reference_data.source_filename
        stats["cache_size"] = len(self._match_cache)

        return stats

    def _find_column(self, df: pd.DataFrame, column_type: str) -> Optional[str]:
        """
        Find a column in the DataFrame by checking multiple possible names.

        Args:
            df: DataFrame to search
            column_type: Type of column ('text', 'frequency', etc.)

        Returns:
            Column name if found, None otherwise
        """
        possible_names = self.COLUMN_MAPPINGS.get(column_type, [])

        for name in possible_names:
            if name in df.columns:
                return name

        return None

    def _simplify_text(self, text: str) -> str:
        """
        Simplify text for matching.

        Normalizes text by lowercasing and stripping whitespace.
        For more aggressive normalization, could use text_normalization utils.

        Args:
            text: Text to simplify

        Returns:
            Simplified text
        """
        if not text:
            return ""

        # Basic normalization
        simplified = text.lower().strip()

        # Remove common variations
        simplified = " ".join(simplified.split())  # Normalize whitespace

        return simplified
