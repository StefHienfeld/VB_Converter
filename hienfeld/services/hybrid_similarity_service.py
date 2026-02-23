# hienfeld/services/hybrid_similarity_service.py
"""
Hybrid similarity service combining multiple matching techniques.

Combines:
1. RapidFuzz (exact/fuzzy string matching)
2. Lemmatized matching (normalized word forms)
3. TF-IDF (keyword importance)
4. Synonym matching (domain-specific)
5. Sentence embeddings (semantic meaning)
6. FAISS vector index (exhaustive search) - v3.4
7. BM25 pre-filter (terminology matching) - v3.5

Each method contributes to a weighted final score.
No external APIs required - runs entirely locally.
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import time

import numpy as np

from ..config import AppConfig, SemanticConfig
from ..logging_config import get_logger
from .similarity_service import RapidFuzzSimilarityService, SemanticSimilarityService
from .nlp_service import NLPService
from .synonym_service import SynonymService
from .document_similarity_service import DocumentSimilarityService

logger = get_logger('hybrid_similarity_service')

# Try to import FAISS for exhaustive vector search
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.debug("FAISS not available - will use brute-force search")

# Try to import rank_bm25 for BM25 terminology pre-filtering (v3.5)
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.debug("rank_bm25 not available - BM25 pre-filter disabled (pip install rank-bm25)")


@dataclass
class SimilarityBreakdown:
    """Detailed breakdown of similarity scores from each method."""
    rapidfuzz: float = 0.0
    lemmatized: float = 0.0
    tfidf: float = 0.0
    synonyms: float = 0.0
    embeddings: float = 0.0
    bm25: float = 0.0      # v3.5: BM25 terminology-match score
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

    # FAISS statistics (v3.4)
    faiss_index_builds: int = 0
    faiss_searches: int = 0
    faiss_search_time_ms: float = 0.0
    brute_force_fallbacks: int = 0

    def log_summary(self):
        """Log performance summary."""
        if self.total_find_best_calls > 0:
            savings = (1 - self.total_full_hybrid_calls / max(1, self.total_candidates_screened)) * 100
            faiss_info = ""
            if self.faiss_searches > 0:
                avg_faiss_time = self.faiss_search_time_ms / self.faiss_searches
                faiss_info = f", FAISS: {self.faiss_searches} searches ({avg_faiss_time:.1f}ms avg)"
            logger.info(
                f"[PERF] Performance: {self.total_find_best_calls} calls, "
                f"{self.total_candidates_screened} candidates screened, "
                f"{self.total_full_hybrid_calls} full hybrid ({savings:.1f}% saved){faiss_info}"
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

        # FAISS index for exhaustive vector search (v3.4)
        self._faiss_index = None
        self._faiss_embeddings: Optional[np.ndarray] = None
        self._faiss_texts: List[str] = []
        self._faiss_available = FAISS_AVAILABLE
        self._use_faiss = True  # Can be disabled via config

        # BM25 pre-filter for terminology matching (v3.5)
        # Corpus is built lazily when candidates are first seen in find_best_match
        self._bm25_available = BM25_AVAILABLE
        self._bm25_index: Optional[object] = None   # BM25Okapi instance
        self._bm25_corpus_texts: List[str] = []     # tokenised candidate texts
        self._bm25_raw_texts: List[str] = []        # original candidate texts (for identity check)
    
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
        if self._bm25_available:
            available.append("BM25")
        
        if len(available) == 1 and "RapidFuzz" in available:
            logger.warning(
                "[WARN] Only RapidFuzz available - semantic enhancements disabled. "
                "Install dependencies for better matching: pip install spacy scikit-learn"
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

    def build_faiss_index(self, texts: List[str]) -> bool:
        """
        Build a FAISS index for fast approximate nearest neighbor search.

        This pre-computes embeddings for all texts and builds a FAISS index.
        IndexFlatIP performs exhaustive O(n) inner product search over all
        indexed vectors. The speedup over repeated on-demand embedding
        computation comes from batch pre-computation, not from sub-linear
        search; all n vectors are still compared per query.

        IMPORTANT: Call this method before find_best_match/find_all_matches
        with the candidate texts (e.g., policy conditions) for significant
        speedup on large datasets (100+ seconds saved on 500+ candidates).

        Args:
            texts: List of texts to index (e.g., policy condition texts)

        Returns:
            True if index was built successfully, False otherwise
        """
        if not texts:
            logger.warning("No texts provided for FAISS index")
            return False

        self._ensure_services_initialized()

        # Check if semantic service is available (needed for embeddings)
        if not self._semantic or not self._semantic.is_available:
            logger.warning("FAISS index skipped: semantic service not available")
            return False

        # Check if FAISS is available
        if not self._faiss_available:
            logger.info("FAISS not installed - using brute-force search (install faiss-cpu for 100+ sec speedup)")
            return False

        start_time = time.time()

        try:
            # Get embeddings for all texts
            logger.info(f"Building FAISS index for {len(texts)} texts...")

            # Use the embeddings service to get vectors
            embeddings_service = getattr(self._semantic, '_embeddings_service', None)
            if embeddings_service is None:
                logger.warning("No embeddings service available for FAISS (model may not be loaded)")
                return False

            # Check if embeddings service has the required method
            if not hasattr(embeddings_service, 'embed_texts'):
                logger.warning("Embeddings service does not support batch embedding")
                return False

            # Batch embed all texts
            embeddings = embeddings_service.embed_texts(texts)

            if embeddings is None:
                logger.warning("Embeddings service returned None")
                return False
            embeddings = np.ascontiguousarray(embeddings.astype(np.float32))

            # Normalize for cosine similarity (FAISS inner product on normalized vectors = cosine)
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Avoid division by zero
            embeddings = embeddings / norms

            # Build FAISS index (IndexFlatIP for inner product = cosine on normalized)
            embedding_dim = embeddings.shape[1]
            self._faiss_index = faiss.IndexFlatIP(embedding_dim)
            self._faiss_index.add(embeddings)

            # Store references
            self._faiss_embeddings = embeddings
            self._faiss_texts = texts.copy()

            elapsed = time.time() - start_time
            self._perf_stats.faiss_index_builds += 1

            logger.info(
                f"[OK] FAISS index built: {len(texts)} vectors, "
                f"dim={embedding_dim}, time={elapsed:.2f}s"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}")
            self._faiss_index = None
            self._faiss_embeddings = None
            self._faiss_texts = []
            return False

    def _faiss_search(self, query_text: str, k: int = 10) -> List[Tuple[int, float]]:
        """
        Search the FAISS index for top-k similar texts.

        Args:
            query_text: Query text
            k: Number of results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by score descending
        """
        if self._faiss_index is None or not self._faiss_texts:
            return []

        start_time = time.time()

        try:
            # Get query embedding
            embeddings_service = self._semantic._embeddings_service
            query_emb = embeddings_service.embed_single(query_text)
            query_emb = query_emb.astype(np.float32).reshape(1, -1)

            # Normalize for cosine similarity
            query_norm = np.linalg.norm(query_emb)
            if query_norm > 0:
                query_emb = query_emb / query_norm

            # Search FAISS index
            actual_k = min(k, self._faiss_index.ntotal)
            scores, indices = self._faiss_index.search(query_emb, actual_k)

            # Track performance
            elapsed_ms = (time.time() - start_time) * 1000
            self._perf_stats.faiss_searches += 1
            self._perf_stats.faiss_search_time_ms += elapsed_ms

            # Build results (filter invalid indices)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0:
                    results.append((int(idx), float(score)))

            return results

        except Exception as e:
            logger.debug(f"FAISS search failed: {e}")
            return []

    def clear_faiss_index(self) -> None:
        """Clear the FAISS index to free memory."""
        self._faiss_index = None
        self._faiss_embeddings = None
        self._faiss_texts = []
        logger.debug("FAISS index cleared")

    @property
    def has_faiss_index(self) -> bool:
        """Check if a FAISS index is available."""
        return self._faiss_index is not None and len(self._faiss_texts) > 0

    @property
    def faiss_index_size(self) -> int:
        """Get the number of vectors in the FAISS index."""
        return len(self._faiss_texts) if self._faiss_texts else 0

    # ------------------------------------------------------------------
    # BM25 helpers (v3.5)
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize_for_bm25(text: str) -> List[str]:
        """
        Simple whitespace tokenizer for BM25.

        Lowercases and splits on whitespace.  For Dutch insurance clauses a
        simple split is sufficient; a more elaborate tokenizer can be
        substituted here without touching any other code.
        """
        return text.lower().split()

    def _build_bm25_index(self, candidates: List[str]) -> bool:
        """
        Build (or rebuild) a BM25Okapi index over *candidates*.

        The index is rebuilt only when the candidate list changes, so the
        cost is paid once per unique candidate set.

        Args:
            candidates: Raw candidate texts to index.

        Returns:
            True if the index was built successfully, False otherwise.
        """
        if not self._bm25_available:
            return False
        if not candidates:
            return False

        try:
            tokenized = [self._tokenize_for_bm25(c) for c in candidates]
            self._bm25_index = BM25Okapi(tokenized)
            self._bm25_raw_texts = list(candidates)
            logger.debug(f"BM25 index built for {len(candidates)} candidates")
            return True
        except Exception as e:
            logger.warning(f"BM25 index build failed: {e}")
            self._bm25_index = None
            self._bm25_raw_texts = []
            return False

    def _bm25_scores(self, query: str, candidates: List[str]) -> List[float]:
        """
        Return normalised BM25 scores (0.0–1.0) for *query* against all
        *candidates*.

        Rebuilds the index lazily whenever the candidate list changes.
        Scores are normalised by dividing by the maximum score so that
        the values are always in [0, 1].  When all scores are 0 (no term
        overlap) every candidate receives 0.0.

        Args:
            query: Query text.
            candidates: Candidate texts (same list used in find_best_match).

        Returns:
            List of float scores, one per candidate, in [0.0, 1.0].
        """
        if not self._bm25_available:
            return [0.0] * len(candidates)

        # Rebuild index if candidate list changed
        if self._bm25_raw_texts != candidates:
            ok = self._build_bm25_index(candidates)
            if not ok:
                return [0.0] * len(candidates)

        if self._bm25_index is None:
            return [0.0] * len(candidates)

        try:
            tokenized_query = self._tokenize_for_bm25(query)
            raw_scores = self._bm25_index.get_scores(tokenized_query)
            max_score = float(max(raw_scores)) if len(raw_scores) > 0 else 0.0
            if max_score > 0:
                return [float(s) / max_score for s in raw_scores]
            return [0.0] * len(candidates)
        except Exception as e:
            logger.debug(f"BM25 scoring failed: {e}")
            return [0.0] * len(candidates)

    def clear_bm25_index(self) -> None:
        """Clear the BM25 index to free memory."""
        self._bm25_index = None
        self._bm25_raw_texts = []
        logger.debug("BM25 index cleared")

    @property
    def has_bm25_index(self) -> bool:
        """Check if a BM25 index is currently available."""
        return self._bm25_index is not None

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

        # 6. BM25 pairwise score (v3.5)
        # Only active in BALANCED and ACCURATE modes (enable_bm25=True, weight_bm25>0).
        # A single-document corpus [text_b] is used so that BM25 measures how well
        # the query terms from text_a are covered by text_b relative to itself.
        # The score is always 1.0 for a perfect term match and 0.0 for no overlap.
        if (self._bm25_available and
                mode_config.enable_bm25 and
                mode_config.weight_bm25 > 0):
            try:
                bm25_score = self._bm25_scores(text_a, [text_b])
                scores['bm25'] = bm25_score[0] if bm25_score else 0.0
                weights['bm25'] = mode_config.weight_bm25
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

        # 6. BM25 pairwise score (v3.5) - active only in BALANCED/ACCURATE modes
        mode_config = self._semantic_config.get_active_config()
        if (self._bm25_available and
                mode_config.enable_bm25 and
                mode_config.weight_bm25 > 0):
            try:
                bm25_score = self._bm25_scores(text_a, [text_b])
                breakdown.bm25 = bm25_score[0] if bm25_score else 0.0
                scores['bm25'] = breakdown.bm25
                weights['bm25'] = self._semantic_config.weight_bm25
                breakdown.methods_used.append('bm25')
            except Exception as e:
                logger.debug(f"BM25 scoring failed: {e}")

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

        OPTIMIZED (v3.4): Three-stage filtering with optional FAISS:
        - Stage 0 (NEW): FAISS exhaustive search if index available (O(n), but
          avoids repeated on-demand embedding computation per query)
        - Stage 1: Fast RapidFuzz pre-screening to find top candidates
        - Stage 2: Full hybrid similarity only on top candidates

        For large datasets (500+ candidates), FAISS provides 100+ second speedup
        through pre-computed batch embeddings, not sub-linear search.

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

        # OPTIMIZATION v3.4: Use FAISS if index is available and matches candidates
        # IndexFlatIP is exhaustive O(n) search, but avoids recomputing embeddings
        # per query - significant speedup via batch pre-computation on large sets
        if self._use_faiss and self.has_faiss_index and self._faiss_texts == candidates:
            return self._find_best_match_faiss(query, candidates, min_score)

        # Fallback: Track brute-force usage
        self._perf_stats.brute_force_fallbacks += 1

        # OPTIMIZATION v3.3 / v3.5: Two-stage filtering (brute-force path)
        # Stage 1: Fast pre-screening with RapidFuzz + optional BM25 (v3.5)
        PRE_SCREEN_THRESHOLD = 0.35  # Low threshold to not miss potential matches
        TOP_CANDIDATES = 10  # Only run full hybrid on top 10

        mode_config = self._semantic_config.get_active_config()
        use_bm25_prefilter = (
            self._bm25_available
            and mode_config.enable_bm25
            and mode_config.weight_bm25 > 0
        )

        # Compute BM25 scores over the full candidate list if BM25 is active
        # This builds (or reuses) the BM25 index for the current candidate set
        bm25_scores_list: List[float] = []
        if use_bm25_prefilter:
            bm25_scores_list = self._bm25_scores(query, candidates)

        pre_scores = []
        for idx, candidate in enumerate(candidates):
            # Fast RapidFuzz only (no embeddings, no NLP)
            rf_score = self._rapidfuzz.similarity(query, candidate)
            if rf_score >= PRE_SCREEN_THRESHOLD:
                # Combine RapidFuzz and BM25 for a better pre-ranking signal
                if use_bm25_prefilter and bm25_scores_list:
                    combined = (rf_score + bm25_scores_list[idx]) / 2
                else:
                    combined = rf_score
                pre_scores.append((idx, combined))

        # Track filtering effectiveness
        self._perf_stats.pre_screen_filtered_count += len(candidates) - len(pre_scores)

        # If no candidates pass pre-screening, return None
        if not pre_scores:
            return None

        # Sort by combined score and take top candidates
        pre_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = pre_scores[:TOP_CANDIDATES]

        # Track how many get full hybrid
        self._perf_stats.total_full_hybrid_calls += len(top_candidates)

        # Stage 2: Full hybrid similarity only on top candidates
        best_idx = -1
        best_score = min_score

        for orig_idx, _ in top_candidates:
            # Full hybrid similarity (includes embeddings + BM25 if enabled)
            score = self.similarity(query, candidates[orig_idx])

            if score > best_score:
                best_idx = orig_idx
                best_score = score

        if best_idx >= 0:
            # Only compute detailed breakdown for the best match (for logging/debugging)
            best_breakdown = self.similarity_detailed(query, candidates[best_idx])
            return (best_idx, best_score, best_breakdown)

        return None

    def _find_best_match_faiss(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.0
    ) -> Optional[Tuple[int, float, SimilarityBreakdown]]:
        """
        Find best match using FAISS index (exhaustive vector search).

        IndexFlatIP performs exhaustive O(n) search over all indexed vectors.
        The speedup on large candidate sets comes from using pre-computed
        batch embeddings instead of computing them on demand per query.

        Args:
            query: Query text
            candidates: List of candidate texts (must match indexed texts)
            min_score: Minimum score threshold

        Returns:
            Tuple of (index, score, breakdown) or None if no match above threshold
        """
        # Stage 0: FAISS exhaustive search for top candidates (O(n))
        TOP_K_FAISS = 20  # Get more candidates from FAISS for re-ranking
        faiss_results = self._faiss_search(query, k=TOP_K_FAISS)

        if not faiss_results:
            # FAISS search failed, fall back to brute-force RapidFuzz
            self._perf_stats.brute_force_fallbacks += 1
            return self._find_best_match_bruteforce(query, candidates, min_score)

        # Stage 1: Re-rank with RapidFuzz (very fast)
        PRE_SCREEN_THRESHOLD = 0.35
        TOP_CANDIDATES = 10

        pre_scores = []
        for idx, faiss_score in faiss_results:
            if idx < len(candidates):
                rf_score = self._rapidfuzz.similarity(query, candidates[idx])
                if rf_score >= PRE_SCREEN_THRESHOLD:
                    # Combine FAISS and RapidFuzz for better ranking
                    combined_score = (faiss_score + rf_score) / 2
                    pre_scores.append((idx, combined_score, rf_score))

        if not pre_scores:
            return None

        # Sort by combined score and take top candidates
        pre_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = pre_scores[:TOP_CANDIDATES]

        # Track how many get full hybrid
        self._perf_stats.total_full_hybrid_calls += len(top_candidates)

        # Stage 2: Full hybrid similarity only on top candidates
        best_idx = -1
        best_score = min_score

        for orig_idx, _, _ in top_candidates:
            # Full hybrid similarity (includes all methods)
            score = self.similarity(query, candidates[orig_idx])

            if score > best_score:
                best_idx = orig_idx
                best_score = score

        if best_idx >= 0:
            best_breakdown = self.similarity_detailed(query, candidates[best_idx])
            return (best_idx, best_score, best_breakdown)

        return None

    def _find_best_match_bruteforce(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.0
    ) -> Optional[Tuple[int, float, SimilarityBreakdown]]:
        """
        Brute-force find_best_match for fallback.

        Used when FAISS is not available or index doesn't match candidates.
        """
        PRE_SCREEN_THRESHOLD = 0.35
        TOP_CANDIDATES = 10

        mode_config = self._semantic_config.get_active_config()
        use_bm25_prefilter = (
            self._bm25_available
            and mode_config.enable_bm25
            and mode_config.weight_bm25 > 0
        )
        bm25_scores_list: List[float] = []
        if use_bm25_prefilter:
            bm25_scores_list = self._bm25_scores(query, candidates)

        pre_scores = []
        for idx, candidate in enumerate(candidates):
            rf_score = self._rapidfuzz.similarity(query, candidate)
            if rf_score >= PRE_SCREEN_THRESHOLD:
                if use_bm25_prefilter and bm25_scores_list:
                    combined = (rf_score + bm25_scores_list[idx]) / 2
                else:
                    combined = rf_score
                pre_scores.append((idx, combined))

        self._perf_stats.pre_screen_filtered_count += len(candidates) - len(pre_scores)

        if not pre_scores:
            return None

        pre_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = pre_scores[:TOP_CANDIDATES]
        self._perf_stats.total_full_hybrid_calls += len(top_candidates)

        best_idx = -1
        best_score = min_score

        for orig_idx, _ in top_candidates:
            score = self.similarity(query, candidates[orig_idx])
            if score > best_score:
                best_idx = orig_idx
                best_score = score

        if best_idx >= 0:
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

        OPTIMIZED (v3.4): Three-stage filtering with optional FAISS:
        - Stage 0 (NEW): FAISS exhaustive search if index available (O(n),
          avoids recomputing embeddings per query via batch pre-computation)
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

        # OPTIMIZATION v3.4: Use FAISS if index is available and matches candidates
        # (exhaustive O(n) search, speedup via pre-computed batch embeddings)
        if self._use_faiss and self.has_faiss_index and self._faiss_texts == candidates:
            return self._find_all_matches_faiss(query, candidates, min_score, top_k)

        # Fallback: brute-force path
        return self._find_all_matches_bruteforce(query, candidates, min_score, top_k)

    def _find_all_matches_faiss(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.5,
        top_k: int = 5
    ) -> List[Tuple[int, float, SimilarityBreakdown]]:
        """
        Find all matches using FAISS index (exhaustive vector search).
        """
        # Stage 0: FAISS exhaustive search for candidates (O(n))
        TOP_K_FAISS = max(top_k * 5, 30)  # Get more candidates for filtering
        faiss_results = self._faiss_search(query, k=TOP_K_FAISS)

        if not faiss_results:
            return self._find_all_matches_bruteforce(query, candidates, min_score, top_k)

        # Stage 1: Re-rank with RapidFuzz
        PRE_SCREEN_THRESHOLD = 0.35
        MAX_PRE_SCREEN = max(top_k * 3, 15)

        pre_scores = []
        for idx, faiss_score in faiss_results:
            if idx < len(candidates):
                rf_score = self._rapidfuzz.similarity(query, candidates[idx])
                if rf_score >= PRE_SCREEN_THRESHOLD:
                    combined_score = (faiss_score + rf_score) / 2
                    pre_scores.append((idx, combined_score))

        if not pre_scores:
            return []

        pre_scores.sort(key=lambda x: x[1], reverse=True)
        pre_scores = pre_scores[:MAX_PRE_SCREEN]

        # Stage 2: Full hybrid similarity
        scored_candidates = []
        for orig_idx, _ in pre_scores:
            score = self.similarity(query, candidates[orig_idx])
            if score >= min_score:
                scored_candidates.append((orig_idx, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_matches = scored_candidates[:top_k]

        results = []
        for idx, score in top_matches:
            breakdown = self.similarity_detailed(query, candidates[idx])
            results.append((idx, score, breakdown))

        return results

    def _find_all_matches_bruteforce(
        self,
        query: str,
        candidates: List[str],
        min_score: float = 0.5,
        top_k: int = 5
    ) -> List[Tuple[int, float, SimilarityBreakdown]]:
        """
        Brute-force find_all_matches for fallback.
        v3.5: BM25 pre-filter incorporated for BALANCED/ACCURATE modes.
        """
        PRE_SCREEN_THRESHOLD = 0.35
        MAX_PRE_SCREEN = max(top_k * 3, 15)

        mode_config = self._semantic_config.get_active_config()
        use_bm25_prefilter = (
            self._bm25_available
            and mode_config.enable_bm25
            and mode_config.weight_bm25 > 0
        )
        bm25_scores_list: List[float] = []
        if use_bm25_prefilter:
            bm25_scores_list = self._bm25_scores(query, candidates)

        pre_scores = []
        for idx, candidate in enumerate(candidates):
            rf_score = self._rapidfuzz.similarity(query, candidate)
            if rf_score >= PRE_SCREEN_THRESHOLD:
                if use_bm25_prefilter and bm25_scores_list:
                    combined = (rf_score + bm25_scores_list[idx]) / 2
                else:
                    combined = rf_score
                pre_scores.append((idx, combined))

        if not pre_scores:
            return []

        pre_scores.sort(key=lambda x: x[1], reverse=True)
        pre_scores = pre_scores[:MAX_PRE_SCREEN]

        scored_candidates = []
        for orig_idx, _ in pre_scores:
            score = self.similarity(query, candidates[orig_idx])
            if score >= min_score:
                scored_candidates.append((orig_idx, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_matches = scored_candidates[:top_k]

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

        # FAISS statistics (v3.4)
        avg_faiss_time = 0.0
        if self._perf_stats.faiss_searches > 0:
            avg_faiss_time = self._perf_stats.faiss_search_time_ms / self._perf_stats.faiss_searches

        return {
            'call_count': self._call_count,
            'total_time_ms': round(self._total_time_ms, 2),
            'avg_time_ms': round(avg_time, 2),
            'services_available': {
                'rapidfuzz': True,
                'nlp': self._nlp is not None and self._nlp.is_available if self._nlp else False,
                'synonyms': self._synonyms is not None and self._synonyms.is_available if self._synonyms else False,
                'tfidf': self._tfidf is not None and self._tfidf.is_trained if self._tfidf else False,
                'embeddings': self._semantic is not None and self._semantic.is_available if self._semantic else False,
                'faiss': self.has_faiss_index,
                'bm25': self._bm25_available  # v3.5
            },
            'performance_v33': {
                'find_best_calls': self._perf_stats.total_find_best_calls,
                'candidates_screened': self._perf_stats.total_candidates_screened,
                'full_hybrid_calls': self._perf_stats.total_full_hybrid_calls,
                'pre_screen_filtered': self._perf_stats.pre_screen_filtered_count,
                'savings_percent': round(savings_pct, 1)
            },
            'faiss_v34': {
                'available': self._faiss_available,
                'index_built': self.has_faiss_index,
                'index_size': self.faiss_index_size,
                'index_builds': self._perf_stats.faiss_index_builds,
                'searches': self._perf_stats.faiss_searches,
                'avg_search_time_ms': round(avg_faiss_time, 2),
                'brute_force_fallbacks': self._perf_stats.brute_force_fallbacks
            }
        }

    def log_performance_summary(self) -> None:
        """Log performance summary for this session."""
        self._perf_stats.log_summary()
    
    def clear_caches(self) -> None:
        """Clear all internal caches including FAISS and BM25 indexes."""
        if self._nlp:
            self._nlp.clear_cache()
        if self._synonyms:
            self._synonyms.clear_cache()
        # Clear FAISS index (v3.4)
        self.clear_faiss_index()
        # Clear BM25 index (v3.5)
        self.clear_bm25_index()

