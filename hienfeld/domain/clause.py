# hienfeld/domain/clause.py
"""
Domain model for a single clause (vrije tekst) from a policy CSV.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Clause:
    """
    Represents a single free-text clause from the policy data.
    
    Attributes:
        id: Unique identifier (e.g., row index or policy_number+rule)
        raw_text: Original text as imported from source
        simplified_text: Normalized text for comparison
        source_policy_number: Optional policy number reference
        source_file_name: Name of the source file
        cluster_id: Assigned cluster ID after clustering
        is_multi_clause: Flag indicating if text contains multiple clauses
    """
    id: str
    raw_text: str
    simplified_text: str
    source_policy_number: Optional[str] = None
    source_file_name: Optional[str] = None
    cluster_id: Optional[str] = None
    is_multi_clause: bool = False
    
    def __post_init__(self):
        """Validate clause data after initialization."""
        if not self.id:
            raise ValueError("Clause id cannot be empty")
    
    @property
    def text_length(self) -> int:
        """Return length of raw text."""
        return len(self.raw_text) if self.raw_text else 0
    
    @property
    def is_empty(self) -> bool:
        """Check if clause has meaningful content."""
        return not self.simplified_text or len(self.simplified_text.strip()) < 5

