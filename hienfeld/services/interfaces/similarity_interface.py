# hienfeld/services/interfaces/similarity_interface.py
"""
Protocol interfaces for similarity services.

These interfaces define the contracts that similarity services must implement,
enabling dependency injection and easy mocking for tests.

Example usage:
    def my_function(similarity: ISimilarityService) -> float:
        return similarity.similarity("text a", "text b")
"""

from typing import Protocol, List, Tuple, Optional, Dict, Any, runtime_checkable


@runtime_checkable
class ISimilarityService(Protocol):
    """
    Protocol defining the base similarity service interface.

    All similarity services must implement these methods for computing
    text similarity scores between 0.0 (no match) and 1.0 (exact match).

    Implementations:
    - RapidFuzzSimilarityService: Fast fuzzy string matching
    - DifflibSimilarityService: Python built-in (fallback)
    - SemanticSimilarityService: Embedding-based semantic matching
    - HybridSimilarityService: Multi-method weighted matching
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

    def is_similar(self, a: str, b: str) -> bool:
        """
        Check if two strings meet the similarity threshold.

        Args:
            a: First string
            b: Second string

        Returns:
            True if similarity >= threshold
        """
        ...


@runtime_checkable
class IBatchSimilarityService(Protocol):
    """
    Protocol for similarity services that support efficient batch operations.

    Batch operations can be significantly faster than calling similarity()
    in a loop, especially for embedding-based services.
    """

    def find_best_match(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.0
    ) -> Optional[Tuple[int, float]]:
        """
        Find the best matching text from a list of candidates.

        Args:
            query: Query text to match
            candidates: List of candidate texts to compare against
            min_score: Minimum score threshold

        Returns:
            Tuple of (index, score) for best match, or None if no match above threshold
        """
        ...

    def find_all_matches(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.5,
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Find all matching texts above a threshold.

        Args:
            query: Query text to match
            candidates: List of candidate texts
            min_score: Minimum score threshold
            top_k: Maximum number of results

        Returns:
            List of (index, score) tuples, sorted by score descending
        """
        ...


@runtime_checkable
class ISemanticSimilarityService(Protocol):
    """
    Protocol for semantic similarity services using embeddings.

    Semantic services compare texts based on MEANING rather than exact wording,
    using vector embeddings and cosine similarity.
    """

    @property
    def is_available(self) -> bool:
        """Check if semantic similarity is available (model loaded)."""
        ...

    @property
    def is_indexed(self) -> bool:
        """Check if texts have been indexed for fast search."""
        ...

    def similarity(self, a: str, b: str) -> float:
        """
        Compute semantic similarity between two strings.

        Uses cosine similarity of embeddings to measure how similar
        the MEANING of two texts is.

        Args:
            a: First string
            b: Second string

        Returns:
            Semantic similarity score between 0.0 and 1.0
        """
        ...

    def index_texts(
        self,
        texts: Dict[str, str],
        metadata: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        Index multiple texts for fast similarity search.

        Pre-computes embeddings for all texts so that queries are fast.

        Args:
            texts: Dictionary mapping id -> text
            metadata: Optional dictionary mapping id -> metadata dict
        """
        ...

    def find_similar(
        self,
        query_text: str,
        top_k: int = 5,
        min_score: Optional[float] = None
    ) -> List[Any]:
        """
        Find semantically similar texts from the index.

        Args:
            query_text: Text to search for
            top_k: Maximum number of results
            min_score: Minimum similarity score

        Returns:
            List of SemanticMatch objects, sorted by score descending
        """
        ...

    def enable_cache(self, cache_size: int = 5000) -> None:
        """
        Enable LRU caching for embeddings.

        Args:
            cache_size: Maximum number of embeddings to cache
        """
        ...


@runtime_checkable
class IHybridSimilarityService(ISimilarityService, IBatchSimilarityService, Protocol):
    """
    Protocol for hybrid similarity services combining multiple methods.

    Hybrid services combine multiple similarity techniques (fuzzy, lemmatized,
    TF-IDF, synonyms, embeddings) with configurable weights.
    """

    def train_tfidf(self, documents: List[str]) -> None:
        """
        Train the TF-IDF model on a corpus.

        Args:
            documents: List of document texts to train on
        """
        ...

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get service usage statistics.

        Returns:
            Dictionary with statistics including:
            - call_count: Number of similarity calls
            - total_time_ms: Total computation time
            - services_available: Dict of available services
        """
        ...

    def clear_caches(self) -> None:
        """Clear all internal caches."""
        ...
