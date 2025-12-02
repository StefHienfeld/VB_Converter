# hienfeld/services/ai/vector_store.py
"""
Vector store implementations for semantic search.
"""
from typing import List, Dict, Optional, Protocol
from abc import abstractmethod

import numpy as np

from ...logging_config import get_logger

logger = get_logger('vector_store')


class VectorStore(Protocol):
    """
    Protocol for vector store implementations.
    
    Vector stores enable efficient similarity search over embeddings.
    """
    
    def add_documents(
        self, 
        ids: List[str], 
        vectors: np.ndarray, 
        metadata: List[dict]
    ) -> None:
        """
        Add documents to the store.
        
        Args:
            ids: Unique identifiers for documents
            vectors: Embedding vectors (n_docs, embedding_dim)
            metadata: Metadata for each document
        """
        ...
    
    def similarity_search(
        self, 
        query_vector: np.ndarray, 
        k: int = 3,
        filters: Optional[dict] = None
    ) -> List[dict]:
        """
        Find similar documents.
        
        Args:
            query_vector: Query embedding
            k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of results with id, score, metadata
        """
        ...
    
    def clear(self) -> None:
        """Clear all documents from the store."""
        ...


class FaissVectorStore:
    """
    Vector store using FAISS for efficient similarity search.
    
    FAISS provides fast approximate nearest neighbor search,
    suitable for large document collections.
    """
    
    def __init__(self, embedding_dim: int = 384, use_gpu: bool = False):
        """
        Initialize FAISS vector store.
        
        Args:
            embedding_dim: Dimensionality of embeddings
            use_gpu: Whether to use GPU acceleration
        """
        self.embedding_dim = embedding_dim
        self.use_gpu = use_gpu
        self._index = None
        self._id_map: List[str] = []
        self._metadata: List[dict] = []
        self._faiss = None
        
        self._init_faiss()
    
    def _init_faiss(self):
        """Initialize FAISS index."""
        try:
            import faiss
            self._faiss = faiss
            
            # Create index (L2 distance)
            self._index = faiss.IndexFlatL2(self.embedding_dim)
            
            # Optionally use GPU
            if self.use_gpu and faiss.get_num_gpus() > 0:
                self._index = faiss.index_cpu_to_gpu(
                    faiss.StandardGpuResources(),
                    0,
                    self._index
                )
            
            logger.info(f"FAISS index initialized (dim={self.embedding_dim})")
        except ImportError:
            logger.warning("FAISS not installed - vector search disabled")
    
    def add_documents(
        self, 
        ids: List[str], 
        vectors: np.ndarray, 
        metadata: List[dict]
    ) -> None:
        """
        Add documents to FAISS index.
        
        Args:
            ids: Document identifiers
            vectors: Embedding vectors
            metadata: Document metadata
        """
        if self._index is None:
            logger.error("FAISS not initialized")
            return
        
        # Ensure vectors are float32 and contiguous
        vectors = np.ascontiguousarray(vectors.astype(np.float32))
        
        # Add to index
        self._index.add(vectors)
        
        # Store mappings
        self._id_map.extend(ids)
        self._metadata.extend(metadata)
        
        logger.info(f"Added {len(ids)} documents to index (total: {self._index.ntotal})")
    
    def similarity_search(
        self, 
        query_vector: np.ndarray, 
        k: int = 3,
        filters: Optional[dict] = None
    ) -> List[dict]:
        """
        Search for similar documents.
        
        Args:
            query_vector: Query embedding
            k: Number of results
            filters: Optional metadata filters (not fully implemented)
            
        Returns:
            List of results with id, score, metadata
        """
        if self._index is None or self._index.ntotal == 0:
            return []
        
        # Ensure query is float32 and 2D
        query = np.ascontiguousarray(
            query_vector.reshape(1, -1).astype(np.float32)
        )
        
        # Search (k might be larger than index size)
        actual_k = min(k, self._index.ntotal)
        distances, indices = self._index.search(query, actual_k)
        
        # Build results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:  # Invalid index
                continue
            
            result = {
                'id': self._id_map[idx],
                'score': float(1 / (1 + dist)),  # Convert distance to similarity
                'metadata': self._metadata[idx] if idx < len(self._metadata) else {}
            }
            
            # Apply filters (simple implementation)
            if filters:
                meta = result['metadata']
                if not all(meta.get(k) == v for k, v in filters.items()):
                    continue
            
            results.append(result)
        
        return results
    
    def clear(self) -> None:
        """Clear the index."""
        if self._faiss:
            self._index = self._faiss.IndexFlatL2(self.embedding_dim)
        self._id_map = []
        self._metadata = []
        logger.info("Vector store cleared")
    
    @property
    def is_available(self) -> bool:
        """Check if FAISS is available."""
        return self._faiss is not None
    
    @property
    def document_count(self) -> int:
        """Get number of documents in index."""
        return self._index.ntotal if self._index else 0


class SimpleVectorStore:
    """
    Simple in-memory vector store using NumPy.
    
    No external dependencies, but slower for large datasets.
    Good for testing and small document sets.
    """
    
    def __init__(self, embedding_dim: int = 384):
        """
        Initialize simple vector store.
        
        Args:
            embedding_dim: Dimensionality of embeddings
        """
        self.embedding_dim = embedding_dim
        self._vectors: Optional[np.ndarray] = None
        self._ids: List[str] = []
        self._metadata: List[dict] = []
    
    def add_documents(
        self, 
        ids: List[str], 
        vectors: np.ndarray, 
        metadata: List[dict]
    ) -> None:
        """Add documents to store."""
        vectors = vectors.astype(np.float32)
        
        if self._vectors is None:
            self._vectors = vectors
        else:
            self._vectors = np.vstack([self._vectors, vectors])
        
        self._ids.extend(ids)
        self._metadata.extend(metadata)
        
        logger.info(f"Added {len(ids)} documents (total: {len(self._ids)})")
    
    def similarity_search(
        self, 
        query_vector: np.ndarray, 
        k: int = 3,
        filters: Optional[dict] = None
    ) -> List[dict]:
        """Search using cosine similarity."""
        if self._vectors is None or len(self._vectors) == 0:
            return []
        
        query = query_vector.astype(np.float32).flatten()
        
        # Compute cosine similarities
        norms = np.linalg.norm(self._vectors, axis=1) * np.linalg.norm(query)
        norms[norms == 0] = 1  # Avoid division by zero
        similarities = np.dot(self._vectors, query) / norms
        
        # Get top k indices
        top_indices = np.argsort(similarities)[::-1][:k]
        
        results = []
        for idx in top_indices:
            result = {
                'id': self._ids[idx],
                'score': float(similarities[idx]),
                'metadata': self._metadata[idx]
            }
            results.append(result)
        
        return results
    
    def clear(self) -> None:
        """Clear the store."""
        self._vectors = None
        self._ids = []
        self._metadata = []


def create_vector_store(
    method: str = "faiss",
    embedding_dim: int = 384,
    **kwargs
) -> VectorStore:
    """
    Factory function to create vector store.
    
    Args:
        method: "faiss" or "simple"
        embedding_dim: Embedding dimensionality
        **kwargs: Additional arguments
        
    Returns:
        VectorStore instance
    """
    if method == "simple":
        return SimpleVectorStore(embedding_dim)
    else:
        store = FaissVectorStore(embedding_dim, **kwargs)
        if not store.is_available:
            logger.warning("FAISS not available, falling back to SimpleVectorStore")
            return SimpleVectorStore(embedding_dim)
        return store

