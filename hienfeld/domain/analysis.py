# hienfeld/domain/analysis.py
"""
Domain model for analysis advice results.
"""
from dataclasses import dataclass
from typing import Optional
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


class ConfidenceLevel(Enum):
    """Confidence levels for analysis results."""
    LAAG = "Laag"
    MIDDEN = "Midden"
    HOOG = "Hoog"


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
        return self.advice_code not in [
            AdviceCode.HANDMATIG_CHECKEN.value,
            "HANDMATIG CHECKEN"
        ]
    
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

