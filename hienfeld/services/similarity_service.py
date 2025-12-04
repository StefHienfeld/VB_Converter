# hienfeld/services/similarity_service.py
"""
Service for computing text similarity.
Provides multiple implementations (RapidFuzz, difflib, MinHash, Semantic).
"""
from typing import Protocol, Optional, List, Tuple, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
import difflib

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


class MinHashLSHSimilarityService:
    """
    Similarity service using MinHash LSH for near-duplicate detection.
    
    Excellent for very large datasets where O(n²) comparison is prohibitive.
    Requires datasketch library.
    """
    
    def __init__(
        self, 
        threshold: float = 0.9,
        num_perm: int = 128,
        shingle_size: int = 3
    ):
        """
        Initialize MinHash LSH service.
        
        Args:
            threshold: Jaccard similarity threshold
            num_perm: Number of permutations for MinHash
            shingle_size: Size of character n-grams
        """
        self.threshold = threshold
        self.num_perm = num_perm
        self.shingle_size = shingle_size
        self._available = False
        
        try:
            from datasketch import MinHash, MinHashLSH
            self._MinHash = MinHash
            self._MinHashLSH = MinHashLSH
            self._available = True
            self._lsh = None
            self._minhashes = {}
        except ImportError:
            pass
    
    def _create_minhash(self, text: str):
        """Create MinHash for a text string."""
        if not self._available:
            return None
        
        m = self._MinHash(num_perm=self.num_perm)
        # Create shingles
        for i in range(len(text) - self.shingle_size + 1):
            shingle = text[i:i + self.shingle_size]
            m.update(shingle.encode('utf-8'))
        return m
    
    def build_index(self, texts: dict) -> None:
        """
        Build LSH index from a dictionary of texts.
        
        Args:
            texts: Dictionary mapping id -> text
        """
        if not self._available:
            return
        
        self._lsh = self._MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        self._minhashes = {}
        
        for text_id, text in texts.items():
            mh = self._create_minhash(text)
            self._minhashes[text_id] = mh
            self._lsh.insert(text_id, mh)
    
    def query_similar(self, text: str) -> list:
        """
        Find similar texts from the index.
        
        Args:
            text: Query text
            
        Returns:
            List of similar text IDs
        """
        if not self._available or self._lsh is None:
            return []
        
        mh = self._create_minhash(text)
        return self._lsh.query(mh)
    
    def similarity(self, a: str, b: str) -> float:
        """
        Compute Jaccard similarity estimate between two strings.
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            Estimated Jaccard similarity
        """
        if not self._available:
            return 0.0
        
        mh_a = self._create_minhash(a)
        mh_b = self._create_minhash(b)
        return mh_a.jaccard(mh_b)
    
    @property
    def is_available(self) -> bool:
        """Check if MinHash LSH is available."""
        return self._available


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
        model_name: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize semantic similarity service.
        
        Args:
            threshold: Minimum similarity for a match (0.0 to 1.0)
            embeddings_service: Optional pre-configured embeddings service
            model_name: Model to use if creating new embeddings service
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
        
        Args:
            a: First string
            b: Second string
            
        Returns:
            Semantic similarity score between 0.0 and 1.0
        """
        if not self._available or not a or not b:
            return 0.0
        
        try:
            # Generate embeddings for both texts
            emb_a = self._embeddings_service.embed_single(a)
            emb_b = self._embeddings_service.embed_single(b)
            
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
        
        Args:
            texts: Dictionary mapping id -> text
            metadata: Optional dictionary mapping id -> metadata dict
        """
        if not self._available or not texts:
            return
        
        self._indexed_texts = texts.copy()
        self._indexed_ids = list(texts.keys())
        self._indexed_metadata = metadata or {}
        
        # Generate embeddings for all texts
        text_list = [texts[tid] for tid in self._indexed_ids]
        self._indexed_embeddings = self._embeddings_service.embed_texts(text_list)
    
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
        
        # Generate query embedding
        query_embedding = self._embeddings_service.embed_single(query_text)
        
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
        method: "rapidfuzz", "difflib", "minhash", or "semantic"
        threshold: Similarity threshold
        **kwargs: Additional arguments for specific services
        
    Returns:
        SimilarityService instance
    """
    if method == "semantic":
        return SemanticSimilarityService(threshold=threshold, **kwargs)
    elif method == "minhash":
        return MinHashLSHSimilarityService(threshold=threshold, **kwargs)
    elif method == "rapidfuzz":
        return RapidFuzzSimilarityService(threshold=threshold)
    else:
        return DifflibSimilarityService(threshold=threshold)

