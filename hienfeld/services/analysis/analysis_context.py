# hienfeld/services/analysis/analysis_context.py
"""
Context builder for analysis strategies.

The AnalysisContextBuilder creates an AnalysisContext from existing services,
providing a clean way to set up the context for the analysis pipeline.
"""

from typing import Any, Dict, List, Optional

from hienfeld.config import AppConfig
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.services.interfaces import AnalysisContext


class AnalysisContextBuilder:
    """
    Builder for creating AnalysisContext instances.

    Provides a fluent interface for building the analysis context
    from various services and data sources.

    Example:
        context = (
            AnalysisContextBuilder(config)
            .with_policy_sections(sections)
            .with_similarity_service(similarity)
            .with_hybrid_service(hybrid)
            .build()
        )
    """

    def __init__(self, config: AppConfig) -> None:
        """
        Initialize the builder with configuration.

        Args:
            config: Application configuration
        """
        self._config = config
        self._policy_sections: List[PolicyDocumentSection] = []
        self._similarity_service: Optional[Any] = None
        self._hybrid_service: Optional[Any] = None
        self._semantic_service: Optional[Any] = None
        self._clause_library_service: Optional[Any] = None
        self._admin_check_service: Optional[Any] = None
        self._custom_instructions_service: Optional[Any] = None
        self._reference_service: Optional[Any] = None
        self._ai_analyzer: Optional[Any] = None
        self._semantic_index_ready: bool = False

    def with_policy_sections(
        self,
        sections: List[PolicyDocumentSection]
    ) -> "AnalysisContextBuilder":
        """
        Set policy sections for conditions matching.

        Args:
            sections: Parsed policy document sections

        Returns:
            Self for chaining
        """
        self._policy_sections = sections or []
        return self

    def with_similarity_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the base similarity service (RapidFuzz)."""
        self._similarity_service = service
        return self

    def with_hybrid_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the hybrid similarity service."""
        self._hybrid_service = service
        return self

    def with_semantic_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the semantic similarity service."""
        self._semantic_service = service
        return self

    def with_clause_library_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the clause library service."""
        self._clause_library_service = service
        return self

    def with_admin_check_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the admin check service."""
        self._admin_check_service = service
        return self

    def with_custom_instructions_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the custom instructions service."""
        self._custom_instructions_service = service
        return self

    def with_reference_service(self, service: Any) -> "AnalysisContextBuilder":
        """Set the reference analysis service."""
        self._reference_service = service
        return self

    def with_ai_analyzer(self, analyzer: Any) -> "AnalysisContextBuilder":
        """Set the AI/LLM analyzer."""
        self._ai_analyzer = analyzer
        return self

    def with_semantic_index_ready(self, ready: bool) -> "AnalysisContextBuilder":
        """Set whether semantic index is ready."""
        self._semantic_index_ready = ready
        return self

    def build(self) -> AnalysisContext:
        """
        Build the AnalysisContext.

        Creates the context with all configured services and data.
        Builds the policy full text and section lookup automatically.

        Returns:
            Configured AnalysisContext
        """
        # Build policy full text for substring matching
        policy_full_text = ""
        if self._policy_sections:
            policy_full_text = " ".join(
                s.simplified_text for s in self._policy_sections if s.simplified_text
            )

        # Build section lookup
        section_lookup: Dict[str, PolicyDocumentSection] = {}
        for section in self._policy_sections:
            if section and section.id:
                section_lookup[section.id] = section

        return AnalysisContext(
            config=self._config,
            policy_sections=self._policy_sections,
            policy_full_text=policy_full_text,
            section_lookup=section_lookup,
            similarity_service=self._similarity_service,
            hybrid_service=self._hybrid_service,
            semantic_service=self._semantic_service,
            clause_library_service=self._clause_library_service,
            admin_check_service=self._admin_check_service,
            custom_instructions_service=self._custom_instructions_service,
            reference_service=self._reference_service,
            ai_analyzer=self._ai_analyzer,
            semantic_index_ready=self._semantic_index_ready,
        )

    @classmethod
    def from_analysis_service(cls, service: Any) -> "AnalysisContextBuilder":
        """
        Create a builder from an existing AnalysisService.

        Extracts all the services and state from the AnalysisService
        to create a compatible context.

        Args:
            service: Existing AnalysisService instance

        Returns:
            Configured builder
        """
        builder = cls(service.config)

        builder._policy_sections = getattr(service, "_policy_sections", [])
        builder._similarity_service = getattr(service, "similarity_service", None)
        builder._hybrid_service = getattr(service, "hybrid_similarity_service", None)
        builder._semantic_service = getattr(service, "semantic_similarity_service", None)
        builder._clause_library_service = getattr(service, "clause_library_service", None)
        builder._admin_check_service = getattr(service, "admin_check_service", None)
        builder._custom_instructions_service = getattr(service, "custom_instructions_service", None)
        builder._reference_service = getattr(service, "reference_service", None)
        builder._ai_analyzer = getattr(service, "ai_analyzer", None)
        builder._semantic_index_ready = getattr(service, "_semantic_index_ready", False)

        return builder
