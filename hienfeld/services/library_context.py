"""
In-memory representation of a loaded product library.

Contains all pre-computed data needed for RAG-based analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.domain.standard_clause import StandardClause


@dataclass
class LibraryContext:
    """
    In-memory representation of a loaded product library.

    Contains all pre-computed data needed for a library-based analysis.
    Built by LibraryService.load_library_for_analysis() and cached
    in ServiceCache for repeated use.

    Attributes:
        library_id: UUID of the ProductLibrary record.
        library_naam: Human-readable library name for logging/display.
        policy_sections: Parsed PolicyDocumentSection domain objects with raw text.
        faiss_store: Optional FaissVectorStore built from stored embeddings.
        tfidf_vectorizer: Optional deserialized sklearn TfidfVectorizer.
        tfidf_matrix: Optional deserialized scipy sparse matrix.
        standard_clauses: List of StandardClause objects from the clause library.
        synonym_overrides: Product-specific synonym mappings (term -> synonyms).
        loaded_at: Timestamp when this context was built.
        section_count: Number of policy sections (mirrors DB record).
        clause_count: Number of standard clauses (mirrors DB record).
    """

    library_id: str
    library_naam: str

    # Policy sections with their text data
    policy_sections: List[PolicyDocumentSection] = field(default_factory=list)

    # FAISS vector store for similarity search (built from stored embeddings)
    faiss_store: Optional[Any] = None  # FaissVectorStore

    # TF-IDF data (deserialized from stored index)
    tfidf_vectorizer: Optional[Any] = None  # sklearn TfidfVectorizer
    tfidf_matrix: Optional[Any] = None  # scipy sparse matrix

    # Standard clauses from clause library
    standard_clauses: List[StandardClause] = field(default_factory=list)

    # Custom synonym overrides for this library
    synonym_overrides: Dict[str, List[str]] = field(default_factory=dict)

    # Metadata
    loaded_at: datetime = field(default_factory=lambda: datetime.now())
    section_count: int = 0
    clause_count: int = 0

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """Return True when at least one policy section has been loaded."""
        return len(self.policy_sections) > 0

    @property
    def has_faiss(self) -> bool:
        """Return True when a FAISS vector index is available for this library."""
        return self.faiss_store is not None

    @property
    def has_tfidf(self) -> bool:
        """Return True when both the TF-IDF vectorizer and matrix are present."""
        return self.tfidf_vectorizer is not None and self.tfidf_matrix is not None

    @property
    def has_clauses(self) -> bool:
        """Return True when standard clauses are loaded."""
        return len(self.standard_clauses) > 0

    def __repr__(self) -> str:
        return (
            f"LibraryContext(id={self.library_id!r}, naam={self.library_naam!r}, "
            f"sections={len(self.policy_sections)}, clauses={len(self.standard_clauses)}, "
            f"faiss={self.has_faiss}, tfidf={self.has_tfidf})"
        )
