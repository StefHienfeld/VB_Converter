# hienfeld/domain/clause.py
"""
Domain model for a single clause (vrije tekst) from a policy CSV.

Enhanced with multi-level text normalization for different use cases:
- raw_text: Original text (for LLM context)
- simplified_text: Light normalized (for display)
- embedding_text: Embedding normalized (for vector search)
- clusterable_text: Clustering normalized (for grouping)
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Clause:
    """
    Represents a single free-text clause from the policy data.

    Multi-level text normalization for different use cases:
    - raw_text: Original text preserved for LLM context
    - simplified_text: Light normalization for display (whitespace, encoding)
    - embedding_text: For vector embeddings (preserves legal refs, removes noise)
    - clusterable_text: Aggressive normalization for duplicate detection

    Attributes:
        id: Unique identifier (e.g., row index or policy_number+rule)
        raw_text: Original text as imported from source (for LLM)
        simplified_text: Light normalized text for display
        embedding_text: Embedding-optimized text for vector search
        clusterable_text: Aggressively normalized text for clustering
        source_policy_number: Optional policy number reference
        source_file_name: Name of the source file
        cluster_id: Assigned cluster ID after clustering
        is_multi_clause: Flag indicating if text contains multiple clauses
    """
    id: str
    raw_text: str
    simplified_text: str
    embedding_text: Optional[str] = None
    clusterable_text: Optional[str] = None
    source_policy_number: Optional[str] = None
    source_file_name: Optional[str] = None
    cluster_id: Optional[str] = None
    is_multi_clause: bool = False
    
    def __post_init__(self):
        """Validate clause data and auto-generate missing text representations."""
        if not self.id:
            raise ValueError("Clause id cannot be empty")

        # Auto-generate missing text representations using lazy import
        if self.raw_text and (self.embedding_text is None or self.clusterable_text is None):
            from ..utils.text_normalization import normalize_text, NormalizationLevel

            if self.embedding_text is None:
                self.embedding_text = normalize_text(self.raw_text, NormalizationLevel.EMBEDDING)

            if self.clusterable_text is None:
                self.clusterable_text = normalize_text(self.raw_text, NormalizationLevel.CLUSTERING)

    @classmethod
    def from_raw(
        cls,
        id: str,
        raw_text: str,
        source_policy_number: Optional[str] = None,
        source_file_name: Optional[str] = None,
        **kwargs
    ) -> 'Clause':
        """
        Create a Clause with all normalization levels auto-generated.

        This is the recommended way to create Clause objects as it ensures
        all text representations are properly generated.

        Args:
            id: Unique identifier for the clause
            raw_text: Original text from source
            source_policy_number: Optional policy number reference
            source_file_name: Name of the source file
            **kwargs: Additional optional fields

        Returns:
            Clause with all text representations populated
        """
        from ..utils.text_normalization import normalize_text, NormalizationLevel

        return cls(
            id=id,
            raw_text=raw_text,
            simplified_text=normalize_text(raw_text, NormalizationLevel.LIGHT),
            embedding_text=normalize_text(raw_text, NormalizationLevel.EMBEDDING),
            clusterable_text=normalize_text(raw_text, NormalizationLevel.CLUSTERING),
            source_policy_number=source_policy_number,
            source_file_name=source_file_name,
            **kwargs
        )

    @property
    def text_length(self) -> int:
        """Return length of raw text."""
        return len(self.raw_text) if self.raw_text else 0

    @property
    def is_empty(self) -> bool:
        """Check if clause has meaningful content."""
        return not self.simplified_text or len(self.simplified_text.strip()) < 5

    @property
    def text_for_embedding(self) -> str:
        """Get the best text for embedding generation."""
        return self.embedding_text or self.simplified_text or self.raw_text

    @property
    def text_for_clustering(self) -> str:
        """Get the best text for clustering comparison."""
        return self.clusterable_text or self.simplified_text or self.raw_text

