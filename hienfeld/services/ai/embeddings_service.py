# hienfeld/services/ai/embeddings_service.py
"""
Service for generating text embeddings.
"""
from typing import List, Protocol, Optional
from abc import abstractmethod

import numpy as np

from ...logging_config import get_logger

logger = get_logger('embeddings_service')


class EmbeddingsService(Protocol):
    """
    Protocol for embedding services.
    
    Implementations should convert text to dense vector representations
    suitable for semantic similarity search.
    """
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            NumPy array of shape (len(texts), embedding_dim)
        """
        ...
    
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            NumPy array of shape (embedding_dim,)
        """
        ...
    
    @property
    def embedding_dim(self) -> int:
        """Return the dimensionality of embeddings."""
        ...


class SentenceTransformerEmbeddingsService:
    """
    Embedding service using sentence-transformers library.
    
    Provides high-quality multilingual embeddings suitable for
    Dutch policy text.
    """
    
    def __init__(
        self, 
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    ):
        """
        Initialize with a sentence-transformers model.
        
        Args:
            model_name: HuggingFace model name or path
        """
        self.model_name = model_name
        self._model = None
        self._embedding_dim: Optional[int] = None
    
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._embedding_dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded, embedding dim: {self._embedding_dim}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for embeddings. "
                    "Install with: pip install sentence-transformers"
                )
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            NumPy array of embeddings
        """
        self._load_model()
        
        # Handle empty input
        if not texts:
            return np.array([])
        
        logger.debug(f"Embedding {len(texts)} texts")
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings
    
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for single text.
        
        Args:
            text: Text string
            
        Returns:
            Embedding vector
        """
        self._load_model()
        return self._model.encode([text], convert_to_numpy=True)[0]
    
    @property
    def embedding_dim(self) -> int:
        """Get embedding dimensionality."""
        self._load_model()
        return self._embedding_dim
    
    @property
    def is_available(self) -> bool:
        """Check if sentence-transformers is available."""
        try:
            import sentence_transformers
            return True
        except ImportError:
            return False


class DummyEmbeddingsService:
    """
    Dummy embedding service for testing without ML dependencies.
    
    Generates random embeddings - NOT for production use.
    """
    
    def __init__(self, embedding_dim: int = 384):
        """
        Initialize with specified dimension.
        
        Args:
            embedding_dim: Dimensionality of dummy embeddings
        """
        self._embedding_dim = embedding_dim
        logger.warning("Using DummyEmbeddingsService - NOT for production use!")
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate random embeddings."""
        return np.random.randn(len(texts), self._embedding_dim).astype(np.float32)
    
    def embed_single(self, text: str) -> np.ndarray:
        """Generate random embedding."""
        return np.random.randn(self._embedding_dim).astype(np.float32)
    
    @property
    def embedding_dim(self) -> int:
        """Get embedding dimensionality."""
        return self._embedding_dim


def create_embeddings_service(
    method: str = "sentence-transformers",
    model_name: Optional[str] = None,
    **kwargs
) -> EmbeddingsService:
    """
    Factory function to create embedding service.
    
    Args:
        method: "sentence-transformers" or "dummy"
        model_name: Model name for sentence-transformers
        **kwargs: Additional arguments
        
    Returns:
        EmbeddingsService instance
    """
    if method == "dummy":
        return DummyEmbeddingsService(**kwargs)
    else:
        if model_name:
            return SentenceTransformerEmbeddingsService(model_name)
        return SentenceTransformerEmbeddingsService()

