# hienfeld/services/similarity_service.py
"""
Service for computing text similarity.
Provides multiple implementations (RapidFuzz, difflib, Semantic).

OPTIMIZED (v4.4): SemanticSimilarityService now supports PolicyEmbeddingsCache
for ~20-30s speedup when analyzing the same policy documents repeatedly.
"""
from typing import Protocol, Optional, List, Tuple, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
import difflib
import hashlib

import numpy as np


class SimilarityService(Protocol):
    """
    Protocol defining the similarity service interface.
    
    All similarity services must implement the similarity() method
    returning a value between 0.0 (no match) and 1.0 (exact match).
    """
    
    def similarity(self, a: str, b: str) -> float:
        """
        Compute similarity between two strings.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        ...


class DifflibSimilarityService:
    """
    Similarity service using Python's built-in difflib.
    
    Slower but requires no external dependencies.
    """
    
    def __init__(self, threshold: float = 0.9):
        """
        Initialize with similarity threshold.
        
        Args:
            threshold: Minimum similarity for a match (used for is_similar)
        """
        self.threshold = threshold
    
    def similarity(self, a: str, b: str) -> float:
        """
        Compute similarity using SequenceMatcher.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a, b).ratio()
    
    def is_similar(self, a: str, b: str) -> bool:
        """
        Check if two strings meet the similarity threshold.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            True if similarity >= threshold
        """
        return self.similarity(a, b) >= self.threshold


class RapidFuzzSimilarityService:
    """
    Similarity service using RapidFuzz library.
    
    Much faster than difflib, especially for large datasets.
    Falls back to difflib if RapidFuzz is not installed.
    """
    
    def __init__(self, threshold: float = 0.9):
        """
        Initialize with similarity threshold.
        
        Args:
            threshold: Minimum similarity for a match (0.0 to 1.0)
        """
        self.threshold = threshold
        self._use_rapidfuzz = False
        self._fallback = DifflibSimilarityService(threshold)
        
        try:
            from rapidfuzz import fuzz
            self._fuzz = fuzz
            self._use_rapidfuzz = True
        except ImportError:
            pass
    
    def similarity(self, a: str, b: str) -> float:
        """
        Compute similarity using RapidFuzz or fallback.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not a or not b:
            return 0.0
        
        if self._use_rapidfuzz:
            # RapidFuzz returns 0-100, convert to 0-1
            return self._fuzz.ratio(a, b) / 100.0
        else:
            return self._fallback.similarity(a, b)
    
    def is_similar(self, a: str, b: str) -> bool:
        """
        Check if two strings meet the similarity threshold.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            True if similarity >= threshold
        """
        return self.similarity(a, b) >= self.threshold
    
    @property
    def using_rapidfuzz(self) -> bool:
        """Check if RapidFuzz is being used."""
        return self._use_rapidfuzz


@dataclass
class SemanticMatch:
    """
    Result of a semantic similarity match.
    
    Attributes:
        text_id: Identifier of the matched text
        score: Similarity score (0.0 to 1.0)
        matched_text: The original text that was matched
        metadata: Additional metadata about the match
    """
    text_id: str
    score: float
    matched_text: str
    metadata: Optional[Dict[str, Any]] = None


class SemanticSimilarityService:
    """
    Similarity service using embeddings for semantic comparison.

    Compares texts based on MEANING rather than exact wording.
    Uses sentence-transformers to generate embeddings and cosine
    similarity to compare them.

    OPTIMIZED (v4.4): Supports PolicyEmbeddingsCache for ~20-30s speedup
    when analyzing the same policy documents repeatedly.

    Example:
        "Kosten gedwongen evacuatie" and "Dekking bij noodgedwongen evacuatie"
        have different words but same meaning -> high semantic similarity.
    """

    # Default threshold for semantic match
    DEFAULT_THRESHOLD = 0.70

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        embeddings_service: Optional[Any] = None,
        model_name: str = "intfloat/multilingual-e5-large-instruct",
        enable_policy_cache: bool = True
    ):
        """
        Initialize semantic similarity service.

        Args:
            threshold: Minimum similarity for a match (0.0 to 1.0)
            embeddings_service: Optional pre-configured embeddings service
            model_name: Model to use if creating new embeddings service
            enable_policy_cache: Enable caching of policy embeddings (v4.4)
        """
        self.threshold = threshold
        self.model_name = model_name
        self._embeddings_service = embeddings_service
        self._available = False

        # Index storage for pre-computed embeddings
        self._indexed_texts: Dict[str, str] = {}  # id -> text
        self._indexed_embeddings: Optional[np.ndarray] = None  # shape: (n, dim)
        self._indexed_ids: List[str] = []  # ordered list of IDs
        self._indexed_metadata: Dict[str, Dict[str, Any]] = {}  # id -> metadata

        # Embedding cache (enabled via enable_cache())
        self._embedding_cache_enabled = False
        self._embedding_cache_size = 5000
        self._cached_embed_single = None

        # Policy embeddings cache (v4.4)
        self._enable_policy_cache = enable_policy_cache
        self._policy_cache = None

        # Try to initialize
        self._init_embeddings_service()
    
    def _init_embeddings_service(self) -> None:
        """Initialize or validate the embeddings service."""
        if self._embeddings_service is not None:
            self._available = True
            return
        
        try:
            from .ai.embeddings_service import SentenceTransformerEmbeddingsService
            self._embeddings_service = SentenceTransformerEmbeddingsService(
                model_name=self.model_name
            )
            self._available = True
        except ImportError:
            self._available = False
    
    def similarity(self, a: str, b: str) -> float:
        """
        Compute semantic similarity between two strings.

        Uses cosine similarity of embeddings to measure how similar
        the MEANING of two texts is.

        For instruct models (e.g. multilingual-e5-large-instruct), `a` is
        treated as the query (clause) and `b` as the passage (policy section).
        This is correct for the primary use case of clause-to-conditions matching.
        For symmetric clause-to-clause comparisons the asymmetry is negligible.

        Args:
            a: First string (treated as query for instruct models)
            b: Second string (treated as passage for instruct models)

        Returns:
            Semantic similarity score between 0.0 and 1.0
        """
        if not self._available or not a or not b:
            return 0.0

        try:
            # Generate embeddings: a is the query, b is the passage
            emb_a = self._get_embedding(a, text_type="query")
            emb_b = self._get_embedding(b, text_type="passage")

            # Compute cosine similarity
            return self._cosine_similarity(emb_a, emb_b)
        except Exception:
            return 0.0
    
    def is_similar(self, a: str, b: str) -> bool:
        """
        Check if two strings are semantically similar.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            True if semantic similarity >= threshold
        """
        return self.similarity(a, b) >= self.threshold
    
    def index_texts(
        self,
        texts: Dict[str, str],
        metadata: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        Index multiple texts for fast similarity search.

        Pre-computes embeddings for all texts so that queries are fast.

        OPTIMIZED (v4.4): Uses PolicyEmbeddingsCache to avoid recomputing
        embeddings for documents that have been analyzed before.

        Args:
            texts: Dictionary mapping id -> text
            metadata: Optional dictionary mapping id -> metadata dict
        """
        if not self._available or not texts:
            return

        self._indexed_texts = texts.copy()
        self._indexed_ids = list(texts.keys())
        self._indexed_metadata = metadata or {}

        # Generate embeddings for all texts (with caching)
        text_list = [texts[tid] for tid in self._indexed_ids]

        # Try to use cached embeddings (v4.4 optimization)
        if self._enable_policy_cache and self._policy_cache is None:
            try:
                from .ai.policy_embeddings_cache import get_policy_embeddings_cache
                self._policy_cache = get_policy_embeddings_cache(persist_to_disk=False)
            except Exception:
                pass  # Cache not available, continue without it

        if self._policy_cache is not None:
            # Compute cache key from text content
            cache_key = self._compute_texts_cache_key(text_list)
            cached = self._policy_cache.get(cache_key, self.model_name)

            if cached is not None and len(cached.section_ids) == len(self._indexed_ids):
                # Use cached embeddings
                self._indexed_embeddings = cached.embeddings
                return

            # Compute embeddings - indexed texts are passages (policy sections)
            self._indexed_embeddings = self._embeddings_service.embed_texts(
                text_list, text_type="passage"
            )

            # Cache for next time
            self._policy_cache.put(
                cache_key,
                self._indexed_embeddings,
                self._indexed_ids,
                [self._indexed_metadata.get(tid, {}) for tid in self._indexed_ids],
                self.model_name
            )
        else:
            # No cache, compute directly - indexed texts are passages (policy sections)
            self._indexed_embeddings = self._embeddings_service.embed_texts(
                text_list, text_type="passage"
            )

    def _compute_texts_cache_key(self, texts: List[str]) -> str:
        """Compute a cache key from a list of texts."""
        hasher = hashlib.sha256()
        for text in texts:
            hasher.update((text or "").encode('utf-8'))
        return hasher.hexdigest()
    
    def find_similar(
        self, 
        query_text: str, 
        top_k: int = 5,
        min_score: float = None
    ) -> List[SemanticMatch]:
        """
        Find semantically similar texts from the index.
        
        Args:
            query_text: Text to search for
            top_k: Maximum number of results
            min_score: Minimum similarity score (defaults to threshold)
            
        Returns:
            List of SemanticMatch objects, sorted by score descending
        """
        if not self._available or self._indexed_embeddings is None:
            return []
        
        min_score = min_score if min_score is not None else self.threshold

        # Generate query embedding - the search text is a clause (query)
        query_embedding = self._get_embedding(query_text, text_type="query")

        # Compute similarities with all indexed texts
        similarities = self._cosine_similarity_batch(
            query_embedding, 
            self._indexed_embeddings
        )
        
        # Get top-k results above threshold
        results = []
        sorted_indices = np.argsort(similarities)[::-1]  # Descending
        
        for idx in sorted_indices[:top_k]:
            score = float(similarities[idx])
            if score < min_score:
                break
            
            text_id = self._indexed_ids[idx]
            results.append(SemanticMatch(
                text_id=text_id,
                score=score,
                matched_text=self._indexed_texts[text_id],
                metadata=self._indexed_metadata.get(text_id)
            ))
        
        return results
    
    def find_best_match(
        self, 
        query_text: str,
        min_score: float = None
    ) -> Optional[SemanticMatch]:
        """
        Find the single best semantic match.
        
        Args:
            query_text: Text to search for
            min_score: Minimum similarity score
            
        Returns:
            Best SemanticMatch or None if no match above threshold
        """
        matches = self.find_similar(query_text, top_k=1, min_score=min_score)
        return matches[0] if matches else None
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def _cosine_similarity_batch(
        self, 
        query: np.ndarray, 
        corpus: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between query and all corpus vectors."""
        # Normalize query
        query_norm = query / (np.linalg.norm(query) + 1e-10)
        
        # Normalize corpus (row-wise)
        corpus_norms = np.linalg.norm(corpus, axis=1, keepdims=True) + 1e-10
        corpus_normalized = corpus / corpus_norms
        
        # Dot product gives cosine similarity for normalized vectors
        return np.dot(corpus_normalized, query_norm)

    def enable_cache(self, cache_size: int = 5000) -> None:
        """
        Enable LRU caching for embeddings.

        This significantly improves performance when the same texts
        are embedded multiple times (common in clustering and matching).

        The cache key includes the text_type so that query and passage
        embeddings for the same text are stored separately (required for
        instruct-tuned models that use different prefixes per role).

        Args:
            cache_size: Maximum number of embeddings to cache
        """
        from functools import lru_cache

        # Create cached wrapper around embed_single.
        # The key argument is "text\x00text_type" so different roles are cached
        # separately without exposing text_type as a separate parameter
        # (lru_cache requires all arguments to be hashable).
        @lru_cache(maxsize=cache_size)
        def _cached_embed_single(cache_key: str) -> tuple:
            """Cache wrapper for embed_single. Returns tuple for hashability."""
            # Split the composite key back into text and text_type
            text, _, text_type = cache_key.partition("\x00")
            if not text_type:
                text_type = "query"
            emb = self._embeddings_service.embed_single(text, text_type=text_type)
            return tuple(emb.tolist())

        self._cached_embed_single = _cached_embed_single
        self._embedding_cache_enabled = True
        self._embedding_cache_size = cache_size

    def _get_embedding(self, text: str, text_type: str = "query") -> np.ndarray:
        """
        Get embedding for text with optional caching.

        Uses cache if enabled, otherwise calls embed_single directly.

        Args:
            text: Text to embed
            text_type: Role hint for instruct models ("query" or "passage").
                       Defaults to "query" (clause lookup). Pass "passage"
                       when embedding a policy section without a full index.

        Returns:
            Embedding vector as numpy array
        """
        if not self._embedding_cache_enabled or self._cached_embed_single is None:
            return self._embeddings_service.embed_single(text, text_type=text_type)

        # Get from cache (returns tuple). Cache key includes text_type so that
        # query and passage embeddings for the same text are stored separately.
        cached_tuple = self._cached_embed_single(text + "\x00" + text_type)
        return np.array(cached_tuple, dtype=np.float32)

    def similarity_batch(
        self,
        query: str,
        candidates: List[str],
        min_score: float = None
    ) -> List[Tuple[int, float]]:
        """
        Compute similarity for one query vs many candidates efficiently.

        This is much faster than calling similarity() in a loop because:
        1. Query embedding is computed only once
        2. Candidate embeddings are batched
        3. Cosine similarities are vectorized

        Args:
            query: Query text
            candidates: List of candidate texts
            min_score: Optional minimum score filter

        Returns:
            List of (index, score) tuples for candidates above min_score,
            sorted by score descending
        """
        if not self._available or not candidates:
            return []

        min_score = min_score if min_score is not None else self.threshold

        # Get query embedding - clause text is the search query
        query_emb = self._get_embedding(query, text_type="query")

        # Batch embed candidates - candidates are policy sections (passages)
        candidate_embs = self._embeddings_service.embed_texts(candidates, text_type="passage")

        # Compute all similarities at once
        similarities = self._cosine_similarity_batch(query_emb, candidate_embs)

        # Filter and sort
        results = [
            (idx, float(score))
            for idx, score in enumerate(similarities)
            if score >= min_score
        ]
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def clear_index(self) -> None:
        """Clear the indexed texts."""
        self._indexed_texts = {}
        self._indexed_embeddings = None
        self._indexed_ids = []
        self._indexed_metadata = {}
    
    @property
    def is_available(self) -> bool:
        """Check if semantic similarity is available."""
        return self._available
    
    @property
    def is_indexed(self) -> bool:
        """Check if texts have been indexed."""
        return self._indexed_embeddings is not None and len(self._indexed_ids) > 0
    
    @property
    def index_size(self) -> int:
        """Get number of indexed texts."""
        return len(self._indexed_ids)


def create_similarity_service(
    method: str = "rapidfuzz",
    threshold: float = 0.9,
    **kwargs
) -> SimilarityService:
    """
    Factory function to create appropriate similarity service.

    Args:
        method: "rapidfuzz", "difflib", or "semantic"
        threshold: Similarity threshold
        **kwargs: Additional arguments for specific services

    Returns:
        SimilarityService instance
    """
    if method == "semantic":
        return SemanticSimilarityService(threshold=threshold, **kwargs)
    elif method == "rapidfuzz":
        return RapidFuzzSimilarityService(threshold=threshold)
    else:
        return DifflibSimilarityService(threshold=threshold)

