# hienfeld/services/hybrid_similarity_service.py
"""
Hybrid similarity service combining multiple matching techniques.

Combines:
1. RapidFuzz (exact/fuzzy string matching)
2. Lemmatized matching (normalized word forms)
3. TF-IDF (keyword importance)
4. Synonym matching (domain-specific)
5. Sentence embeddings (semantic meaning)

Each method contributes to a weighted final score.
No external APIs required - runs entirely locally.
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import time

from ..config import AppConfig, SemanticConfig
from ..logging_config import get_logger
from .similarity_service import RapidFuzzSimilarityService, SemanticSimilarityService
from .nlp_service import NLPService
from .synonym_service import SynonymService
from .document_similarity_service import DocumentSimilarityService

logger = get_logger('hybrid_similarity_service')


@dataclass
class SimilarityBreakdown:
    """Detailed breakdown of similarity scores from each method."""
    rapidfuzz: float = 0.0
    lemmatized: float = 0.0
    tfidf: float = 0.0
    synonyms: float = 0.0
    embeddings: float = 0.0
    final_score: float = 0.0

    # Metadata
    methods_used: List[str] = field(default_factory=list)
    computation_time_ms: float = 0.0


@dataclass
class PerformanceStats:
    """Performance statistics for hybrid similarity service."""
    total_find_best_calls: int = 0
    total_candidates_screened: int = 0
    total_full_hybrid_calls: int = 0
    pre_screen_filtered_count: int = 0
    avg_candidates_per_call: float = 0.0

    def log_summary(self):
        """Log performance summary."""
        if self.total_find_best_calls > 0:
            savings = (1 - self.total_full_hybrid_calls / max(1, self.total_candidates_screened)) * 100
            logger.info(
                f"🚀 Performance: {self.total_find_best_calls} calls, "
                f"{self.total_candidates_screened} candidates screened, "
                f"{self.total_full_hybrid_calls} full hybrid ({savings:.1f}% saved)"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            'rapidfuzz': round(self.rapidfuzz, 3),
            'lemmatized': round(self.lemmatized, 3),
            'tfidf': round(self.tfidf, 3),
            'synonyms': round(self.synonyms, 3),
            'embeddings': round(self.embeddings, 3),
            'final_score': round(self.final_score, 3),
            'methods_used': self.methods_used,
            'computation_time_ms': round(self.computation_time_ms, 2)
        }


class HybridSimilarityService:
    """
    Multi-method similarity service for robust text matching.
    
    Combines multiple similarity techniques with configurable weights:
    - RapidFuzz: Fast fuzzy string matching (character-level)
    - Lemmatized: Matching after normalizing word forms
    - TF-IDF: Keyword-based document similarity
    - Synonyms: Domain-specific term matching
    - Embeddings: Deep semantic similarity
    
    The final score is a weighted average of all available methods.
    """
    
    def __init__(
        self,
        config: AppConfig,
        rapidfuzz_service: Optional[RapidFuzzSimilarityService] = None,
        nlp_service: Optional[NLPService] = None,
        synonym_service: Optional[SynonymService] = None,
        tfidf_service: Optional[DocumentSimilarityService] = None,
        semantic_service: Optional[SemanticSimilarityService] = None
    ):
        """
        Initialize the hybrid similarity service.
        
        Args:
            config: Application configuration
            rapidfuzz_service: Optional pre-configured RapidFuzz service
            nlp_service: Optional pre-configured NLP service
            synonym_service: Optional pre-configured Synonym service
            tfidf_service: Optional pre-configured TF-IDF service
            semantic_service: Optional pre-configured Semantic service
        """
        self.config = config
        self._semantic_config = config.semantic
        
        # Initialize or use provided services
        self._rapidfuzz = rapidfuzz_service or RapidFuzzSimilarityService()
        self._nlp = nlp_service
        self._synonyms = synonym_service
        self._tfidf = tfidf_service
        self._semantic = semantic_service
        
        # Lazy initialization flags
        self._services_initialized = False

        # Statistics
        self._call_count = 0
        self._total_time_ms = 0.0

        # Performance tracking (v3.3)
        self._perf_stats = PerformanceStats()
    
    def _ensure_services_initialized(self) -> None:
        """Lazy initialize services that weren't provided."""
        if self._services_initialized:
            return
        
        # Initialize NLP service if not provided
        if self._nlp is None and self._semantic_config.enable_nlp:
            try:
                self._nlp = NLPService(self.config)
            except Exception as e:
                logger.warning(f"Could not initialize NLP service: {e}")
        
        # Initialize synonym service if not provided
        if self._synonyms is None and self._semantic_config.enable_synonyms:
            try:
                self._synonyms = SynonymService(self.config)
            except Exception as e:
                logger.warning(f"Could not initialize Synonym service: {e}")
        
        # Initialize TF-IDF service if not provided
        if self._tfidf is None and self._semantic_config.enable_tfidf:
            try:
                self._tfidf = DocumentSimilarityService(self.config)
            except Exception as e:
                logger.warning(f"Could not initialize TF-IDF service: {e}")
        
        # Initialize semantic service if not provided
        if self._semantic is None and self._semantic_config.enable_embeddings:
            try:
                self._semantic = SemanticSimilarityService(
                    model_name=self._semantic_config.embedding_model
                )
            except Exception as e:
                logger.warning(f"Could not initialize Semantic service: {e}")
        
        self._services_initialized = True
        
        # Log which services are available
        available = []
        if self._rapidfuzz:
            available.append("RapidFuzz")
        if self._nlp and self._nlp.is_available:
            available.append("NLP/Lemma")
        if self._synonyms and self._synonyms.is_available:
            available.append("Synonyms")
        if self._tfidf and self._tfidf.is_available:
            available.append("TF-IDF")
        if self._semantic and self._semantic.is_available:
            available.append("Embeddings")
        
        if len(available) == 1 and "RapidFuzz" in available:
            logger.warning(
                "⚠️ Only RapidFuzz available - semantic enhancements disabled. "
                "Install dependencies for better matching: pip install spacy gensim"
            )
        
        logger.info(f"Hybrid similarity services available: {', '.join(available)}")
    
    def train_tfidf(self, documents: List[str]) -> None:
        """
        Train the TF-IDF model on a corpus.
        
        Call this with the policy conditions/voorwaarden before analysis.
        
        Args:
            documents: List of document texts to train on
        """
        self._ensure_services_initialized()
        
        if self._tfidf and self._tfidf.is_available:
            self._tfidf.train_on_corpus(documents)
            logger.info(f"TF-IDF trained on {len(documents)} documents")
    
    def similarity(self, text_a: str, text_b: str, detailed: bool = False) -> float:
        """
        Compute hybrid similarity between two texts.

        Performance optimization: When detailed=False (default), computes only
        essential scores for 5-10x speedup. When detailed=True, provides full
        breakdown via similarity_detailed().

        Args:
            text_a: First text
            text_b: Second text
            detailed: If True, compute full breakdown (slower)

        Returns:
            Weighted similarity score between 0.0 and 1.0
        """
        if detailed:
            breakdown = self.similarity_detailed(text_a, text_b)
            return breakdown.final_score

        # FAST PATH: Compute only essential scores
        self._ensure_services_initialized()

        if not text_a or not text_b:
            return 0.0

        # Get active mode config
        mode_config = self._semantic_config.get_active_config()

        # 1. RapidFuzz (always computed, very fast)
        rapidfuzz_score = self._rapidfuzz.similarity(text_a, text_b)

        # OPTIMIZATION: Early exit on very low scores (clearly not similar)
        if rapidfuzz_score < 0.50:
            logger.debug(f"Early exit: RapidFuzz too low ({rapidfuzz_score:.2f})")
            return rapidfuzz_score * mode_config.weight_rapidfuzz

        # OPTIMIZATION: Early exit if RapidFuzz score is high enough (clearly similar)
        if rapidfuzz_score >= mode_config.skip_embeddings_threshold:
            logger.debug(f"Early exit: RapidFuzz high enough ({rapidfuzz_score:.2f})")
            return rapidfuzz_score

        # Collect scores and weights for enabled methods
        scores = {'rapidfuzz': rapidfuzz_score}
        weights = {'rapidfuzz': mode_config.weight_rapidfuzz}

        # 2. Lemmatized (if enabled and available)
        if mode_config.enable_nlp and self._nlp and self._nlp.is_available:
            try:
                lemma_a = self._nlp.lemmatize_cached(text_a)
                lemma_b = self._nlp.lemmatize_cached(text_b)
                scores['lemmatized'] = self._rapidfuzz.similarity(lemma_a, lemma_b)
                weights['lemmatized'] = mode_config.weight_lemmatized
            except Exception:
                pass

        # OPTIMIZATION: Cascading confidence check after cheap methods
        # If we have RapidFuzz + Lemma and score is already very high, skip expensive methods
        if 'lemmatized' in scores and 'rapidfuzz' in scores:
            current_weights = sum(weights.values())
            current_score = sum(scores[k] * weights[k] for k in scores) / current_weights

            # If already scoring very high (>0.90) with cheap methods, skip embeddings
            if current_score >= 0.90:
                logger.debug(f"Cascading exit: score already high ({current_score:.2f})")
                return current_score

            # If score is very low even with both methods, can't possibly reach threshold
            remaining_weight = 1.0 - current_weights
            max_possible = current_score * current_weights + remaining_weight  # Max if rest = 1.0

            if max_possible < 0.70:  # Can't reach useful threshold
                logger.debug(f"Cascading exit: max possible too low ({max_possible:.2f})")
                return current_score

        # 3. TF-IDF (if enabled and trained)
        if mode_config.enable_tfidf and self._tfidf and self._tfidf.is_trained:
            try:
                scores['tfidf'] = self._tfidf.similarity(text_a, text_b)
                weights['tfidf'] = mode_config.weight_tfidf
            except Exception:
                pass

        # 4. Synonyms (if enabled and available)
        if mode_config.enable_synonyms and self._synonyms and self._synonyms.is_available:
            try:
                scores['synonyms'] = self._synonyms.synonym_similarity(text_a, text_b)
                weights['synonyms'] = mode_config.weight_synonyms
            except Exception:
                pass

        # 5. Embeddings (if enabled, available, and not skipped)
        if (mode_config.enable_embeddings and
            self._semantic and self._semantic.is_available and
            rapidfuzz_score < mode_config.skip_embeddings_threshold):
            try:
                scores['embeddings'] = self._semantic.similarity(text_a, text_b)
                weights['embeddings'] = mode_config.weight_embeddings
            except Exception:
                pass

        # Calculate weighted average
        total_weight = sum(weights.values())
        if total_weight > 0:
            weighted_sum = sum(scores[k] * weights[k] for k in scores)
            return weighted_sum / total_weight

        # Fallback to RapidFuzz if no weights available
        return rapidfuzz_score
    
    def similarity_detailed(self, text_a: str, text_b: str) -> SimilarityBreakdown:
        """
        Compute hybrid similarity with detailed breakdown.
        
        CRITICAL FIX: Dynamic weight redistribution to prevent score dilution
        when semantic services are unavailable.
        
        Args:
            text_a: First text
            text_b: Second text
            
        Returns:
            SimilarityBreakdown with scores from each method
        """
        start_time = time.time()
        self._ensure_services_initialized()
        
        breakdown = SimilarityBreakdown()
        weights = {}
        scores = {}
        
        if not text_a or not text_b:
            return breakdown
        
        # 1. RapidFuzz (always available)
        breakdown.rapidfuzz = self._rapidfuzz.similarity(text_a, text_b)
        scores['rapidfuzz'] = breakdown.rapidfuzz
        weights['rapidfuzz'] = self._semantic_config.weight_rapidfuzz
        breakdown.methods_used.append('rapidfuzz')
        
        # 2. Lemmatized matching
        if self._nlp and self._nlp.is_available:
            try:
                lemma_a = self._nlp.lemmatize_cached(text_a)
                lemma_b = self._nlp.lemmatize_cached(text_b)
                breakdown.lemmatized = self._rapidfuzz.similarity(lemma_a, lemma_b)
                scores['lemmatized'] = breakdown.lemmatized
                weights['lemmatized'] = self._semantic_config.weight_lemmatized
                breakdown.methods_used.append('lemmatized')
            except Exception as e:
                logger.debug(f"Lemmatization failed: {e}")
        
        # 3. TF-IDF (if trained)
        if self._tfidf and self._tfidf.is_trained:
            try:
                breakdown.tfidf = self._tfidf.similarity(text_a, text_b)
                scores['tfidf'] = breakdown.tfidf
                weights['tfidf'] = self._semantic_config.weight_tfidf
                breakdown.methods_used.append('tfidf')
            except Exception as e:
                logger.debug(f"TF-IDF failed: {e}")
        
        # 4. Synonym matching
        if self._synonyms and self._synonyms.is_available:
            try:
                breakdown.synonyms = self._synonyms.synonym_similarity(text_a, text_b)
                scores['synonyms'] = breakdown.synonyms
                weights['synonyms'] = self._semantic_config.weight_synonyms
                breakdown.methods_used.append('synonyms')
            except Exception as e:
                logger.debug(f"Synonym matching failed: {e}")
        
        # 5. Semantic embeddings (slower - skip if RapidFuzz already high)
        if self._semantic and self._semantic.is_available:
            # Optimization: skip embeddings if fuzzy match is already very high
            if breakdown.rapidfuzz < 0.90:
                try:
                    breakdown.embeddings = self._semantic.similarity(text_a, text_b)
                    scores['embeddings'] = breakdown.embeddings
                    weights['embeddings'] = self._semantic_config.weight_embeddings
                    breakdown.methods_used.append('embeddings')
                except Exception as e:
                    logger.debug(f"Semantic similarity failed: {e}")
            else:
                # High fuzzy match - assume semantic is also high
                breakdown.embeddings = breakdown.rapidfuzz
                scores['embeddings'] = breakdown.embeddings
                weights['embeddings'] = self._semantic_config.weight_embeddings
                breakdown.methods_used.append('embeddings(inferred)')
        
        # Calculate weighted average with DYNAMIC WEIGHT REDISTRIBUTION
        # CRITICAL FIX: If only RapidFuzz is available, use its score directly
        # This prevents score dilution when semantic services are unavailable
        if weights:
            total_weight = sum(weights.values())
            if total_weight > 0:
                weighted_sum = sum(scores[k] * weights[k] for k in scores)
                breakdown.final_score = weighted_sum / total_weight
            
            # FALLBACK: If only one method is available (usually RapidFuzz),
            # use that score directly to maintain backward compatibility
            if len(scores) == 1 and 'rapidfuzz' in scores:
                breakdown.final_score = breakdown.rapidfuzz
                logger.debug("Using RapidFuzz score directly (no semantic services available)")
        
        # Record timing
        elapsed_ms = (time.time() - start_time) * 1000
        breakdown.computation_time_ms = elapsed_ms
        
        # Update statistics
        self._call_count += 1
        self._total_time_ms += elapsed_ms
        
        return breakdown
    
    def is_similar(self, text_a: str, text_b: str) -> bool:
        """
        Check if two texts are similar based on hybrid matching.
        
        Args:
            text_a: First text
            text_b: Second text
            
        Returns:
            True if similarity >= threshold
        """
        score = self.similarity(text_a, text_b)
        return score >= self._semantic_config.semantic_match_threshold
    
    def is_highly_similar(self, text_a: str, text_b: str) -> bool:
        """
        Check if two texts are highly similar (strong match).
        
        Args:
            text_a: First text
            text_b: Second text
            
        Returns:
            True if similarity >= high threshold
        """
        score = self.similarity(text_a, text_b)
        return score >= self._semantic_config.semantic_high_threshold
    
    def find_best_match(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.0
    ) -> Optional[Tuple[int, float, SimilarityBreakdown]]:
        """
        Find the best matching text from a list of candidates.

        OPTIMIZED (v3.3): Two-stage filtering for 5-10x speedup:
        - Stage 1: Fast RapidFuzz pre-screening to find top candidates
        - Stage 2: Full hybrid similarity only on top candidates

        Args:
            query: Query text
            candidates: List of candidate texts
            min_score: Minimum score threshold

        Returns:
            Tuple of (index, score, breakdown) or None if no match above threshold
        """
        if not candidates:
            return None

        # Track performance (v3.3)
        self._perf_stats.total_find_best_calls += 1
        self._perf_stats.total_candidates_screened += len(candidates)

        # OPTIMIZATION v3.3: Two-stage filtering
        # Stage 1: Fast RapidFuzz pre-screening (very fast, ~0.5ms per comparison)
        PRE_SCREEN_THRESHOLD = 0.35  # Low threshold to not miss potential matches
        TOP_CANDIDATES = 10  # Only run full hybrid on top 10

        pre_scores = []
        for idx, candidate in enumerate(candidates):
            # Fast RapidFuzz only (no embeddings, no NLP)
            rf_score = self._rapidfuzz.similarity(query, candidate)
            if rf_score >= PRE_SCREEN_THRESHOLD:
                pre_scores.append((idx, rf_score))

        # Track filtering effectiveness
        self._perf_stats.pre_screen_filtered_count += len(candidates) - len(pre_scores)

        # If no candidates pass pre-screening, return None
        if not pre_scores:
            return None

        # Sort by RapidFuzz score and take top candidates
        pre_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = pre_scores[:TOP_CANDIDATES]

        # Track how many get full hybrid
        self._perf_stats.total_full_hybrid_calls += len(top_candidates)

        # Stage 2: Full hybrid similarity only on top candidates
        best_idx = -1
        best_score = min_score

        for orig_idx, rf_score in top_candidates:
            # Full hybrid similarity (includes embeddings if needed)
            score = self.similarity(query, candidates[orig_idx])

            if score > best_score:
                best_idx = orig_idx
                best_score = score

        if best_idx >= 0:
            # Only compute detailed breakdown for the best match (for logging/debugging)
            best_breakdown = self.similarity_detailed(query, candidates[best_idx])
            return (best_idx, best_score, best_breakdown)

        return None
    
    def find_all_matches(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.5,
        top_k: int = 5
    ) -> List[Tuple[int, float, SimilarityBreakdown]]:
        """
        Find all matching texts above a threshold.

        OPTIMIZED (v3.3): Two-stage filtering for 5-10x speedup:
        - Stage 1: Fast RapidFuzz pre-screening
        - Stage 2: Full hybrid similarity only on promising candidates

        Args:
            query: Query text
            candidates: List of candidate texts
            min_score: Minimum score threshold
            top_k: Maximum number of results

        Returns:
            List of (index, score, breakdown) tuples, sorted by score descending
        """
        if not candidates:
            return []

        # OPTIMIZATION v3.3: Two-stage filtering
        # Stage 1: Fast RapidFuzz pre-screening
        PRE_SCREEN_THRESHOLD = 0.35  # Low threshold to catch potential semantic matches
        MAX_PRE_SCREEN = max(top_k * 3, 15)  # Screen more candidates than needed

        pre_scores = []
        for idx, candidate in enumerate(candidates):
            rf_score = self._rapidfuzz.similarity(query, candidate)
            if rf_score >= PRE_SCREEN_THRESHOLD:
                pre_scores.append((idx, rf_score))

        if not pre_scores:
            return []

        # Sort and limit pre-screening results
        pre_scores.sort(key=lambda x: x[1], reverse=True)
        pre_scores = pre_scores[:MAX_PRE_SCREEN]

        # Stage 2: Full hybrid similarity on pre-screened candidates
        scored_candidates = []
        for orig_idx, rf_score in pre_scores:
            score = self.similarity(query, candidates[orig_idx])
            if score >= min_score:
                scored_candidates.append((orig_idx, score))

        # Sort by score descending and take top_k
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_matches = scored_candidates[:top_k]

        # Only compute detailed breakdowns for final results
        results = []
        for idx, score in top_matches:
            breakdown = self.similarity_detailed(query, candidates[idx])
            results.append((idx, score, breakdown))

        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service usage statistics."""
        avg_time = self._total_time_ms / self._call_count if self._call_count > 0 else 0

        # Calculate performance savings
        if self._perf_stats.total_candidates_screened > 0:
            savings_pct = (1 - self._perf_stats.total_full_hybrid_calls / self._perf_stats.total_candidates_screened) * 100
        else:
            savings_pct = 0.0

        return {
            'call_count': self._call_count,
            'total_time_ms': round(self._total_time_ms, 2),
            'avg_time_ms': round(avg_time, 2),
            'services_available': {
                'rapidfuzz': True,
                'nlp': self._nlp is not None and self._nlp.is_available if self._nlp else False,
                'synonyms': self._synonyms is not None and self._synonyms.is_available if self._synonyms else False,
                'tfidf': self._tfidf is not None and self._tfidf.is_trained if self._tfidf else False,
                'embeddings': self._semantic is not None and self._semantic.is_available if self._semantic else False
            },
            'performance_v33': {
                'find_best_calls': self._perf_stats.total_find_best_calls,
                'candidates_screened': self._perf_stats.total_candidates_screened,
                'full_hybrid_calls': self._perf_stats.total_full_hybrid_calls,
                'pre_screen_filtered': self._perf_stats.pre_screen_filtered_count,
                'savings_percent': round(savings_pct, 1)
            }
        }

    def log_performance_summary(self) -> None:
        """Log performance summary for this session."""
        self._perf_stats.log_summary()
    
    def clear_caches(self) -> None:
        """Clear all internal caches."""
        if self._nlp:
            self._nlp.clear_cache()
        if self._synonyms:
            self._synonyms.clear_cache()

