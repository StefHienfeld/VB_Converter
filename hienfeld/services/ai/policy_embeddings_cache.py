# hienfeld/services/ai/policy_embeddings_cache.py
"""
Cache for pre-computed policy document embeddings.

This cache stores embeddings for policy documents to avoid recomputing
them on every analysis run. This can save 20-30+ seconds per analysis.

Architecture:
- Cache key: SHA256 hash of document content (bytes)
- Cache value: Dict with embeddings array, section IDs, metadata
- Storage: In-memory with optional persistence to disk (pickle)
- Invalidation: Automatic based on content hash
"""

from __future__ import annotations

import hashlib
import pickle
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np

from ...logging_config import get_logger

if TYPE_CHECKING:
    from ...domain.policy_document import PolicyDocumentSection

logger = get_logger('policy_embeddings_cache')

# Default cache directory
DEFAULT_CACHE_DIR = Path.home() / ".hienfeld_cache" / "policy_embeddings"


@dataclass
class CachedEmbeddings:
    """
    Cached embeddings for a policy document.

    Attributes:
        content_hash: SHA256 hash of the document content
        embeddings: NumPy array of embeddings (shape: n_sections x embedding_dim)
        section_ids: List of section IDs in embedding order
        metadata: List of section metadata dicts in embedding order
        embedding_model: Name of the embedding model used
        created_at: When this cache entry was created
        access_count: Number of times this entry was accessed
    """
    content_hash: str
    embeddings: np.ndarray
    section_ids: List[str]
    metadata: List[Dict[str, Any]]
    embedding_model: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0

    @property
    def num_sections(self) -> int:
        """Number of sections in this cache entry."""
        return len(self.section_ids)

    @property
    def embedding_dim(self) -> int:
        """Embedding dimensionality."""
        return self.embeddings.shape[1] if self.embeddings.ndim == 2 else 0


class PolicyEmbeddingsCache:
    """
    Thread-safe cache for policy document embeddings.

    Features:
    - Content-based hashing for automatic invalidation
    - In-memory storage for fast access
    - Optional disk persistence (pickle)
    - Statistics tracking

    Usage:
        cache = PolicyEmbeddingsCache()

        # Check if embeddings are cached
        cache_key = cache.compute_cache_key(file_bytes, filename)
        cached = cache.get(cache_key, model_name="paraphrase-multilingual-MiniLM-L12-v2")

        if cached:
            # Use cached embeddings
            embeddings = cached.embeddings
        else:
            # Compute embeddings and cache
            embeddings = embeddings_service.embed_texts(texts)
            cache.put(cache_key, embeddings, section_ids, metadata, model_name)
    """

    _instance: Optional['PolicyEmbeddingsCache'] = None
    _lock = threading.Lock()

    def __init__(
        self,
        persist_to_disk: bool = False,
        cache_dir: Optional[Path] = None,
        max_entries: int = 50
    ):
        """
        Initialize the policy embeddings cache.

        Args:
            persist_to_disk: Whether to save cache to disk
            cache_dir: Directory for disk cache (default: ~/.hienfeld_cache/policy_embeddings)
            max_entries: Maximum number of cached documents (LRU eviction)
        """
        self._cache: Dict[str, CachedEmbeddings] = {}
        self._cache_lock = threading.Lock()
        self._persist_to_disk = persist_to_disk
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._max_entries = max_entries

        # Statistics
        self._hits = 0
        self._misses = 0
        self._total_time_saved_ms = 0.0

        # Load existing cache from disk
        if self._persist_to_disk:
            self._ensure_cache_dir()
            self._load_from_disk()

        logger.info(
            f"PolicyEmbeddingsCache initialized (max_entries={max_entries}, "
            f"persist={persist_to_disk})"
        )

    @classmethod
    def get_instance(
        cls,
        persist_to_disk: bool = False,
        cache_dir: Optional[Path] = None
    ) -> 'PolicyEmbeddingsCache':
        """
        Get singleton instance of the cache.

        Args:
            persist_to_disk: Enable disk persistence
            cache_dir: Directory for disk cache

        Returns:
            PolicyEmbeddingsCache singleton
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = PolicyEmbeddingsCache(
                        persist_to_disk=persist_to_disk,
                        cache_dir=cache_dir
                    )
        return cls._instance

    def compute_cache_key(
        self,
        file_bytes: bytes,
        filename: str
    ) -> str:
        """
        Compute a unique cache key for a document.

        Uses SHA256 hash of content + filename for uniqueness.

        Args:
            file_bytes: Raw file bytes
            filename: Original filename

        Returns:
            SHA256 hash string
        """
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        hasher.update(filename.encode('utf-8'))
        return hasher.hexdigest()

    def compute_sections_key(
        self,
        sections: List['PolicyDocumentSection']
    ) -> str:
        """
        Compute a cache key from parsed sections.

        Useful when you have already parsed sections but want to check
        if embeddings are cached.

        Args:
            sections: List of parsed policy sections

        Returns:
            SHA256 hash string
        """
        hasher = hashlib.sha256()

        for section in sections:
            # Hash section content
            hasher.update((section.simplified_text or "").encode('utf-8'))
            hasher.update((section.id or "").encode('utf-8'))
            hasher.update((section.document_id or "").encode('utf-8'))

        return hasher.hexdigest()

    def get(
        self,
        cache_key: str,
        embedding_model: str
    ) -> Optional[CachedEmbeddings]:
        """
        Retrieve cached embeddings.

        Args:
            cache_key: Cache key (from compute_cache_key)
            embedding_model: Model name (must match cached model)

        Returns:
            CachedEmbeddings if found and valid, None otherwise
        """
        with self._cache_lock:
            # Build full cache key including model
            full_key = f"{cache_key}_{embedding_model}"

            cached = self._cache.get(full_key)

            if cached is None:
                self._misses += 1
                logger.debug(f"Cache MISS: {full_key[:16]}...")
                return None

            # Verify model matches
            if cached.embedding_model != embedding_model:
                self._misses += 1
                logger.debug(
                    f"Cache MISS (model mismatch): cached={cached.embedding_model}, "
                    f"requested={embedding_model}"
                )
                return None

            # Update access stats
            cached.access_count += 1
            self._hits += 1

            # Estimate time saved (rough: ~5ms per section for embedding)
            time_saved_ms = cached.num_sections * 5
            self._total_time_saved_ms += time_saved_ms

            logger.info(
                f"Cache HIT: {full_key[:16]}... "
                f"({cached.num_sections} sections, ~{time_saved_ms}ms saved)"
            )

            return cached

    def put(
        self,
        cache_key: str,
        embeddings: np.ndarray,
        section_ids: List[str],
        metadata: List[Dict[str, Any]],
        embedding_model: str
    ) -> None:
        """
        Store embeddings in cache.

        Args:
            cache_key: Cache key (from compute_cache_key)
            embeddings: NumPy array of embeddings
            section_ids: Section IDs in embedding order
            metadata: Section metadata in embedding order
            embedding_model: Name of embedding model used
        """
        with self._cache_lock:
            full_key = f"{cache_key}_{embedding_model}"

            # LRU eviction if cache is full
            if len(self._cache) >= self._max_entries:
                self._evict_lru()

            self._cache[full_key] = CachedEmbeddings(
                content_hash=cache_key,
                embeddings=embeddings.copy(),  # Copy to prevent mutation
                section_ids=section_ids.copy(),
                metadata=[m.copy() for m in metadata],
                embedding_model=embedding_model,
            )

            logger.info(
                f"Cache STORE: {full_key[:16]}... "
                f"({len(section_ids)} sections, dim={embeddings.shape[1]})"
            )

            # Persist to disk if enabled
            if self._persist_to_disk:
                self._save_entry_to_disk(full_key)

    def invalidate(self, cache_key: str, embedding_model: str = None) -> bool:
        """
        Invalidate a cache entry.

        Args:
            cache_key: Cache key to invalidate
            embedding_model: If provided, only invalidate for this model

        Returns:
            True if entry was removed, False if not found
        """
        with self._cache_lock:
            removed = False

            if embedding_model:
                full_key = f"{cache_key}_{embedding_model}"
                if full_key in self._cache:
                    del self._cache[full_key]
                    removed = True
                    if self._persist_to_disk:
                        self._remove_from_disk(full_key)
            else:
                # Remove all entries matching this cache key
                keys_to_remove = [
                    k for k in self._cache.keys()
                    if k.startswith(cache_key)
                ]
                for k in keys_to_remove:
                    del self._cache[k]
                    if self._persist_to_disk:
                        self._remove_from_disk(k)
                removed = len(keys_to_remove) > 0

            if removed:
                logger.info(f"Cache INVALIDATE: {cache_key[:16]}...")

            return removed

    def clear(self) -> int:
        """
        Clear entire cache.

        Returns:
            Number of entries removed
        """
        with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()

            # Clear disk cache
            if self._persist_to_disk:
                self._clear_disk_cache()

            logger.info(f"Cache CLEAR: {count} entries removed")
            return count

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._cache_lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            # Calculate total cached sections
            total_sections = sum(c.num_sections for c in self._cache.values())

            # Calculate total memory usage (rough estimate)
            total_memory_mb = sum(
                c.embeddings.nbytes / (1024 * 1024)
                for c in self._cache.values()
            )

            return {
                'entries': len(self._cache),
                'max_entries': self._max_entries,
                'total_sections': total_sections,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(hit_rate, 3),
                'total_time_saved_ms': round(self._total_time_saved_ms, 1),
                'total_time_saved_sec': round(self._total_time_saved_ms / 1000, 1),
                'memory_usage_mb': round(total_memory_mb, 2),
                'persist_to_disk': self._persist_to_disk,
            }

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return

        # Find entry with oldest access (or lowest access count if same time)
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (
                self._cache[k].access_count,
                self._cache[k].created_at
            )
        )

        del self._cache[lru_key]

        if self._persist_to_disk:
            self._remove_from_disk(lru_key)

        logger.debug(f"LRU eviction: {lru_key[:16]}...")

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """Get path for a cache entry."""
        # Use first 64 chars of key as filename (safe for filesystem)
        safe_key = key[:64].replace("/", "_").replace("\\", "_")
        return self._cache_dir / f"{safe_key}.pkl"

    def _save_entry_to_disk(self, key: str) -> None:
        """Save a single cache entry to disk."""
        try:
            cache_path = self._get_cache_path(key)
            with open(cache_path, 'wb') as f:
                pickle.dump(self._cache[key], f)
            logger.debug(f"Saved to disk: {key[:16]}...")
        except Exception as e:
            logger.warning(f"Failed to save cache entry to disk: {e}")

    def _remove_from_disk(self, key: str) -> None:
        """Remove a cache entry from disk."""
        try:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                cache_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove cache entry from disk: {e}")

    def _clear_disk_cache(self) -> None:
        """Clear all disk cache entries."""
        try:
            for path in self._cache_dir.glob("*.pkl"):
                path.unlink()
        except Exception as e:
            logger.warning(f"Failed to clear disk cache: {e}")

    def _load_from_disk(self) -> None:
        """Load cache entries from disk."""
        try:
            loaded = 0
            for path in self._cache_dir.glob("*.pkl"):
                try:
                    with open(path, 'rb') as f:
                        entry = pickle.load(f)

                    # Reconstruct key from entry
                    key = f"{entry.content_hash}_{entry.embedding_model}"
                    self._cache[key] = entry
                    loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to load cache entry {path}: {e}")

            if loaded > 0:
                logger.info(f"Loaded {loaded} cache entries from disk")
        except Exception as e:
            logger.warning(f"Failed to load cache from disk: {e}")


# Global singleton accessor
def get_policy_embeddings_cache(
    persist_to_disk: bool = False
) -> PolicyEmbeddingsCache:
    """
    Get the global policy embeddings cache instance.

    Args:
        persist_to_disk: Enable disk persistence (only on first call)

    Returns:
        PolicyEmbeddingsCache singleton
    """
    return PolicyEmbeddingsCache.get_instance(persist_to_disk=persist_to_disk)
