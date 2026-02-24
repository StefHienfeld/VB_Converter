"""
Factory for initializing semantic and AI services.

This factory handles the complex initialization of:
- Embeddings service
- Vector store (FAISS)
- RAG service
- LLM analyzer
- Hybrid similarity service

Extracted from ServiceFactory to improve maintainability and testability.
"""

from __future__ import annotations

from typing import Any, List, Optional, TYPE_CHECKING

from hienfeld.config import AppConfig
from hienfeld.logging_config import get_logger
from hienfeld.settings import get_settings
from hienfeld.services.service_cache import get_service_cache
from hienfeld.services.similarity_service import SemanticSimilarityService

if TYPE_CHECKING:
    from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
    from hienfeld_api.factories.service_factory import ServiceContainer

logger = get_logger("semantic_factory")

# Check if hybrid similarity is available
try:
    from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False


class SemanticStackFactory:
    """
    Factory for initializing semantic and AI services.

    Handles the complex initialization of embeddings, RAG, LLM,
    and hybrid similarity services. Uses caching for expensive
    model loading operations.
    """

    def __init__(self) -> None:
        """Initialize the semantic stack factory."""
        self._cache = get_service_cache()

    def initialize(
        self,
        container: "ServiceContainer",
        policy_sections: List[Any],
        use_semantic: bool = True,
        ai_enabled: bool = False
    ) -> None:
        """
        Initialize the complete semantic stack.

        This includes TF-IDF training, embeddings, RAG, LLM,
        and hybrid similarity services.

        Args:
            container: Service container to update (modified in-place)
            policy_sections: Parsed policy document sections
            use_semantic: Whether to enable semantic features
            ai_enabled: Whether to enable AI/LLM features
        """
        config = container.config

        if not use_semantic or not config.semantic.enabled:
            logger.info("Semantic analysis disabled")
            return

        # Train TF-IDF on conditions if available
        self._train_tfidf(container, policy_sections)

        # Initialize embeddings + vector store + RAG
        if config.semantic.enable_embeddings:
            self._initialize_embeddings(container, policy_sections)

        # Initialize semantic similarity service
        self._initialize_semantic_service(container)

        # Initialize LLM analyzer (optional)
        if ai_enabled:
            self._initialize_llm(container)

        # Initialize hybrid similarity service
        if HYBRID_AVAILABLE and config.semantic.enabled:
            self._initialize_hybrid(container, policy_sections)

    def _train_tfidf(
        self,
        container: "ServiceContainer",
        policy_sections: List[Any]
    ) -> None:
        """Train TF-IDF model on policy sections."""
        config = container.config

        if not policy_sections:
            return
        if not container.tfidf.is_available:
            return
        if not config.semantic.enable_tfidf:
            return

        logger.info("Training TF-IDF model...")
        tfidf_corpus = [
            s.simplified_text for s in policy_sections
            if s.simplified_text
        ]

        if tfidf_corpus:
            container.tfidf.train_on_corpus(tfidf_corpus)
            logger.info(f"TF-IDF trained on {len(tfidf_corpus)} documents")

    def _initialize_embeddings(
        self,
        container: "ServiceContainer",
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

    def _initialize_semantic_service(self, container: "ServiceContainer") -> None:
        """Initialize semantic similarity service."""
        if container.embeddings is None:
            return

        config = container.config
        container.semantic = SemanticSimilarityService(
            embeddings_service=container.embeddings,
            model_name=config.semantic.embedding_model,
        )

        if not container.semantic.is_available:
            container.semantic = None

    def _initialize_llm(self, container: "ServiceContainer") -> None:
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

    def _initialize_hybrid(
        self,
        container: "ServiceContainer",
        policy_sections: Optional[List[Any]] = None
    ) -> None:
        """Initialize hybrid similarity service with optional FAISS index."""
        config = container.config
        mode_config = config.semantic.get_active_config()

        try:
            from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
            from hienfeld.services.synonym_service import SynonymService

            # Enable embedding cache if configured
            if mode_config.use_embedding_cache and container.semantic:
                container.semantic.enable_cache(mode_config.cache_size)
                logger.info(f"Embedding cache enabled: {mode_config.cache_size} entries")

            # Create synonym service
            synonym_service = self._create_synonym_service(config, mode_config)

            # Create hybrid service with pre-initialized services
            container.hybrid = HybridSimilarityService(
                config,
                rapidfuzz_service=container.base_similarity,
                nlp_service=container.nlp,
                synonym_service=synonym_service,
                tfidf_service=container.tfidf if mode_config.enable_tfidf else None,
                semantic_service=container.semantic if mode_config.enable_embeddings else None,
            )

            # Validate and configure
            if not self._validate_hybrid_service(container):
                return

            # NOTE: Clustering stays on RapidFuzz (base_similarity) intentionally.
            # Clustering detects near-duplicates, not paraphrases — embeddings are overkill.
            # This saves ~50 min on 6000-row datasets in ACCURATE mode.
            logger.info("Hybrid similarity ready (clustering stays on RapidFuzz for speed)")

            # Build FAISS index for fast ANN search
            if policy_sections and mode_config.enable_embeddings:
                self._build_faiss_index(container.hybrid, policy_sections)

        except Exception as e:
            logger.warning(f"Could not initialize hybrid similarity: {e}")
            container.hybrid = None

    def _create_synonym_service(
        self,
        config: AppConfig,
        mode_config: Any
    ) -> Optional[Any]:
        """Create synonym service if enabled."""
        if not mode_config.enable_synonyms:
            return None

        try:
            from hienfeld.services.synonym_service import SynonymService
            return SynonymService(config)
        except Exception as e:
            logger.debug(f"Synonym service not available: {e}")
            return None

    def _validate_hybrid_service(self, container: "ServiceContainer") -> bool:
        """Validate hybrid service has at least one semantic method available."""
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
            return False

        active_methods = ", ".join(
            k for k, v in services_available.items()
            if v and k != "rapidfuzz"
        )
        logger.info(f"Hybrid similarity active: {active_methods}")
        return True

    def _build_faiss_index(
        self,
        hybrid_service: "HybridSimilarityService",
        policy_sections: List[Any]
    ) -> None:
        """
        Build FAISS index for fast ANN search on policy sections.

        Args:
            hybrid_service: The hybrid similarity service
            policy_sections: Parsed policy document sections
        """
        try:
            section_texts = [
                s.simplified_text for s in policy_sections
                if hasattr(s, 'simplified_text') and s.simplified_text
            ]

            if not section_texts:
                logger.debug("No policy section texts available for FAISS index")
                return

            success = hybrid_service.build_faiss_index(section_texts)

            if success:
                logger.info(f"FAISS index built for {len(section_texts)} policy sections")
            else:
                logger.debug("FAISS index not built (embeddings may not be available)")

        except Exception as e:
            logger.warning(f"Could not build FAISS index: {e}")

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
                ttl=None
            )
        except Exception as e:
            logger.warning(f"Embeddings service not available: {e}")
            return None
