# hienfeld/services/similarity_service.py
"""
Service for computing text similarity.
Provides multiple implementations (RapidFuzz, difflib, MinHash).
"""
from typing import Protocol, Optional
from abc import ABC, abstractmethod
import difflib


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


def create_similarity_service(
    method: str = "rapidfuzz",
    threshold: float = 0.9,
    **kwargs
) -> SimilarityService:
    """
    Factory function to create appropriate similarity service.
    
    Args:
        method: "rapidfuzz", "difflib", or "minhash"
        threshold: Similarity threshold
        **kwargs: Additional arguments for specific services
        
    Returns:
        SimilarityService instance
    """
    if method == "minhash":
        return MinHashLSHSimilarityService(threshold=threshold, **kwargs)
    elif method == "rapidfuzz":
        return RapidFuzzSimilarityService(threshold=threshold)
    else:
        return DifflibSimilarityService(threshold=threshold)

