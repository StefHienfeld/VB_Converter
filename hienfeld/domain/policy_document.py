# hienfeld/domain/policy_document.py
"""
Domain model for policy document sections (articles/paragraphs).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PolicyDocumentSection:
    """
    Represents an article or paragraph from the policy conditions document.
    
    Attributes:
        id: Section identifier (e.g., "Art 2.14")
        title: Section title/heading
        raw_text: Original text content
        simplified_text: Normalized text for matching
        page_number: Optional page number in source document
        document_id: Source document identifier (e.g., filename)
    """
    id: str
    title: str
    raw_text: str
    simplified_text: str
    page_number: Optional[int] = None
    document_id: Optional[str] = None
    
    @property
    def full_reference(self) -> str:
        """Get full reference string including document info."""
        ref = self.id
        if self.title:
            ref = f"{ref} - {self.title}"
        if self.page_number:
            ref = f"{ref} (p.{self.page_number})"
        return ref
    
    @property
    def is_empty(self) -> bool:
        """Check if section has meaningful content."""
        return not self.simplified_text or len(self.simplified_text.strip()) < 10

