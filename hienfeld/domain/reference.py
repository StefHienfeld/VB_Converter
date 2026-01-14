# hienfeld/domain/reference.py
"""
Domain models for reference analysis comparison.

Used to compare current analysis against a previous (yearly) analysis
to maintain consistency and catch frequency-based recommendations.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List


class ComparisonStatus(Enum):
    """Status indicators for reference comparison."""
    CONSISTENT = "consistent"    # Same advice as reference
    DIFFERENT = "different"      # Different advice than reference
    NEW = "new"                  # Not found in reference (new text)
    GONE = "gone"                # In reference but not in current


# Display symbols for Excel output
COMPARISON_SYMBOLS = {
    ComparisonStatus.CONSISTENT: "✓",
    ComparisonStatus.DIFFERENT: "⚠️",
    ComparisonStatus.NEW: "🆕",
    ComparisonStatus.GONE: "🗑️",
}


@dataclass
class ReferenceClause:
    """
    Represents a clause from a previous reference analysis.

    Parsed from a VB Converter Excel output file.

    Attributes:
        text: Original text from reference
        simplified_text: Normalized text for matching
        frequency: Frequency count from reference analysis
        advice_code: Advice recommendation from reference
        cluster_name: Cluster name from reference
        confidence: Confidence level from reference
        reason: Reason/explanation from reference
        reference_article: Article reference from reference
        policy_number: Policy number for per-policy matching
        is_matched: Whether this clause was matched to current data
    """
    text: str
    simplified_text: str
    frequency: int
    advice_code: str
    cluster_name: str = ""
    confidence: str = ""
    reason: str = ""
    reference_article: str = ""
    policy_number: str = ""
    is_matched: bool = False

    def mark_matched(self) -> None:
        """Mark this reference clause as matched."""
        self.is_matched = True


@dataclass
class ReferenceMatch:
    """
    Result of matching a current clause to a reference.

    Attributes:
        reference_clause: The matched reference clause
        match_type: How the match was found ('exact', 'fuzzy', 'semantic')
        match_score: Similarity score (0.0 - 1.0)
    """
    reference_clause: ReferenceClause
    match_type: str  # 'exact', 'fuzzy', 'semantic'
    match_score: float

    @property
    def is_exact(self) -> bool:
        """Check if this is an exact match."""
        return self.match_type == "exact"

    @property
    def is_high_confidence(self) -> bool:
        """Check if match score is high enough for confidence."""
        return self.match_score >= 0.95


@dataclass
class ReferenceData:
    """
    Container for all reference analysis data.

    Holds parsed reference clauses and provides lookup methods.

    Attributes:
        clauses: List of all reference clauses
        source_filename: Name of the source Excel file
        total_rows: Total number of rows in reference
    """
    clauses: List[ReferenceClause] = field(default_factory=list)
    source_filename: str = ""
    total_rows: int = 0

    # Lookup caches (built after loading)
    _text_lookup: Dict[str, ReferenceClause] = field(default_factory=dict, repr=False)
    _text_policy_lookup: Dict[str, ReferenceClause] = field(default_factory=dict, repr=False)
    _cluster_lookup: Dict[str, List[ReferenceClause]] = field(default_factory=dict, repr=False)

    def build_indexes(self) -> None:
        """Build lookup indexes for fast matching."""
        self._text_lookup = {}
        self._text_policy_lookup = {}
        self._cluster_lookup = {}

        for clause in self.clauses:
            # Index by simplified text (for exact matching)
            if clause.simplified_text:
                self._text_lookup[clause.simplified_text] = clause

            # Index by text + policy_number (for per-policy matching)
            if clause.simplified_text and clause.policy_number:
                key = f"{clause.simplified_text}|{clause.policy_number}"
                self._text_policy_lookup[key] = clause

            # Index by cluster name (for grouping)
            if clause.cluster_name:
                if clause.cluster_name not in self._cluster_lookup:
                    self._cluster_lookup[clause.cluster_name] = []
                self._cluster_lookup[clause.cluster_name].append(clause)

    def get_by_text(self, simplified_text: str) -> Optional[ReferenceClause]:
        """Get reference clause by exact simplified text match."""
        return self._text_lookup.get(simplified_text)

    def get_by_text_and_policy(
        self, simplified_text: str, policy_number: str
    ) -> Optional[ReferenceClause]:
        """Get reference clause by exact text + policy number match."""
        key = f"{simplified_text}|{policy_number}"
        return self._text_policy_lookup.get(key)

    def get_by_cluster(self, cluster_name: str) -> List[ReferenceClause]:
        """Get all reference clauses for a cluster name."""
        return self._cluster_lookup.get(cluster_name, [])

    def get_unmatched(self) -> List[ReferenceClause]:
        """Get all reference clauses that were not matched (gone texts)."""
        return [c for c in self.clauses if not c.is_matched]

    def get_match_stats(self) -> Dict[str, int]:
        """Get statistics about matching."""
        matched = sum(1 for c in self.clauses if c.is_matched)
        return {
            "total": len(self.clauses),
            "matched": matched,
            "unmatched": len(self.clauses) - matched,
        }


def get_comparison_status(
    current_advice: str,
    reference_match: Optional[ReferenceMatch]
) -> ComparisonStatus:
    """
    Determine comparison status between current and reference analysis.

    Args:
        current_advice: Current analysis advice code
        reference_match: Reference match result (or None if not found)

    Returns:
        ComparisonStatus indicating the relationship
    """
    if reference_match is None:
        return ComparisonStatus.NEW

    ref_advice = reference_match.reference_clause.advice_code

    # Normalize advice codes for comparison (ignore emojis, case)
    def normalize_advice(advice: str) -> str:
        # Remove common emojis and normalize
        cleaned = advice.replace("🛠️", "").replace("⚠️", "").replace("✅", "")
        cleaned = cleaned.replace("📋", "").strip().upper()
        return cleaned

    current_normalized = normalize_advice(current_advice)
    ref_normalized = normalize_advice(ref_advice)

    # Check if they match (allowing for some variation)
    if current_normalized == ref_normalized:
        return ComparisonStatus.CONSISTENT

    # Check for equivalent meanings
    equivalents = {
        ("VERWIJDEREN", "VERWIJDEREN (VERLOPEN)"),
        ("HANDMATIG CHECKEN", "HANDMATIG"),
        ("STANDAARDISEREN", "STANDAARD"),
    }

    for eq_set in equivalents:
        if current_normalized in eq_set and ref_normalized in eq_set:
            return ComparisonStatus.CONSISTENT

    return ComparisonStatus.DIFFERENT


def get_comparison_symbol(status: ComparisonStatus) -> str:
    """Get display symbol for comparison status."""
    return COMPARISON_SYMBOLS.get(status, "?")
