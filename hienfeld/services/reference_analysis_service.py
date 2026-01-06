# hienfeld/services/reference_analysis_service.py
"""
Service for loading, parsing, and comparing reference analysis data.

Enables comparison between current (monthly) analysis and a previous
(yearly) reference analysis to maintain frequency-based recommendations.
"""
from typing import Optional, List, Dict, Tuple
from io import BytesIO
import pandas as pd

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
        'advice': ['Advies', 'advies', 'Advice', 'advice'],
        'cluster_name': ['Cluster_Naam', 'cluster_naam', 'Cluster Naam', 'ClusterNaam', 'Cluster_ID'],
        'confidence': ['Vertrouwen', 'vertrouwen', 'Confidence', 'confidence'],
        'reason': ['Reden', 'reden', 'Reason', 'reason'],
        'article': ['Artikel', 'artikel', 'Article', 'article'],
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

            # Parse rows into ReferenceClause objects
            clauses = []
            seen_texts = set()  # Track unique texts to avoid duplicates

            for idx, row in df.iterrows():
                text = str(row.get(text_col, "")).strip()

                # Skip empty rows
                if not text or text == "nan":
                    continue

                # Skip duplicates (use simplified text for deduplication)
                simplified = self._simplify_text(text)
                if simplified in seen_texts:
                    continue
                seen_texts.add(simplified)

                # Parse frequency (default to 1 if missing)
                frequency = 1
                if freq_col and pd.notna(row.get(freq_col)):
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
                )
                clauses.append(clause)

            # Create reference data
            self._reference_data = ReferenceData(
                clauses=clauses,
                source_filename=filename,
                total_rows=len(df),
            )
            self._reference_data.build_indexes()

            # Clear match cache
            self._match_cache = {}

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
        min_score: float = 0.90
    ) -> Optional[ReferenceMatch]:
        """
        Find the best matching reference clause for a given text.

        Matching strategy (in order of speed):
        1. Exact match on simplified_text (O(1) hash lookup)
        2. Fuzzy match via RapidFuzz (threshold: min_score)
        3. Semantic match via hybrid service (if available, for borderline cases)

        Args:
            text: Text to match
            min_score: Minimum similarity score (default: 0.90)

        Returns:
            ReferenceMatch if found, None otherwise
        """
        if not self.is_loaded:
            return None

        # Check cache first
        simplified = self._simplify_text(text)
        if simplified in self._match_cache:
            return self._match_cache[simplified]

        # TIER 1: Exact match (O(1))
        exact_match = self._reference_data.get_by_text(simplified)
        if exact_match:
            exact_match.mark_matched()
            result = ReferenceMatch(
                reference_clause=exact_match,
                match_type="exact",
                match_score=1.0,
            )
            self._match_cache[simplified] = result
            return result

        # TIER 2: Fuzzy match (O(n))
        best_match: Optional[Tuple[float, ReferenceClause]] = None

        for ref_clause in self._reference_data.clauses:
            if ref_clause.is_matched:
                continue  # Skip already matched

            score = self.similarity_service.compute_similarity(
                simplified, ref_clause.simplified_text
            )

            if score >= min_score:
                if best_match is None or score > best_match[0]:
                    best_match = (score, ref_clause)

        if best_match and best_match[0] >= min_score:
            best_match[1].mark_matched()
            result = ReferenceMatch(
                reference_clause=best_match[1],
                match_type="fuzzy",
                match_score=best_match[0],
            )
            self._match_cache[simplified] = result
            return result

        # TIER 3: Semantic match (expensive, only for borderline)
        if self.hybrid_similarity_service and best_match and best_match[0] >= 0.75:
            # Try semantic matching for borderline cases
            semantic_score = self.hybrid_similarity_service.compute_similarity(
                simplified, best_match[1].simplified_text
            )

            if semantic_score >= 0.85:
                best_match[1].mark_matched()
                result = ReferenceMatch(
                    reference_clause=best_match[1],
                    match_type="semantic",
                    match_score=semantic_score,
                )
                self._match_cache[simplified] = result
                return result

        # No match found
        self._match_cache[simplified] = None
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
