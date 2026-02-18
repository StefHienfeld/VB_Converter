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

    The text_type parameter on embed_texts / embed_single is used by
    instruct-tuned models (e.g. multilingual-e5-large-instruct) to apply
    the correct prefix:
    - "query"   -> "query: {text}"   (clause texts doing the searching)
    - "passage" -> "passage: {text}" (policy sections being searched)
    Non-instruct models ignore this parameter.
    """

    def embed_texts(self, texts: List[str], text_type: str = "passage") -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            text_type: Role hint for instruct models ("query" or "passage")

        Returns:
            NumPy array of shape (len(texts), embedding_dim)
        """
        ...

    def embed_single(self, text: str, text_type: str = "query") -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed
            text_type: Role hint for instruct models ("query" or "passage")

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

    For Dutch texts, the multilingual-instruct model is preferred as default.
    The default model (intfloat/multilingual-e5-large-instruct) is optimized for
    retrieval tasks (query-passage matching) with 1024 dimensions.

    The -instruct model requires role-based prefixes for best performance:
    - Texts used as queries (clause lookup): prepend "query: "
    - Texts used as passages (policy sections): prepend "passage: "
    Pass text_type="query" or text_type="passage" to embed_texts / embed_single.
    """

    # Model options:
    # - "intfloat/multilingual-e5-large-instruct" - Best for Dutch retrieval (1024 dims, ~2.2GB) [DEFAULT]
    # - "intfloat/multilingual-e5-large" - Previous default (1024 dims, MTEB 66.3, ~2.2GB)
    # - "intfloat/multilingual-e5-base" - Good balance (768 dims, ~1.1GB)
    # - "paraphrase-multilingual-MiniLM-L12-v2" - Smaller, decent Dutch (384 dims, ~470MB)
    # - "all-MiniLM-L6-v2" - Fast, small (~90MB), English-optimized

    # Models that require query/passage prefixes for correct retrieval behaviour
    INSTRUCT_MODELS = {
        "intfloat/multilingual-e5-large-instruct",
        "intfloat/multilingual-e5-base-instruct",
        "intfloat/multilingual-e5-small-instruct",
        "intfloat/e5-large-instruct",
        "intfloat/e5-base-instruct",
        "intfloat/e5-small-instruct",
    }

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large-instruct"
    ):
        """
        Initialize with a sentence-transformers model.

        Args:
            model_name: HuggingFace model name or path
        """
        self.model_name = model_name
        self._model = None
        self._embedding_dim: Optional[int] = None
        # Whether this model requires query/passage prefixes
        self._requires_prefix: bool = model_name in self.INSTRUCT_MODELS
    
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
                    # Quick check for model files (case-insensitive comparison)
                    model_name_normalized = self.model_name.replace("/", "--").lower()
                    for item in cache_folder.glob("*"):
                        if model_name_normalized in item.name.lower():
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
    
    def _apply_prefix(self, texts: List[str], text_type: str) -> List[str]:
        """
        Apply query/passage prefix for instruct-tuned models.

        The -instruct variant of E5 models is trained with role prefixes:
        - "query: {text}" for texts used to look up relevant passages
        - "passage: {text}" for texts that are being searched against

        This method is a no-op for non-instruct models.

        Args:
            texts: List of text strings
            text_type: "query" for clause lookups, "passage" for policy sections

        Returns:
            List of prefixed texts (or original texts if prefix not needed)
        """
        if not self._requires_prefix:
            return texts
        if text_type not in ("query", "passage"):
            raise ValueError(f"text_type must be 'query' or 'passage', got '{text_type}'")
        prefix = f"{text_type}: "
        return [prefix + t for t in texts]

    def embed_texts(self, texts: List[str], text_type: str = "passage") -> np.ndarray:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of text strings
            text_type: Role of these texts for instruct models.
                       Use "passage" for policy sections (things being searched),
                       use "query" for clause texts (things doing the searching).
                       Has no effect for non-instruct models.

        Returns:
            NumPy array of embeddings
        """
        self._load_model()

        # Handle empty input
        if not texts:
            return np.array([])

        prefixed = self._apply_prefix(texts, text_type)

        logger.debug(f"Embedding {len(prefixed)} texts (batch_size=128, text_type={text_type})")
        # batch_size=128 gives ~23x speedup vs one-by-one (7ms -> 0.3ms per text)
        embeddings = self._model.encode(
            prefixed,
            batch_size=128,
            convert_to_numpy=True,
            show_progress_bar=len(prefixed) > 500,
        )
        return embeddings

    def embed_single(self, text: str, text_type: str = "query") -> np.ndarray:
        """
        Generate embedding for single text.

        Args:
            text: Text string
            text_type: Role of this text for instruct models.
                       Defaults to "query" because embed_single is typically
                       called for clause lookups (retrieval queries).
                       Use "passage" when encoding a single policy section.

        Returns:
            Embedding vector
        """
        self._load_model()
        prefixed = self._apply_prefix([text], text_type)
        return self._model.encode(prefixed, convert_to_numpy=True)[0]
    
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

    def __init__(self, embedding_dim: int = 1024):
        """
        Initialize with specified dimension.

        Args:
            embedding_dim: Dimensionality of dummy embeddings
        """
        self._embedding_dim = embedding_dim
        logger.warning("Using DummyEmbeddingsService - NOT for production use!")

    def embed_texts(self, texts: List[str], text_type: str = "passage") -> np.ndarray:
        """Generate random embeddings. text_type is accepted but ignored."""
        return np.random.randn(len(texts), self._embedding_dim).astype(np.float32)

    def embed_single(self, text: str, text_type: str = "query") -> np.ndarray:
        """Generate random embedding. text_type is accepted but ignored."""
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

