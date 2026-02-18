# hienfeld/services/ai/rag_service.py
"""
RAG (Retrieval Augmented Generation) service for policy document search.

Enhanced with:
- Cross-Encoder Re-Ranking for improved retrieval precision
- Policy Embeddings Cache for 20-30s speedup on repeated documents (v4.4)
"""
from typing import List, Optional, TYPE_CHECKING

from ...domain.policy_document import PolicyDocumentSection
from ...domain.clause import Clause
from .embeddings_service import EmbeddingsService
from .vector_store import VectorStore
from .policy_embeddings_cache import get_policy_embeddings_cache, PolicyEmbeddingsCache
from ...logging_config import get_logger

if TYPE_CHECKING:
    from .reranking_service import ReRankingService

logger = get_logger('rag_service')


class RAGService:
    """
    Retrieval Augmented Generation service.

    Combines embedding-based retrieval with policy document sections
    to find relevant context for clause analysis.

    Enhanced features:
    - Cross-Encoder Re-Ranking for +15-25% precision
    - Policy Embeddings Cache for 20-30s speedup on repeated documents (v4.4)
    """

    def __init__(
        self,
        embeddings_service: EmbeddingsService,
        vector_store: VectorStore,
        reranking_service: Optional['ReRankingService'] = None,
        enable_reranking: bool = True,
        enable_embedding_cache: bool = True
    ):
        """
        Initialize RAG service.

        Args:
            embeddings_service: Service for generating embeddings
            vector_store: Store for vector similarity search
            reranking_service: Optional re-ranking service for improved precision
            enable_reranking: Enable re-ranking if service available (default: True)
            enable_embedding_cache: Enable caching of policy embeddings (default: True)
        """
        self.embeddings_service = embeddings_service
        self.vector_store = vector_store
        self.reranking_service = reranking_service
        self.enable_reranking = enable_reranking
        self.enable_embedding_cache = enable_embedding_cache
        self._indexed = False

        # Get embeddings cache (singleton)
        self._embeddings_cache: Optional[PolicyEmbeddingsCache] = None
        if enable_embedding_cache:
            try:
                self._embeddings_cache = get_policy_embeddings_cache(persist_to_disk=False)
            except Exception as e:
                logger.warning(f"Could not initialize embeddings cache: {e}")

        # Track embedding model name for cache key
        self._embedding_model_name = getattr(
            embeddings_service, 'model_name', 'unknown'
        )
    
    def index_policy_sections(
        self,
        sections: List[PolicyDocumentSection]
    ) -> None:
        """
        Index policy document sections for retrieval.

        OPTIMIZED (v4.4): Uses PolicyEmbeddingsCache to avoid recomputing
        embeddings for documents that have been analyzed before.
        This typically saves 20-30 seconds per analysis.

        Args:
            sections: List of policy sections to index
        """
        if not sections:
            logger.warning("No sections to index")
            return

        logger.info(f"Indexing {len(sections)} policy sections")

        # Extract texts and metadata
        texts = [s.simplified_text for s in sections]
        ids = [s.id for s in sections]
        metadata = [
            {
                'article_id': s.id,
                'title': s.title,
                'page': s.page_number,
                'document_id': s.document_id,
                'raw_text': s.raw_text[:500]  # Store truncated text
            }
            for s in sections
        ]

        # Try to use cached embeddings (v4.4 optimization)
        vectors = None

        if self._embeddings_cache and self.enable_embedding_cache:
            # Compute cache key from section content
            cache_key = self._embeddings_cache.compute_sections_key(sections)

            # Check cache
            cached = self._embeddings_cache.get(cache_key, self._embedding_model_name)

            if cached is not None:
                # Validate cached data matches current sections
                if (
                    len(cached.section_ids) == len(ids) and
                    cached.section_ids == ids
                ):
                    vectors = cached.embeddings
                    logger.info(
                        f"Using cached embeddings for {len(sections)} sections "
                        f"(saved ~{len(sections) * 5}ms)"
                    )
                else:
                    logger.debug(
                        f"Cache mismatch: sections changed. "
                        f"Cached: {len(cached.section_ids)}, current: {len(ids)}"
                    )

        # Compute embeddings if not cached
        if vectors is None:
            logger.info("Computing embeddings (no cache hit)...")
            # Policy sections are passages being indexed for retrieval
            vectors = self.embeddings_service.embed_texts(texts, text_type="passage")

            # Store in cache for next time
            if self._embeddings_cache and self.enable_embedding_cache:
                cache_key = self._embeddings_cache.compute_sections_key(sections)
                self._embeddings_cache.put(
                    cache_key,
                    vectors,
                    ids,
                    metadata,
                    self._embedding_model_name
                )
                logger.info(f"Embeddings cached for future use ({len(sections)} sections)")

        # Clear existing index and add new documents
        self.vector_store.clear()
        self.vector_store.add_documents(ids, vectors, metadata)

        self._indexed = True
        logger.info("Policy sections indexed successfully")
    
    def retrieve_relevant_sections(
        self,
        clause_text: str,
        top_k: int = 3,
        rerank: bool = True
    ) -> List[dict]:
        """
        Find policy sections relevant to a clause.

        Uses a two-stage retrieval:
        1. Bi-encoder embedding search (fast, gets candidates)
        2. Cross-encoder re-ranking (accurate, refines top results)

        Args:
            clause_text: Clause text to search for
            top_k: Number of results to return
            rerank: Apply re-ranking if available (default: True)

        Returns:
            List of relevant section results with id, score, metadata
        """
        if not self._indexed:
            logger.warning("No documents indexed yet")
            return []

        # Stage 1: Bi-encoder retrieval (get more candidates for re-ranking)
        retrieval_k = top_k * 3 if (rerank and self._can_rerank()) else top_k
        # Clause text is the search query, policy sections are the passages
        query_vector = self.embeddings_service.embed_single(clause_text, text_type="query")
        results = self.vector_store.similarity_search(query_vector, k=retrieval_k)

        logger.debug(f"Stage 1: Retrieved {len(results)} candidates")

        # Stage 2: Cross-encoder re-ranking (optional)
        if rerank and self._can_rerank() and len(results) > 1:
            try:
                results = self.reranking_service.rerank(
                    query=clause_text,
                    results=results,
                    top_k=top_k,
                    text_key='raw_text'
                )
                logger.debug(f"Stage 2: Re-ranked to {len(results)} results")
            except Exception as e:
                logger.warning(f"Re-ranking failed: {e}, using original order")
                results = results[:top_k]
        else:
            results = results[:top_k]

        logger.debug(f"Found {len(results)} relevant sections for query")
        return results

    def _can_rerank(self) -> bool:
        """Check if re-ranking is available and enabled."""
        return (
            self.enable_reranking and
            self.reranking_service is not None and
            self.reranking_service.is_available
        )
    
    def retrieve_for_clause(
        self, 
        clause: Clause, 
        top_k: int = 3
    ) -> List[dict]:
        """
        Find policy sections relevant to a Clause object.
        
        Args:
            clause: Clause to search for
            top_k: Number of results
            
        Returns:
            List of relevant section results
        """
        # Use simplified text for more consistent matching
        return self.retrieve_relevant_sections(clause.simplified_text, top_k)
    
    def get_context_for_analysis(
        self, 
        clause_text: str, 
        top_k: int = 3,
        min_score: float = 0.5
    ) -> str:
        """
        Get formatted context text for LLM analysis.
        
        Args:
            clause_text: Clause to analyze
            top_k: Number of sections to include
            min_score: Minimum similarity score
            
        Returns:
            Formatted context string
        """
        results = self.retrieve_relevant_sections(clause_text, top_k)
        
        # Filter by score
        relevant = [r for r in results if r['score'] >= min_score]
        
        if not relevant:
            return "Geen relevante voorwaarden gevonden."
        
        # Format context as XML for structured LLM parsing
        context_parts = []
        for r in relevant:
            meta = r['metadata']
            text = meta.get('raw_text', '')
            article = meta.get('article_id', 'Onbekend')
            title = meta.get('title', '')

            part = f"""<artikel id="{article}">
  <titel>{title}</titel>
  <inhoud>{text}</inhoud>
</artikel>"""
            context_parts.append(part)

        return "\n".join(context_parts)
    
    def is_ready(self) -> bool:
        """Check if RAG service is ready for queries."""
        return self._indexed
    
    def clear(self) -> None:
        """Clear the index."""
        self.vector_store.clear()
        self._indexed = False

