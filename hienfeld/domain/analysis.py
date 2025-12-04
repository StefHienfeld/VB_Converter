# hienfeld/domain/analysis.py
"""
Domain model for analysis advice results.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class AdviceCode(Enum):
    """Enumeration of possible advice codes."""
    # With conditions mode
    VERWIJDEREN = "VERWIJDEREN"
    SPLITSEN = "⚠️ SPLITSEN"
    SPLITSEN_CONTROLEREN = "⚠️ SPLITSEN/CONTROLEREN"
    STANDAARDISEREN = "🛠️ STANDAARDISEREN"
    BEHOUDEN_CLAUSULE = "BEHOUDEN (CLAUSULE)"
    HANDMATIG_CHECKEN = "HANDMATIG CHECKEN"
    
    # Internal analysis mode (without conditions)
    FREQUENTIE_INFO = "📊 FREQUENTIE INFO"
    CONSISTENTIE_CHECK = "🔄 CONSISTENTIE CHECK"
    UNIEK = "✨ UNIEK"
    
    # Administrative / Hygiene codes (Step 0)
    OPSCHONEN = "🧹 OPSCHONEN"              # Text needs cleaning (encoding, corrupt)
    AANVULLEN = "📝 AANVULLEN"              # Text is incomplete (placeholders, missing info)
    VERWIJDEREN_VERLOPEN = "📅 VERWIJDEREN (VERLOPEN)"  # Text refers to past date, no longer relevant
    LEEG = "⚪ LEEG"                         # Empty text
    ONLEESBAAR = "❌ ONLEESBAAR"            # Text is unreadable/corrupt


class ConfidenceLevel(Enum):
    """Confidence levels for analysis results."""
    LAAG = "Laag"
    MIDDEN = "Midden"
    HOOG = "Hoog"


class AdminIssueType(Enum):
    """Types of administrative/hygiene issues detected in Step 0."""
    LEEG = "LEEG"                   # Empty or whitespace-only text
    TE_KORT = "TE_KORT"             # Text too short to analyze
    VEROUDERD = "VEROUDERD"         # Contains date in the past
    PLACEHOLDER = "PLACEHOLDER"     # Contains placeholders like [INVULLEN], XXX
    ENCODING = "ENCODING"           # Encoding problems (corrupted characters)
    INCOMPLEET = "INCOMPLEET"       # Incomplete sentence or missing info
    TEGENSTRIJDIG = "TEGENSTRIJDIG" # Internally contradictory
    ONLEESBAAR = "ONLEESBAAR"       # Unreadable or corrupt text
    OK = "OK"                        # No issues found


@dataclass
class AnalysisAdvice:
    """
    Represents the analysis result and recommendation for a cluster.
    
    Attributes:
        cluster_id: ID of the analyzed cluster
        advice_code: Recommendation code (VERWIJDEREN, SPLITSEN, etc.)
        reason: Explanation for the recommendation
        confidence: Confidence level of the analysis
        reference_article: Reference to policy article (e.g., "Art 2.8")
        category: Optional category classification (e.g., "FRAUDE", "MOLEST")
        cluster_name: Human-readable cluster name
        frequency: How often this pattern occurs
    """
    cluster_id: str
    advice_code: str
    reason: str
    confidence: str
    reference_article: Optional[str] = None
    category: Optional[str] = None
    cluster_name: str = ""
    frequency: int = 0
    
    @property
    def is_actionable(self) -> bool:
        """Check if this advice requires user action."""
        non_actionable = [
            AdviceCode.HANDMATIG_CHECKEN.value,
            "HANDMATIG CHECKEN"
        ]
        return self.advice_code not in non_actionable
    
    @property
    def is_administrative_issue(self) -> bool:
        """Check if this is an administrative/hygiene issue (Step 0)."""
        admin_codes = [
            AdviceCode.OPSCHONEN.value,
            AdviceCode.AANVULLEN.value,
            AdviceCode.VERWIJDEREN_VERLOPEN.value,
            AdviceCode.LEEG.value,
            AdviceCode.ONLEESBAAR.value
        ]
        return self.advice_code in admin_codes
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence recommendation."""
        return self.confidence in [ConfidenceLevel.HOOG.value, "Hoog"]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame export."""
        return {
            'Cluster_ID': self.cluster_id,
            'Cluster_Naam': self.cluster_name,
            'Frequentie': self.frequency,
            'Advies': self.advice_code,
            'Reden': self.reason,
            'Vertrouwen': self.confidence,
            'Artikel': self.reference_article or '-'
        }


@dataclass
class AdminIssue:
    """
    Represents a single administrative/hygiene issue found in a text.
    
    Attributes:
        issue_type: Type of issue (LEEG, VEROUDERD, PLACEHOLDER, etc.)
        description: Human-readable description of the issue
        details: Additional details (e.g., the problematic date found)
    """
    issue_type: AdminIssueType
    description: str
    details: Optional[str] = None


@dataclass
class AdminCheckResult:
    """
    Result of the administrative/hygiene check (Step 0).
    
    Attributes:
        has_issues: True if any issues were found
        issues: List of issues found
        recommendation: Recommended action (OPSCHONEN, AANVULLEN, etc.)
        summary: Optional 1-sentence summary of the text (from AI)
        passed_simple_checks: True if text passed all simple (non-AI) checks
    """
    has_issues: bool
    issues: List[AdminIssue] = field(default_factory=list)
    recommendation: Optional[AdviceCode] = None
    summary: Optional[str] = None
    passed_simple_checks: bool = True
    
    @classmethod
    def ok(cls) -> 'AdminCheckResult':
        """Create an OK result (no issues found)."""
        return cls(has_issues=False, issues=[], recommendation=None)
    
    @classmethod
    def with_issue(
        cls, 
        issue_type: AdminIssueType, 
        description: str,
        recommendation: AdviceCode,
        details: Optional[str] = None
    ) -> 'AdminCheckResult':
        """Create a result with a single issue."""
        issue = AdminIssue(
            issue_type=issue_type,
            description=description,
            details=details
        )
        return cls(
            has_issues=True,
            issues=[issue],
            recommendation=recommendation,
            passed_simple_checks=False
        )
    
    def add_issue(
        self, 
        issue_type: AdminIssueType, 
        description: str,
        details: Optional[str] = None
    ) -> None:
        """Add an issue to the result."""
        self.issues.append(AdminIssue(
            issue_type=issue_type,
            description=description,
            details=details
        ))
        self.has_issues = True
    
    @property
    def issue_types(self) -> List[str]:
        """Get list of issue type names."""
        return [issue.issue_type.value for issue in self.issues]
    
    @property
    def primary_issue(self) -> Optional[AdminIssue]:
        """Get the most important issue (first in list)."""
        return self.issues[0] if self.issues else None

