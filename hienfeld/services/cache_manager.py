# hienfeld/services/cache_manager.py
"""
Unified CacheManager for all caching layers.

Consolidates 7 different caching implementations:
1. ServiceCache (singleton instances)
2. PolicyEmbeddingsCache (embeddings)
3. NLPService.lemmatize_cached (@lru_cache)
4. SynonymService.get_synonyms (@lru_cache)
5. DocumentSimilarityService TF-IDF state
6. HybridSimilarityService FAISS/BM25 indexes
7. ClusteringService local dicts (transient)

Provides:
- Unified clear_all() method
- Consolidated statistics
- Grouped invalidation (by type)
- Thread-safe operations
"""
from typing import Dict, List, Optional, Callable
import threading
from dataclasses import dataclass, field
from datetime import datetime

from ..logging_config import get_logger

logger = get_logger('cache_manager')


@dataclass
class CacheStatistics:
    """Statistics for a single cache."""
    name: str
    type: str
    size: int = 0
    hit_count: int = 0
    miss_count: int = 0
    hit_rate: float = 0.0
    memory_bytes: int = 0
    last_cleared: Optional[datetime] = None
    metadata: Dict[str, any] = field(default_factory=dict)


class CacheManager:
    """
    Centralized cache management for all caching layers.
    
    Responsibilities:
    - Register caches from services
    - Unified clear/invalidate operations
    - Consolidated statistics
    - Thread-safe access
    
    Usage:
        manager = CacheManager()
        manager.register_cache('service_cache', clear_fn=ServiceCache.get_instance().clear)
        manager.clear_all()  # Clears all registered caches
    """
    
    # Singleton instance
    _instance: Optional['CacheManager'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize cache manager."""
        self._caches: Dict[str, Callable[[], None]] = {}
        self._stats_providers: Dict[str, Callable[[], CacheStatistics]] = {}
        self._cache_lock = threading.Lock()
        self._last_clear_time: Optional[datetime] = None
    
    @classmethod
    def get_instance(cls) -> 'CacheManager':
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = CacheManager()
        return cls._instance
    
    def register_cache(
        self,
        name: str,
        clear_fn: Callable[[], None],
        stats_fn: Optional[Callable[[], CacheStatistics]] = None
    ) -> None:
        """
        Register a cache with the manager.
        
        Args:
            name: Unique cache identifier
            clear_fn: Function to call to clear the cache
            stats_fn: Optional function to get cache statistics
        """
        with self._cache_lock:
            self._caches[name] = clear_fn
            if stats_fn:
                self._stats_providers[name] = stats_fn
            logger.debug(f"Registered cache: {name}")
    
    def clear_all(self) -> Dict[str, str]:
        """
        Clear all registered caches.
        
        Returns:
            Dict mapping cache name to status (success/error)
        """
        results = {}
        
        with self._cache_lock:
            logger.info(f"Clearing all caches ({len(self._caches)} registered)")
            
            for name, clear_fn in self._caches.items():
                try:
                    clear_fn()
                    results[name] = "cleared"
                    logger.info(f"[OK] Cleared cache: {name}")
                except Exception as e:
                    results[name] = f"error: {str(e)}"
                    logger.error(f"[ERROR] Failed to clear {name}: {e}")
            
            self._last_clear_time = datetime.now()
        
        return results
    
    def clear_by_type(self, cache_type: str) -> Dict[str, str]:
        """
        Clear all caches of a specific type.
        
        Args:
            cache_type: Type identifier (e.g., 'singleton', 'lru_cache', 'index')
        
        Returns:
            Dict mapping cache name to status
        """
        results = {}
        
        # Type mapping based on naming conventions
        type_patterns = {
            'singleton': ['service_cache', 'policy_embeddings'],
            'lru': ['nlp', 'synonym'],
            'index': ['faiss', 'bm25', 'tfidf'],
            'embeddings': ['policy_embeddings', 'faiss']
        }
        
        pattern = type_patterns.get(cache_type, [cache_type])
        
        with self._cache_lock:
            for name, clear_fn in self._caches.items():
                if any(p in name.lower() for p in pattern):
                    try:
                        clear_fn()
                        results[name] = "cleared"
                        logger.info(f"[OK] Cleared {cache_type} cache: {name}")
                    except Exception as e:
                        results[name] = f"error: {str(e)}"
                        logger.error(f"[ERROR] Failed to clear {name}: {e}")
        
        return results
    
    def get_statistics(self) -> Dict[str, CacheStatistics]:
        """
        Get statistics for all registered caches.
        
        Returns:
            Dict mapping cache name to CacheStatistics
        """
        stats = {}
        
        with self._cache_lock:
            for name, stats_fn in self._stats_providers.items():
                try:
                    stats[name] = stats_fn()
                except Exception as e:
                    logger.error(f"Failed to get stats for {name}: {e}")
                    stats[name] = CacheStatistics(
                        name=name,
                        type="unknown",
                        metadata={"error": str(e)}
                    )
        
        return stats
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get summary of all cache statistics.
        
        Returns:
            Summary dict with aggregate statistics
        """
        stats = self.get_statistics()
        
        total_size = sum(s.size for s in stats.values())
        total_hits = sum(s.hit_count for s in stats.values())
        total_misses = sum(s.miss_count for s in stats.values())
        total_memory = sum(s.memory_bytes for s in stats.values())
        
        overall_hit_rate = 0.0
        if (total_hits + total_misses) > 0:
            overall_hit_rate = total_hits / (total_hits + total_misses)
        
        return {
            "total_caches": len(self._caches),
            "total_size": total_size,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": round(overall_hit_rate, 3),
            "total_memory_mb": round(total_memory / (1024 * 1024), 2),
            "last_clear_time": self._last_clear_time.isoformat() if self._last_clear_time else None,
            "registered_caches": list(self._caches.keys())
        }


# Convenience functions for common operations

def clear_all_caches() -> Dict[str, str]:
    """Clear all caches (convenience function)."""
    return CacheManager.get_instance().clear_all()


def get_cache_statistics() -> Dict[str, CacheStatistics]:
    """Get all cache statistics (convenience function)."""
    return CacheManager.get_instance().get_statistics()


def get_cache_summary() -> Dict[str, any]:
    """Get cache summary (convenience function)."""
    return CacheManager.get_instance().get_summary()
