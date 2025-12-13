# hienfeld/services/clustering_service.py
"""
Service for clustering similar clauses using the Leader algorithm.

IMPROVED v2.1:
- Uses aggressive text normalization to ignore variable parts (addresses, amounts, dates)
- Two-stage matching: first on normalized text, then on original for verification
- Better clustering of similar clauses with different specific values
"""
from typing import List, Dict, Tuple, Optional, Callable
import re

from ..config import AppConfig
from ..domain.clause import Clause
from ..domain.cluster import Cluster
from .similarity_service import SimilarityService, RapidFuzzSimilarityService
from ..utils.text_normalization import normalize_for_clustering
from ..logging_config import get_logger

logger = get_logger('clustering_service')


class ClusteringService:
    """
    Groups similar clauses using the Leader clustering algorithm.
    
    IMPROVED v2.1: Uses aggressive normalization to cluster similar clauses
    that differ only in variable parts (addresses, amounts, dates).
    
    The Leader algorithm is a single-pass clustering approach:
    1. Sort items by length (longest first)
    2. For each item, find a similar "leader" or become a new leader
    3. Efficient for large datasets with O(n*k) complexity where k is window size
    """
    
    def __init__(
        self,
        config: AppConfig,
        similarity_service: Optional[SimilarityService] = None,
        nlp_service: Optional['NLPService'] = None
    ):
        """
        Initialize the clustering service.

        Args:
            config: Application configuration
            similarity_service: Service for computing text similarity
            nlp_service: Optional NLP service for semantic cluster naming
        """
        self.config = config
        self.nlp_service = nlp_service

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
        
        IMPROVED v2.1: Uses two-stage matching:
        1. First match on normalized text (with placeholders for variables)
        2. Creates better clusters for similar clauses with different addresses/amounts
        
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
        normalized_match_cache: Dict[str, str] = {}  # normalized_text -> cluster_id (NEW!)
        cluster_normalized_texts: Dict[str, str] = {}  # cluster_id -> normalized_text (for leaders)
        
        cluster_counter = 1
        total = len(sorted_clauses)
        window_size = self.config.clustering.leader_window_size
        min_length = self.config.clustering.min_text_length
        threshold = self.config.clustering.similarity_threshold
        length_tolerance = self.config.clustering.length_tolerance
        
        # Lower threshold for normalized text matching (more aggressive clustering)
        normalized_threshold = max(0.80, threshold - 0.05)

        # PRE-COMPUTE: Normalize all texts once (performance optimization)
        # Avoids recomputing normalization N*W times in the matching loop
        normalized_texts = {}
        if self.config.semantic.performance.precompute_normalized_text:
            logger.debug("Pre-computing normalized texts for all clauses...")
            normalized_texts = {
                clause.id: normalize_for_clustering(clause.raw_text)
                for clause in sorted_clauses
            }
            logger.debug(f"Pre-computed {len(normalized_texts)} normalized texts")

        for i, clause in enumerate(sorted_clauses):
            # Progress update - more frequent updates for better UX
            # Update every 50 items OR every 5% of total (whichever is more frequent)
            update_interval = min(50, max(1, total // 20))
            if progress_callback and i % update_interval == 0:
                progress_callback(int(i / total * 100))
            
            text = clause.simplified_text

            # Skip very short texts
            if len(text) < min_length:
                clause_to_cluster[clause.id] = "NVT"
                continue

            # Get normalized version (pre-computed if available, else compute on-demand)
            if normalized_texts:
                normalized_text = normalized_texts.get(clause.id)
            else:
                normalized_text = normalize_for_clustering(clause.raw_text)
            
            # STAGE 1: Check exact match cache (O(1) lookup)
            if text in exact_match_cache:
                cluster_id = exact_match_cache[text]
                clause_to_cluster[clause.id] = cluster_id
                
                # Update cluster frequency
                for cluster in clusters:
                    if cluster.id == cluster_id:
                        cluster.add_member(clause.id)
                        break
                continue
            
            # STAGE 2: Check normalized match cache (catches address/amount variations)
            if normalized_text in normalized_match_cache:
                cluster_id = normalized_match_cache[normalized_text]
                clause_to_cluster[clause.id] = cluster_id
                exact_match_cache[text] = cluster_id  # Also cache exact for future
                
                # Update cluster frequency
                for cluster in clusters:
                    if cluster.id == cluster_id:
                        cluster.add_member(clause.id)
                        break
                continue
            
            # STAGE 3: Fuzzy match against recent leaders
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
                
                # First try: match on original simplified text
                similarity = self.similarity_service.similarity(leader_text, text)

                if similarity >= threshold:
                    found_cluster = cluster
                    break

                # Second try: match on normalized text (catches variable differences)
                # Use pre-computed normalized text if available
                if normalized_texts:
                    leader_normalized = cluster_normalized_texts.get(cluster.id)
                    if not leader_normalized:
                        # Fallback: compute on-demand if not in cache (shouldn't happen)
                        leader_normalized = normalize_for_clustering(cluster.original_text)
                else:
                    leader_normalized = normalize_for_clustering(cluster.original_text)

                normalized_similarity = self.similarity_service.similarity(
                    leader_normalized,
                    normalized_text
                )
                
                if normalized_similarity >= normalized_threshold:
                    logger.debug(
                        f"Matched via normalization: {normalized_similarity:.2f} "
                        f"(original was {similarity:.2f})"
                    )
                    found_cluster = cluster
                    break
            
            if found_cluster:
                # Add to existing cluster
                cluster_id = found_cluster.id
                clause_to_cluster[clause.id] = cluster_id
                exact_match_cache[text] = cluster_id
                normalized_match_cache[normalized_text] = cluster_id
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
                normalized_match_cache[normalized_text] = cluster_id

                # Store normalized text for this cluster leader (performance optimization)
                if normalized_texts and normalized_text:
                    cluster_normalized_texts[cluster_id] = normalized_text

                cluster_counter += 1
        
        # Final progress update
        if progress_callback:
            progress_callback(100)

        logger.info(f"Created {len(clusters)} clusters from {len(clauses)} clauses")

        # POST-PROCESSING: Group singleton clusters (frequency=1) into "Uniek" meta-clusters
        # This will be done AFTER analysis, so we preserve individual analysis but group for display
        # We return the original clusters here, grouping happens in export service

        return clusters, clause_to_cluster
    
    def _generate_cluster_name(self, text: str) -> str:
        """
        Generate a descriptive name for a cluster based on its leader text.

        NEW: Uses NLP noun phrase extraction for semantic names when available.

        Args:
            text: Leader clause text

        Returns:
            Human-readable cluster name (max 50 chars)
        """
        if not text:
            return "Onbekend"

        # Extract clause code if present (keep for prefix)
        code_match = re.search(r'\b[A-Z0-9]{3,4}\b', text)
        code = code_match.group(0) if code_match else ""

        # Step 1: Try NLP noun phrase extraction (NEW)
        if self.nlp_service and self.nlp_service.is_available:
            try:
                noun_phrases = self.nlp_service.extract_key_noun_phrases(text, max_phrases=3)
                if noun_phrases:
                    # Join phrases and capitalize
                    name = " ".join(noun_phrases).title()

                    # Add code prefix if found and not already in name
                    if code and code not in name:
                        name = f"{code} {name}"

                    # Trim if too long
                    if len(name) > 50:
                        name = name[:47] + "..."

                    return name
            except Exception as e:
                logger.debug(f"NLP name generation failed: {e}, falling back to theme matching")

        # Step 2: Fallback to theme keyword matching (existing logic)
        lower_text = text.lower()

        for theme_key, theme_name in self.config.cluster_naming.theme_patterns.items():
            if theme_key in lower_text:
                # Special handling for premie + naverrekening
                if theme_key == 'premie' and 'naverrekening' in lower_text:
                    name = f"{code} Premie Naverrekening".strip()
                else:
                    name = f"{code} {theme_name}".strip()

                # Trim if too long
                if len(name) > 50:
                    name = name[:47] + "..."
                return name

        # Step 3: Final fallback - first N words (without "...")
        words = text.split()
        word_count = self.config.cluster_naming.fallback_word_count

        if len(words) > word_count:
            name = " ".join(words[:word_count])
        else:
            name = text

        # Add code prefix if found
        if code and code not in name:
            name = f"{code} {name}"

        # Trim to 50 chars max
        if len(name) > 50:
            name = name[:50].rsplit(' ', 1)[0]  # Trim at word boundary

        return name
    
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

