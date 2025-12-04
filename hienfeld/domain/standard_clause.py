# hienfeld/domain/standard_clause.py
"""
Domain model for standard clauses from the clause library.

Standard clauses are pre-approved clause texts that can be referenced by code.
When a free text closely matches a standard clause, we recommend replacing it.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StandardClause:
    """
    Represents a standard clause from the clause library.
    
    Attributes:
        code: Unique clause code (e.g., "9NX3", "VB12")
        text: The official/approved clause text
        simplified_text: Normalized text for matching
        category: Classification category (e.g., "Terrorisme", "Brand")
        description: Optional description of what this clause does
    """
    code: str
    text: str
    simplified_text: str
    category: str
    description: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        """Get display name combining code and category."""
        return f"{self.code} ({self.category})"
    
    @property
    def is_valid(self) -> bool:
        """Check if this is a valid clause with required fields."""
        return bool(self.code and self.text and len(self.text.strip()) > 10)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for export/serialization."""
        return {
            'Code': self.code,
            'Tekst': self.text,
            'Categorie': self.category,
            'Beschrijving': self.description or ''
        }


@dataclass
class ClauseLibraryMatch:
    """
    Represents a match result when comparing against the clause library.
    
    Attributes:
        clause: The matched StandardClause
        similarity_score: How similar the input is to this clause (0.0 - 1.0)
        match_type: Type of match ('EXACT', 'HIGH', 'MEDIUM', 'LOW')
    """
    clause: StandardClause
    similarity_score: float
    match_type: str
    
    @property
    def is_replacement_candidate(self) -> bool:
        """Check if this match is strong enough to recommend replacement."""
        return self.similarity_score >= 0.95
    
    @property
    def is_review_candidate(self) -> bool:
        """Check if this match warrants manual review."""
        return 0.85 <= self.similarity_score < 0.95
    
    @classmethod
    def from_score(cls, clause: StandardClause, score: float) -> 'ClauseLibraryMatch':
        """Create a match result with automatic type classification."""
        if score >= 0.95:
            match_type = 'EXACT'
        elif score >= 0.85:
            match_type = 'HIGH'
        elif score >= 0.75:
            match_type = 'MEDIUM'
        else:
            match_type = 'LOW'
        
        return cls(clause=clause, similarity_score=score, match_type=match_type)

