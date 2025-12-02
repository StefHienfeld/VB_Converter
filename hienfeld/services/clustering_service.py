# hienfeld/services/clustering_service.py
"""
Service for clustering similar clauses using the Leader algorithm.
"""
from typing import List, Dict, Tuple, Optional, Callable
import re

from ..config import AppConfig
from ..domain.clause import Clause
from ..domain.cluster import Cluster
from .similarity_service import SimilarityService, RapidFuzzSimilarityService
from ..logging_config import get_logger

logger = get_logger('clustering_service')


class ClusteringService:
    """
    Groups similar clauses using the Leader clustering algorithm.
    
    The Leader algorithm is a single-pass clustering approach:
    1. Sort items by length (longest first)
    2. For each item, find a similar "leader" or become a new leader
    3. Efficient for large datasets with O(n*k) complexity where k is window size
    """
    
    def __init__(
        self, 
        config: AppConfig, 
        similarity_service: Optional[SimilarityService] = None
    ):
        """
        Initialize the clustering service.
        
        Args:
            config: Application configuration
            similarity_service: Service for computing text similarity
        """
        self.config = config
        
        # Use provided similarity service or create default
        if similarity_service is None:
            self.similarity_service = RapidFuzzSimilarityService(
                threshold=config.clustering.similarity_threshold
            )
        else:
            self.similarity_service = similarity_service
    
    def cluster_clauses(
        self, 
        clauses: List[Clause],
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[List[Cluster], Dict[str, str]]:
        """
        Cluster clauses using the Leader algorithm.
        
        Args:
            clauses: List of Clause objects to cluster
            progress_callback: Optional callback for progress updates (0-100)
            
        Returns:
            Tuple of:
            - List of Cluster objects
            - Dictionary mapping clause_id -> cluster_id
        """
        logger.info(f"Starting clustering of {len(clauses)} clauses")
        
        # Sort by length (descending) - longer texts become leaders first
        sorted_clauses = sorted(
            clauses,
            key=lambda c: len(c.simplified_text),
            reverse=True
        )
        
        clusters: List[Cluster] = []
        clause_to_cluster: Dict[str, str] = {}
        exact_match_cache: Dict[str, str] = {}  # simplified_text -> cluster_id
        
        cluster_counter = 1
        total = len(sorted_clauses)
        window_size = self.config.clustering.leader_window_size
        min_length = self.config.clustering.min_text_length
        threshold = self.config.clustering.similarity_threshold
        length_tolerance = self.config.clustering.length_tolerance
        
        for i, clause in enumerate(sorted_clauses):
            # Progress update
            if progress_callback and i % 500 == 0:
                progress_callback(int(i / total * 100))
            
            text = clause.simplified_text
            
            # Skip very short texts
            if len(text) < min_length:
                clause_to_cluster[clause.id] = "NVT"
                continue
            
            # Check exact match cache first (O(1) lookup)
            if text in exact_match_cache:
                cluster_id = exact_match_cache[text]
                clause_to_cluster[clause.id] = cluster_id
                
                # Update cluster frequency
                for cluster in clusters:
                    if cluster.id == cluster_id:
                        cluster.add_member(clause.id)
                        break
                continue
            
            # Fuzzy match against recent leaders
            found_cluster = None
            
            # Look back at recent clusters (window)
            search_window = clusters[-window_size:] if len(clusters) > window_size else clusters
            
            for cluster in search_window:
                leader_text = cluster.leader_text
                
                # Quick length filter (skip if too different)
                if leader_text:
                    len_diff = abs(len(leader_text) - len(text)) / max(len(leader_text), 1)
                    if len_diff > length_tolerance:
                        continue
                
                # Compute similarity
                similarity = self.similarity_service.similarity(leader_text, text)
                
                if similarity >= threshold:
                    found_cluster = cluster
                    break
            
            if found_cluster:
                # Add to existing cluster
                cluster_id = found_cluster.id
                clause_to_cluster[clause.id] = cluster_id
                exact_match_cache[text] = cluster_id
                found_cluster.add_member(clause.id)
            else:
                # Create new cluster
                cluster_id = f"CL-{cluster_counter:04d}"
                cluster_name = self._generate_cluster_name(clause.raw_text)
                
                new_cluster = Cluster(
                    id=cluster_id,
                    leader_clause=clause,
                    member_ids=[],
                    frequency=1,
                    name=cluster_name
                )
                
                clusters.append(new_cluster)
                clause_to_cluster[clause.id] = cluster_id
                exact_match_cache[text] = cluster_id
                cluster_counter += 1
        
        # Final progress update
        if progress_callback:
            progress_callback(100)
        
        logger.info(f"Created {len(clusters)} clusters from {len(clauses)} clauses")
        
        return clusters, clause_to_cluster
    
    def _generate_cluster_name(self, text: str) -> str:
        """
        Generate a descriptive name for a cluster based on its leader text.
        
        Args:
            text: Leader clause text
            
        Returns:
            Human-readable cluster name
        """
        if not text:
            return "Onbekend"
        
        # Extract clause code if present
        code_match = re.search(r'\b[A-Z0-9]{3,4}\b', text)
        code = code_match.group(0) if code_match else ""
        
        lower_text = text.lower()
        
        # Check known themes from config
        for theme_key, theme_name in self.config.cluster_naming.theme_patterns.items():
            if theme_key in lower_text:
                # Special handling for premie + naverrekening
                if theme_key == 'premie' and 'naverrekening' in lower_text:
                    return f"{code} Premie Naverrekening".strip()
                return f"{code} {theme_name}".strip()
        
        # Fallback: first N words
        words = text.split()
        word_count = self.config.cluster_naming.fallback_word_count
        if len(words) > word_count:
            return " ".join(words[:word_count]) + "..."
        return text[:50] + "..." if len(text) > 50 else text
    
    def update_similarity_threshold(self, threshold: float) -> None:
        """
        Update the similarity threshold.
        
        Args:
            threshold: New threshold (0.0 to 1.0)
        """
        if hasattr(self.similarity_service, 'threshold'):
            self.similarity_service.threshold = threshold
        self.config.clustering.similarity_threshold = threshold
        logger.info(f"Updated similarity threshold to {threshold}")
    
    def get_cluster_statistics(self, clusters: List[Cluster]) -> dict:
        """
        Compute statistics about the clustering results.
        
        Args:
            clusters: List of clusters
            
        Returns:
            Dictionary with statistics
        """
        if not clusters:
            return {
                'total_clusters': 0,
                'total_clauses': 0,
                'avg_frequency': 0,
                'max_frequency': 0,
                'singletons': 0
            }
        
        frequencies = [c.frequency for c in clusters]
        
        return {
            'total_clusters': len(clusters),
            'total_clauses': sum(frequencies),
            'avg_frequency': sum(frequencies) / len(frequencies),
            'max_frequency': max(frequencies),
            'singletons': sum(1 for f in frequencies if f == 1)
        }

