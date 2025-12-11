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
    
    Provides high-quality embeddings for semantic similarity.
    
    For Dutch texts, the multilingual model is recommended but requires more resources.
    The default model (all-MiniLM-L6-v2) is smaller and faster but optimized for English.
    """
    
    # Model options:
    # - "all-MiniLM-L6-v2" - Fast, small (~90MB), English-optimized
    # - "paraphrase-multilingual-MiniLM-L12-v2" - Good for Dutch (~470MB)
    # - "distiluse-base-multilingual-cased-v1" - Multilingual (~540MB)
    
    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2"
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
                import os
                from pathlib import Path
                
                # Check if model is already cached locally
                cache_folder = Path.home() / ".cache" / "huggingface" / "hub"
                model_exists = False
                if cache_folder.exists():
                    # Quick check for model files
                    for item in cache_folder.glob("*"):
                        if self.model_name.replace("/", "--") in item.name.lower():
                            model_exists = True
                            break
                
                if not model_exists:
                    logger.warning(
                        f"⚠️ Embedding model '{self.model_name}' not found in cache. "
                        f"First download takes 5-10 minutes. Skipping embeddings for now. "
                        f"Pre-download with: python -c \"from sentence_transformers import SentenceTransformer; "
                        f"SentenceTransformer('{self.model_name}')\""
                    )
                    return  # Skip loading, model stays None
                
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._embedding_dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded, embedding dim: {self._embedding_dim}")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. "
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

