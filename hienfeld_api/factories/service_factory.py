"""
Service factory for creating and configuring analysis services.

This factory centralizes the creation of services used in the analysis
pipeline, supporting dependency injection and testability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from hienfeld.config import load_config, AppConfig, AnalysisMode
from hienfeld.logging_config import get_logger
from hienfeld.settings import get_settings
from hienfeld.services.service_cache import get_service_cache

# Service imports
from hienfeld.services.admin_check_service import AdminCheckService
from hienfeld.services.clause_library_service import ClauseLibraryService
from hienfeld.services.clustering_service import ClusteringService
from hienfeld.services.export_service import ExportService
from hienfeld.services.ingestion_service import IngestionService
from hienfeld.services.policy_parser_service import PolicyParserService
from hienfeld.services.preprocessing_service import PreprocessingService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService, SemanticSimilarityService
from hienfeld.services.document_similarity_service import DocumentSimilarityService
from hienfeld.services.analysis_service import AnalysisService
from hienfeld.services.custom_instructions_service import CustomInstructionsService
from hienfeld.services.reference_analysis_service import ReferenceAnalysisService

if TYPE_CHECKING:
    from hienfeld.services.nlp_service import NLPService
    from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
    from hienfeld.services.ai.rag_service import RAGService
    from hienfeld.services.ai.llm_analysis_service import LLMAnalysisService

logger = get_logger("factory")

# Check if hybrid similarity is available
try:
    from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False


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
    semantic: Optional[SemanticSimilarityService] = None
    hybrid: Optional["HybridSimilarityService"] = None

    # Optional AI services (may be None)
    embeddings: Optional[Any] = None
    vector_store: Optional[Any] = None
    rag: Optional["RAGService"] = None
    llm: Optional["LLMAnalysisService"] = None

    # Optional custom services (may be None)
    custom_instructions: Optional[CustomInstructionsService] = None
    reference: Optional[ReferenceAnalysisService] = None

    # Analysis service (created after semantic stack is initialized)
    analysis: Optional[AnalysisService] = None


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

    def initialize_semantic_stack(
        self,
        container: ServiceContainer,
        policy_sections: List[Any],
        use_semantic: bool = True,
        ai_enabled: bool = False
    ) -> None:
        """
        Initialize semantic services (embeddings, RAG, TF-IDF, hybrid).

        Modifies the container in-place to add semantic services.

        Args:
            container: Service container to update
            policy_sections: Parsed policy document sections
            use_semantic: Whether to enable semantic features
            ai_enabled: Whether to enable AI/LLM features
        """
        config = container.config

        if not use_semantic or not config.semantic.enabled:
            logger.info("Semantic analysis disabled")
            return

        # Train TF-IDF on conditions if available
        if policy_sections and container.tfidf.is_available and config.semantic.enable_tfidf:
            logger.info("Training TF-IDF model...")
            tfidf_corpus = [s.simplified_text for s in policy_sections if s.simplified_text]
            if tfidf_corpus:
                container.tfidf.train_on_corpus(tfidf_corpus)
                logger.info(f"TF-IDF trained on {len(tfidf_corpus)} documents")

        # Embeddings + vector store + RAG
        if config.semantic.enable_embeddings:
            self._initialize_embeddings(container, policy_sections)

        # Semantic similarity service
        if container.embeddings is not None:
            container.semantic = SemanticSimilarityService(
                embeddings_service=container.embeddings,
                model_name=config.semantic.embedding_model,
            )
            if not container.semantic.is_available:
                container.semantic = None

        # LLM analyzer (optional)
        if ai_enabled:
            self._initialize_llm(container)

        # Hybrid similarity service
        if HYBRID_AVAILABLE and config.semantic.enabled:
            self._initialize_hybrid(container)

    def _initialize_embeddings(
        self,
        container: ServiceContainer,
        policy_sections: List[Any]
    ) -> None:
        """Initialize embeddings service, vector store, and RAG."""
        config = container.config

        try:
            from hienfeld.services.ai.embeddings_service import create_embeddings_service
            from hienfeld.services.ai.vector_store import create_vector_store
            from hienfeld.services.ai.rag_service import RAGService

            # Get or create cached embeddings service
            container.embeddings = self._cache.get_or_create(
                f'embeddings_{config.semantic.embedding_model}',
                lambda: create_embeddings_service(
                    model_name=config.semantic.embedding_model
                ),
                ttl=None
            )
            logger.info(f"Embeddings service loaded (model: {config.semantic.embedding_model})")

            # Vector store
            container.vector_store = create_vector_store(
                method=config.ai.vector_store_type or "faiss",
                embedding_dim=getattr(container.embeddings, "embedding_dim", 384),
            )

            # RAG service
            container.rag = RAGService(container.embeddings, container.vector_store)
            container.rag.index_policy_sections(policy_sections)
            logger.info("RAG index built for semantic context")

        except ImportError as exc:
            logger.warning(f"Embeddings/RAG not available: {exc}")
        except Exception as exc:
            logger.warning(f"RAG initialization failed: {exc}")

    def _initialize_llm(self, container: ServiceContainer) -> None:
        """Initialize LLM analyzer service."""
        try:
            from openai import OpenAI
            from hienfeld.services.ai.llm_analysis_service import LLMAnalysisService

            env_settings = get_settings()
            openai_key = env_settings.openai_api_key

            if openai_key:
                openai_client = OpenAI(api_key=openai_key)
                container.llm = LLMAnalysisService(
                    client=openai_client,
                    rag_service=container.rag,
                    model_name=env_settings.llm_model or "gpt-4o-mini",
                )
                logger.info(f"AI analysis enabled with model: {env_settings.llm_model}")
            else:
                logger.warning("AI enabled but OPENAI_API_KEY not set")

        except ImportError:
            logger.warning("OpenAI package not installed")
        except Exception as exc:
            logger.warning(f"LLM analyzer initialization failed: {exc}")

    def _initialize_hybrid(self, container: ServiceContainer) -> None:
        """Initialize hybrid similarity service."""
        config = container.config
        mode_config = config.semantic.get_active_config()

        try:
            from hienfeld.services.hybrid_similarity_service import HybridSimilarityService

            # Enable embedding cache if configured
            if mode_config.use_embedding_cache and container.semantic:
                container.semantic.enable_cache(mode_config.cache_size)
                logger.info(f"Embedding cache enabled: {mode_config.cache_size} entries")

            # Create hybrid service
            container.hybrid = HybridSimilarityService(
                config,
                tfidf_service=container.tfidf if mode_config.enable_tfidf else None,
                semantic_service=container.semantic if mode_config.enable_embeddings else None,
            )

            # Check available services
            stats = container.hybrid.get_statistics()
            services_available = stats.get('services_available', {})
            semantic_count = sum([
                services_available.get('nlp', False),
                services_available.get('synonyms', False),
                services_available.get('tfidf', False),
                services_available.get('embeddings', False)
            ])

            if semantic_count == 0:
                logger.warning("Hybrid similarity disabled: no semantic services available")
                container.hybrid = None
            else:
                active_methods = ", ".join(
                    k for k, v in services_available.items() if v and k != "rapidfuzz"
                )
                logger.info(f"Hybrid similarity active: {active_methods}")

                # Upgrade clustering to use hybrid similarity
                container.clustering.similarity_service = container.hybrid
                logger.info("Clustering upgraded to hybrid similarity")

        except Exception as e:
            logger.warning(f"Could not initialize hybrid similarity: {e}")
            container.hybrid = None

    def create_custom_instructions(
        self,
        container: ServiceContainer,
        extra_instruction: str
    ) -> None:
        """
        Create custom instructions service if instructions provided.

        Args:
            container: Service container to update
            extra_instruction: Raw instruction text from user
        """
        if not extra_instruction:
            return

        service = CustomInstructionsService(
            fuzzy_service=container.base_similarity,
            semantic_service=container.semantic,
            hybrid_service=container.hybrid,
        )

        loaded_count = service.load_instructions(extra_instruction)
        if loaded_count > 0:
            container.custom_instructions = service
            logger.info(f"Custom instructions loaded: {loaded_count} rules")
        else:
            logger.warning("Custom instructions provided but could not be parsed")

    def create_reference_service(
        self,
        container: ServiceContainer,
        reference_file: Optional[tuple[bytes, str]]
    ) -> None:
        """
        Create reference analysis service if reference file provided.

        Args:
            container: Service container to update
            reference_file: Tuple of (bytes, filename) or None
        """
        if not reference_file:
            return

        ref_bytes, ref_filename = reference_file
        logger.info(f"Loading reference file: {ref_filename} ({len(ref_bytes)} bytes)")

        try:
            service = ReferenceAnalysisService(
                config=container.config,
                similarity_service=container.hybrid or container.base_similarity,
            )

            ref_data = service.load_reference_file(ref_bytes, ref_filename)
            ref_count = len(ref_data.clauses) if ref_data else 0

            container.reference = service
            logger.info(f"Reference analysis loaded: {ref_count} clauses")

        except Exception as e:
            logger.error(f"Could not load reference file: {e}", exc_info=True)

    def create_analysis_service(self, container: ServiceContainer) -> AnalysisService:
        """
        Create the analysis service with all dependencies.

        Should be called after semantic stack is initialized.

        Args:
            container: Service container with all services

        Returns:
            Configured AnalysisService
        """
        service = AnalysisService(
            container.config,
            ai_analyzer=container.llm,
            similarity_service=container.base_similarity,
            semantic_similarity_service=container.semantic,
            hybrid_similarity_service=container.hybrid,
            clause_library_service=container.clause_library if container.clause_library.is_loaded else None,
            admin_check_service=container.admin_check,
            custom_instructions_service=container.custom_instructions,
            reference_service=container.reference,
        )

        container.analysis = service
        return service

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
