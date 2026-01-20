# hienfeld/services/analysis/formatters/reference_formatter.py
"""
Formatter for policy section references.

Handles presentation logic for formatting article references,
keeping this concern out of the business logic.
"""

from typing import Optional


class ReferenceFormatter:
    """
    Formats policy section references for display.

    Extracts article numbers and titles from PolicyDocumentSection
    objects and formats them consistently for output.

    Example outputs:
    - "Art 2.8"
    - "Art 2.8 - Uitsluitingen brand"
    - "Art 2.8 - Uitsluitingen brand en aansprakeli..." (truncated)
    """

    def __init__(self, max_title_length: int = 80) -> None:
        """
        Initialize formatter.

        Args:
            max_title_length: Maximum length for article title before truncation
        """
        self._max_title_length = max_title_length

    def format_reference(self, section: Optional["PolicyDocumentSection"]) -> str:
        """
        Format a policy section as a reference string.

        Args:
            section: PolicyDocumentSection or None

        Returns:
            Formatted reference string (e.g., "Art 2.8 - Title")
        """
        if section is None:
            return "-"

        article_ref = self._get_article_reference(section)
        title = self._get_truncated_title(section)

        if title:
            return f"{article_ref} - {title}"
        return article_ref

    def format_short_reference(self, section: Optional["PolicyDocumentSection"]) -> str:
        """
        Format a short reference (article number only).

        Args:
            section: PolicyDocumentSection or None

        Returns:
            Article reference only (e.g., "Art 2.8")
        """
        if section is None:
            return "-"

        return self._get_article_reference(section)

    def _get_article_reference(self, section: "PolicyDocumentSection") -> str:
        """
        Extract article reference from section.

        Args:
            section: PolicyDocumentSection

        Returns:
            Article reference (e.g., "Art 2.8")
        """
        # Try article_number first
        if hasattr(section, "article_number") and section.article_number:
            return f"Art {section.article_number}"

        # Try section_id
        if hasattr(section, "section_id") and section.section_id:
            return f"Art {section.section_id}"

        # Try extracting from id
        if hasattr(section, "id") and section.id:
            section_id = section.id
            # Extract article number from id like "SEC-001-2.8"
            if "-" in section_id:
                parts = section_id.split("-")
                if len(parts) >= 3:
                    return f"Art {parts[-1]}"

        return "Art ?"

    def _get_truncated_title(self, section: "PolicyDocumentSection") -> Optional[str]:
        """
        Get truncated article title.

        Args:
            section: PolicyDocumentSection

        Returns:
            Title (truncated if needed) or None
        """
        title = getattr(section, "article_title", None)

        if not title:
            return None

        title = title.strip()

        if len(title) <= self._max_title_length:
            return title

        # Truncate with ellipsis
        truncated = title[:self._max_title_length - 3].rstrip()
        return f"{truncated}..."

    def format_multiple_references(
        self,
        sections: list,
        separator: str = ", "
    ) -> str:
        """
        Format multiple sections as a combined reference.

        Args:
            sections: List of PolicyDocumentSection objects
            separator: Separator between references

        Returns:
            Combined reference string
        """
        if not sections:
            return "-"

        # Get unique short references
        refs = []
        seen = set()

        for section in sections:
            ref = self.format_short_reference(section)
            if ref not in seen and ref != "-":
                refs.append(ref)
                seen.add(ref)

        if not refs:
            return "-"

        return separator.join(refs)


# Type hint import for documentation
if False:  # TYPE_CHECKING
    from hienfeld.domain.policy_document import PolicyDocumentSection
