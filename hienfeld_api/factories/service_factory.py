"""
Service factory for creating and configuring analysis services.

This factory centralizes the creation of services used in the analysis
pipeline, supporting dependency injection and testability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TYPE_CHECKING

from hienfeld.config import load_config, AppConfig, AnalysisMode
from hienfeld.logging_config import get_logger
from hienfeld.services.service_cache import get_service_cache

# Service imports
from hienfeld.services.admin_check_service import AdminCheckService
from hienfeld.services.clause_library_service import ClauseLibraryService
from hienfeld.services.clustering_service import ClusteringService
from hienfeld.services.export_service import ExportService
from hienfeld.services.ingestion_service import IngestionService
from hienfeld.services.policy_parser_service import PolicyParserService
from hienfeld.services.preprocessing_service import PreprocessingService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService
from hienfeld.services.document_similarity_service import DocumentSimilarityService

if TYPE_CHECKING:
    from hienfeld.services.nlp_service import NLPService
    from hienfeld.services.similarity_service import SemanticSimilarityService
    from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
    from hienfeld.services.ai.rag_service import RAGService
    from hienfeld.services.ai.llm_analysis_service import LLMAnalysisService

logger = get_logger("factory")


@dataclass
class ServiceContainer:
    """
    Container holding all instantiated services for an analysis job.

    Groups related services together for easy access and dependency
    management throughout the analysis pipeline.
    """
    # Configuration
    config: AppConfig

    # Core services (always available)
    ingestion: IngestionService
    preprocessing: PreprocessingService
    policy_parser: PolicyParserService
    clustering: ClusteringService
    export: ExportService
    admin_check: AdminCheckService
    clause_library: ClauseLibraryService

    # Similarity services
    base_similarity: RapidFuzzSimilarityService
    tfidf: DocumentSimilarityService

    # Optional semantic services (may be None)
    nlp: Optional["NLPService"] = None
    semantic: Optional["SemanticSimilarityService"] = None
    hybrid: Optional["HybridSimilarityService"] = None

    # Optional AI services (may be None)
    embeddings: Optional[Any] = None
    vector_store: Optional[Any] = None
    rag: Optional["RAGService"] = None
    llm: Optional["LLMAnalysisService"] = None


class ServiceFactory:
    """
    Factory for creating and configuring service instances.

    Centralizes service instantiation and applies configuration settings.
    Uses caching for expensive services like NLP models.
    """

    def __init__(self) -> None:
        """Initialize the service factory."""
        self._cache = get_service_cache()

    def create_config(self, settings: Dict[str, Any]) -> AppConfig:
        """
        Create and configure an AppConfig from request settings.

        Args:
            settings: Dictionary of analysis settings from the request

        Returns:
            Configured AppConfig instance
        """
        config = load_config()

        # Apply analysis mode
        analysis_mode_str = settings.get("analysis_mode", "balanced")
        try:
            mode = AnalysisMode(analysis_mode_str)
            config.semantic.apply_mode(mode)
            logger.info(f"Analysis mode: {mode.value.upper()}")
        except ValueError:
            logger.warning(f"Invalid analysis mode '{analysis_mode_str}', defaulting to BALANCED")
            config.semantic.apply_mode(AnalysisMode.BALANCED)

        # Apply clustering settings
        strictness = float(settings.get("cluster_accuracy", 90)) / 100.0
        min_freq = int(settings.get("min_frequency", 20))
        win_size = int(settings.get("window_size", 100))
        use_window_limit = bool(settings.get("use_window_limit", True))

        config.clustering.similarity_threshold = strictness
        config.analysis_rules.frequency_standardize_threshold = min_freq
        config.clustering.leader_window_size = win_size if use_window_limit else 999999

        return config

    def create_base_services(self, config: AppConfig) -> ServiceContainer:
        """
        Create the core services needed for analysis.

        This creates the minimal set of services. Semantic and AI services
        should be initialized separately based on runtime conditions.

        Args:
            config: The configured AppConfig

        Returns:
            ServiceContainer with core services initialized
        """
        strictness = config.clustering.similarity_threshold

        # Base similarity service
        base_similarity = RapidFuzzSimilarityService(threshold=strictness)

        # Core data services
        ingestion = IngestionService(config)
        preprocessing = PreprocessingService(config)
        policy_parser = PolicyParserService(config)
        export = ExportService(config)

        # Analysis services
        admin_check = AdminCheckService(
            config=config,
            llm_client=None,
            enable_ai_checks=False
        )
        clause_library = ClauseLibraryService(config)
        tfidf = DocumentSimilarityService(config)

        # NLP service (cached)
        nlp = self._get_cached_nlp(config) if config.semantic.enable_nlp else None

        # Clustering service
        clustering = ClusteringService(
            config,
            similarity_service=base_similarity,
            nlp_service=nlp
        )

        return ServiceContainer(
            config=config,
            ingestion=ingestion,
            preprocessing=preprocessing,
            policy_parser=policy_parser,
            clustering=clustering,
            export=export,
            admin_check=admin_check,
            clause_library=clause_library,
            base_similarity=base_similarity,
            tfidf=tfidf,
            nlp=nlp,
        )

    def _get_cached_nlp(self, config: AppConfig) -> Optional["NLPService"]:
        """
        Get or create a cached NLP service.

        Args:
            config: The app configuration

        Returns:
            NLPService if available, None otherwise
        """
        if not config.semantic.enabled or not config.semantic.enable_nlp:
            return None

        try:
            from hienfeld.services.nlp_service import NLPService

            nlp = self._cache.get_or_create(
                f'nlp_service_{config.semantic.spacy_model}',
                lambda: NLPService(config),
                ttl=None  # Cache indefinitely
            )

            if nlp.is_available:
                logger.info("NLP service loaded (cached)")
                return nlp
            return None
        except Exception as e:
            logger.debug(f"NLP service not available: {e}")
            return None

    def get_cached_embeddings(self, config: AppConfig) -> Optional[Any]:
        """
        Get or create a cached embeddings service.

        Args:
            config: The app configuration

        Returns:
            Embeddings service if available, None otherwise
        """
        if not config.semantic.enable_embeddings:
            return None

        try:
            from hienfeld.services.ai.embeddings_service import create_embeddings_service

            return self._cache.get_or_create(
                f'embeddings_{config.semantic.embedding_model}',
                lambda: create_embeddings_service(
                    model_name=config.semantic.embedding_model
                ),
                ttl=None  # Cache indefinitely
            )
        except Exception as e:
            logger.warning(f"Embeddings service not available: {e}")
            return None
