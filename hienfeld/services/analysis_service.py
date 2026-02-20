# hienfeld/services/analysis_service.py
"""
Service for analyzing clusters and generating advice.

Implements a 5-step WATERFALL PIPELINE:
0. ADMIN CHECK - Hygiene issues (empty, outdated, placeholders) -> CLEAN/COMPLETE/DELETE
0.5. CUSTOM INSTRUCTIONS CHECK - User-defined rules matched semantically -> CUSTOM ACTION
1. CLAUSE LIBRARY CHECK - Match against standard clauses -> REPLACE
2. POLICY CONDITIONS CHECK - Match against conditions -> DELETE (redundant)
3. COMPLIANCE CHECK - LLM analysis for conflicts -> CONFLICT/EXTENSION/LIMITATION
"""
from typing import Dict, List, Optional, Callable, Tuple
import re

from ..config import AppConfig
from ..domain.cluster import Cluster
from ..domain.policy_document import PolicyDocumentSection
from ..domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from ..domain.standard_clause import StandardClause, ClauseLibraryMatch
from ..utils.text_normalization import simplify_text
from ..services.similarity_service import RapidFuzzSimilarityService, SimilarityService, SemanticSimilarityService, SemanticMatch
from ..domain.reference import ReferenceMatch
from ..logging_config import get_logger

# Optional hybrid similarity (semantic enhancement)
try:
    from ..services.hybrid_similarity_service import HybridSimilarityService
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

# Optional LLM reranking service (v4.3 - uncertain match enhancement)
try:
    from ..services.ai.reranking_service import ReRankingService
    RERANKING_AVAILABLE = True
except ImportError:
    RERANKING_AVAILABLE = False

# Analysis pipeline (v4.5 - Strategy pattern refactor)
try:
    from ..services.analysis.analysis_pipeline import AnalysisPipeline
    from ..services.analysis.analysis_context import AnalysisContextBuilder
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

logger = get_logger('analysis_service')


class AnalysisService:
    """
    Analyzes clusters and generates actionable advice.
    
    WATERFALL PIPELINE (5 STEPS):
    
    ┌─────────────────────────────────────────────────────────────┐
    │  STEP 0: ADMIN CHECK                                        │
    │  Hygiene issues: empty, outdated dates, placeholders        │
    │  Issue found? → OPSCHONEN/AANVULLEN/VERWIJDEREN             │
    │  No issues? → Continue to Step 0.5                          │
    └─────────────────────────────────────────────────────────────┘
                               ↓
    ┌─────────────────────────────────────────────────────────────┐
    │  STEP 0.5: CUSTOM INSTRUCTIONS CHECK (NEW)                  │
    │  User-defined rules matched semantically against input      │
    │  Match found? → Return custom action from user              │
    │  No match? → Continue to Step 1                             │
    └─────────────────────────────────────────────────────────────┘
                               ↓
    ┌─────────────────────────────────────────────────────────────┐
    │  STEP 1: CLAUSE LIBRARY CHECK                               │
    │  Compare against standard clauses with codes                │
    │  Match > 95%? → REPLACE with [CODE]                         │
    │  Match > 85%? → REVIEW similarity to [CODE]                 │
    │  No match? → Continue to Step 2                             │
    └─────────────────────────────────────────────────────────────┘
                               ↓
    ┌─────────────────────────────────────────────────────────────┐
    │  STEP 2: POLICY CONDITIONS CHECK                            │
    │  Compare against policy conditions text                     │
    │  Match > 95%? → DELETE (covered by Art X)                   │
    │  Match > 85%? → DELETE with review                          │
    │  No match? → Continue to Step 3                             │
    └─────────────────────────────────────────────────────────────┘
                               ↓
    ┌─────────────────────────────────────────────────────────────┐
    │  STEP 3: FALLBACK / AI ANALYSIS                             │
    │  Keyword rules, frequency analysis, or LLM compliance check │
    └─────────────────────────────────────────────────────────────┘
    """
    
    # Thresholds for matching - RESTORED to proven values
    # Note: Lowering these caused worse results (more false negatives)
    EXACT_MATCH_THRESHOLD = 0.95      # Almost identical -> REPLACE/DELETE
    HIGH_SIMILARITY_THRESHOLD = 0.85   # Very similar -> REVIEW
    MEDIUM_SIMILARITY_THRESHOLD = 0.75 # Similar -> POSSIBLE MATCH
    
    # Semantic similarity thresholds
    SEMANTIC_MATCH_THRESHOLD = 0.70   # Threshold for semantic similarity (embeddings)
    SEMANTIC_HIGH_THRESHOLD = 0.80    # High confidence semantic match
    
    # Brei-detection settings
    # BREI_MIN_LENGTH removed - now using config.analysis_rules.max_text_length instead
    
    def __init__(
        self,
        config: AppConfig,
        ai_analyzer=None,
        similarity_service: Optional[SimilarityService] = None,
        semantic_similarity_service: Optional[SemanticSimilarityService] = None,
        hybrid_similarity_service=None,
        clause_library_service=None,
        admin_check_service=None,
        custom_instructions_service=None,
        reference_service=None,
        reranking_service=None
    ):
        """
        Initialize the analysis service.

        Args:
            config: Application configuration
            ai_analyzer: Optional AI analyzer service for enhanced analysis
            similarity_service: Service for computing text similarity (RapidFuzz)
            semantic_similarity_service: Service for semantic/meaning-based comparison
            hybrid_similarity_service: Optional HybridSimilarityService for enhanced matching
            clause_library_service: Service for clause library lookups
            admin_check_service: Service for administrative/hygiene checks (Step 0)
            custom_instructions_service: Service for user-defined custom rules (Step 0.5)
            reference_service: Service for reference analysis comparison (yearly vs monthly)
            reranking_service: Optional ReRankingService for LLM-based reranking (v4.3)
        """
        self.config = config
        self.ai_analyzer = ai_analyzer
        self.clause_library_service = clause_library_service
        self.admin_check_service = admin_check_service
        self.custom_instructions_service = custom_instructions_service
        self.reference_service = reference_service

        # Similarity service for comparing against conditions (text-based)
        if similarity_service is None:
            self.similarity_service = RapidFuzzSimilarityService(
                threshold=self.HIGH_SIMILARITY_THRESHOLD
            )
        else:
            self.similarity_service = similarity_service

        # Semantic similarity service (embedding-based)
        self.semantic_similarity_service = semantic_similarity_service
        self._semantic_index_ready = False

        # Hybrid similarity service (v3.0 semantic enhancement)
        self.hybrid_similarity_service = hybrid_similarity_service
        self._hybrid_enabled = hybrid_similarity_service is not None

        # LLM Reranking service (v4.3 - uncertain match enhancement)
        self.reranking_service = reranking_service
        self._reranking_enabled = (
            reranking_service is not None and
            hasattr(config, 'ai') and
            hasattr(config.ai, 'reranking') and
            config.ai.reranking.enabled
        )

        # Cache for policy sections
        self._policy_sections: List[PolicyDocumentSection] = []
        self._policy_full_text: str = ""
        self._policy_section_lookup: Dict[str, PolicyDocumentSection] = {}

        # Cache for reference matches (text -> ReferenceMatch)
        self._reference_matches: Dict[str, Optional[ReferenceMatch]] = {}

        # Reranking statistics (v4.3)
        self._reranking_stats = {
            'total_reranked': 0,
            'score_improvements': 0,
            'avg_score_boost': 0.0
        }

        # Analysis pipeline (v4.5 - Strategy pattern)
        self._pipeline: Optional["AnalysisPipeline"] = None
        # Feature flag: disabled by default until strategies have full parity
        # Enable via: analysis_service._use_pipeline = True
        self._use_pipeline = False

    @property
    def pipeline(self) -> Optional["AnalysisPipeline"]:
        """
        Get or create the analysis pipeline with default strategies.

        Returns:
            AnalysisPipeline if available, None otherwise
        """
        if not PIPELINE_AVAILABLE:
            return None

        if self._pipeline is None:
            self._pipeline = AnalysisPipeline.create_default()
            logger.debug(f"Created analysis pipeline: {self._pipeline}")

        return self._pipeline

    def _build_analysis_context(self) -> "AnalysisContextBuilder":
        """
        Build an AnalysisContext from the current service state.

        Returns:
            AnalysisContextBuilder ready to build()
        """
        if not PIPELINE_AVAILABLE:
            raise RuntimeError("Pipeline not available")

        return AnalysisContextBuilder.from_analysis_service(self)

    def _update_stats_from_advice(self, advice: AnalysisAdvice, stats: dict) -> None:
        """
        Update statistics dictionary based on advice category.

        Maps pipeline advice categories back to the stats keys used
        by the legacy waterfall code.

        Args:
            advice: The generated advice
            stats: Stats dictionary to update
        """
        category = advice.category or ""

        # Map categories to stats keys
        if category.startswith("ADMIN"):
            stats['step0_admin_issues'] = stats.get('step0_admin_issues', 0) + 1
        elif category == "CUSTOM_INSTRUCTION":
            stats['step05_custom_instructions'] = stats.get('step05_custom_instructions', 0) + 1
        elif category.startswith("LIBRARY_"):
            stats['step1_library_match'] = stats.get('step1_library_match', 0) + 1
        elif category.startswith("CONDITIONS_"):
            stats['step2_conditions_match'] = stats.get('step2_conditions_match', 0) + 1
        else:
            stats['step3_fallback'] = stats.get('step3_fallback', 0) + 1

    def _format_section_reference(self, section: PolicyDocumentSection) -> str:
        """
        Format a human-friendly, non-hallucinated reference for Excel output.

        Hard rule: never invent numbers/titles/pages. Only use fields that exist on the section.
        """
        if not section:
            return "Voorwaarden"

        section_id = (section.id or "").strip()
        title = (section.title or "").strip()

        # Preferred: real article numbering
        if section_id.startswith("Art "):
            if title:
                ref = f"{section_id} – {title}"
                # Trim if too long for Excel readability (max 80 chars)
                if len(ref) > 80:
                    ref = ref[:77] + "..."
                return ref
            return section_id or "Voorwaarden"

        # Fallback: file + page
        document = (section.document_id or "").strip() or "Voorwaarden"
        page = section.page_number
        if isinstance(page, int) and page > 0:
            return f"{document}, pagina {page}"
        return f"{document}, pagina onbekend"

    def _find_matching_section(self, text: str) -> Optional[PolicyDocumentSection]:
        """Find the first section where the given text appears (substring match)."""
        for section in self._policy_sections:
            if section.simplified_text and text in section.simplified_text:
                return section
        return None
    
    def set_clause_library_service(self, service) -> None:
        """
        Set the clause library service for Step 1 of the pipeline.

        Args:
            service: ClauseLibraryService instance
        """
        self.clause_library_service = service
        logger.info("Clause library service configured for analysis")

    def set_reference_service(self, service) -> None:
        """
        Set the reference analysis service for yearly vs monthly comparison.

        Args:
            service: ReferenceAnalysisService instance
        """
        self.reference_service = service
        self._reference_matches = {}  # Clear cache
        logger.info("Reference analysis service configured")

    def _get_reference_match(self, text: str) -> Optional[ReferenceMatch]:
        """
        Get cached reference match or perform lookup.

        Args:
            text: Simplified text to match

        Returns:
            ReferenceMatch if found, None otherwise
        """
        if not self.reference_service:
            return None

        # Check cache first
        if text in self._reference_matches:
            return self._reference_matches[text]

        # Perform lookup
        match = self.reference_service.find_match(text)
        self._reference_matches[text] = match
        return match
    
    def set_semantic_similarity_service(self, service: SemanticSimilarityService) -> None:
        """
        Set the semantic similarity service for meaning-based comparison.
        
        Args:
            service: SemanticSimilarityService instance
        """
        self.semantic_similarity_service = service
        logger.info("Semantic similarity service configured for analysis")
    
    def set_hybrid_similarity_service(self, service) -> None:
        """
        Set the hybrid similarity service for enhanced multi-method matching.
        
        Args:
            service: HybridSimilarityService instance
        """
        self.hybrid_similarity_service = service
        self._hybrid_enabled = service is not None
        logger.info("Hybrid similarity service configured for analysis (v3.0 semantic enhancement)")
    
    def set_custom_instructions_service(self, service) -> None:
        """
        Set the custom instructions service for user-defined rules (Step 0.5).

        Args:
            service: CustomInstructionsService instance
        """
        self.custom_instructions_service = service
        if service and service.is_loaded:
            logger.info(f"Custom instructions service configured: {service.instruction_count} regels")

    def set_reranking_service(self, service) -> None:
        """
        Set the LLM reranking service for uncertain match enhancement (v4.3).

        The reranking service is used to boost confidence in matches that fall
        within the uncertain range (0.70-0.85 similarity). It uses cross-encoder
        or LLM-based scoring to determine if an uncertain match is actually correct.

        Args:
            service: ReRankingService instance
        """
        self.reranking_service = service
        # Check if reranking is enabled in config
        self._reranking_enabled = (
            service is not None and
            hasattr(self.config, 'ai') and
            hasattr(self.config.ai, 'reranking') and
            self.config.ai.reranking.enabled
        )
        if self._reranking_enabled:
            logger.info("✅ LLM Reranking service configured (v4.3 uncertain match enhancement)")
        elif service is not None:
            logger.info("ℹ️ Reranking service provided but disabled in config (ai.reranking.enabled=False)")
    
    def _index_sections_for_semantic_search(self) -> None:
        """
        Index policy sections for semantic similarity search.
        
        Pre-computes embeddings for all sections to enable fast
        semantic matching during analysis.
        """
        if not self.semantic_similarity_service:
            logger.debug("Semantic similarity service not configured, skipping indexing")
            return
        
        if not self.semantic_similarity_service.is_available:
            logger.warning("Semantic similarity service not available (missing dependencies)")
            return
        
        if not self._policy_sections:
            logger.debug("No policy sections to index")
            return
        
        logger.info(f"Indexing {len(self._policy_sections)} sections for semantic search...")
        
        # Build texts dictionary with section IDs
        texts = {}
        metadata = {}
        
        for section in self._policy_sections:
            if section.simplified_text and len(section.simplified_text) > 10:
                texts[section.id] = section.simplified_text
                metadata[section.id] = {
                    'title': section.title,
                    'raw_text': section.raw_text[:500] if section.raw_text else "",
                    'page': section.page_number
                }
        
        if texts:
            try:
                self.semantic_similarity_service.index_texts(texts, metadata)
                self._semantic_index_ready = True
                logger.info(f"✅ Semantic index ready: {len(texts)} sections indexed")
            except Exception as e:
                logger.error(f"Failed to build semantic index: {e}")
                self._semantic_index_ready = False
        else:
            logger.warning("No valid sections to index for semantic search")
    
    def analyze_clusters(
        self,
        clusters: List[Cluster],
        policy_sections: Optional[List[PolicyDocumentSection]] = None,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, AnalysisAdvice]:
        """
        Analyze all clusters using the 3-step waterfall pipeline.
        
        Args:
            clusters: List of Cluster objects
            policy_sections: List of policy document sections (voorwaarden/clausules)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping cluster_id -> AnalysisAdvice
        """
        logger.info(f"Analyzing {len(clusters)} clusters with waterfall pipeline")
        
        # Store policy sections for comparison
        self._policy_sections = policy_sections or []
        self._policy_section_lookup = {s.id: s for s in self._policy_sections if s and s.id}
        
        # Build combined policy text for substring matching
        if self._policy_sections:
            self._policy_full_text = " ".join(
                s.simplified_text for s in self._policy_sections if s.simplified_text
            )
            logger.info(f"Loaded {len(self._policy_sections)} policy sections for comparison")
            
            # Train hybrid similarity (TF-IDF) on voorwaarden if available
            if self.hybrid_similarity_service:
                section_texts = [s.simplified_text for s in self._policy_sections if s.simplified_text]
                if section_texts:
                    self.hybrid_similarity_service.train_tfidf(section_texts)
                    logger.info(f"✅ Hybrid similarity trained on {len(section_texts)} sections")
        else:
            self._policy_full_text = ""
            logger.warning("⚠️ GEEN VOORWAARDEN GELADEN - Step 2 wordt overgeslagen")
        
        # Log clause library status
        if self.clause_library_service and self.clause_library_service.is_loaded:
            logger.info(f"✅ Clause library loaded: {self.clause_library_service.clause_count} clauses")
        else:
            logger.warning("⚠️ GEEN CLAUSULEBIBLIOTHEEK - Step 1 wordt overgeslagen")
        
        # Log admin check status
        if self.admin_check_service:
            logger.info("✅ Admin check service configured (Step 0 active)")
        else:
            logger.info("ℹ️ Admin check service not configured - Step 0 wordt overgeslagen")
        
        # Log custom instructions status (Step 0.5)
        if self.custom_instructions_service and self.custom_instructions_service.is_loaded:
            logger.info(f"✅ Custom instructions loaded: {self.custom_instructions_service.instruction_count} regels (Step 0.5 active)")
        else:
            logger.info("ℹ️ Geen custom instructions - Step 0.5 wordt overgeslagen")
        
        # Index sections for semantic search (Step 2b)
        if self.semantic_similarity_service:
            self._index_sections_for_semantic_search()
            if self._semantic_index_ready:
                logger.info("✅ Semantic similarity enabled (Step 2b active)")
            else:
                logger.warning("⚠️ Semantic indexing failed - Step 2b wordt overgeslagen")
        else:
            logger.info("ℹ️ Semantic similarity service not configured - alleen tekstuele matching")
        
        # Log hybrid similarity status (v3.0)
        if self._hybrid_enabled:
            stats_info = self.hybrid_similarity_service.get_statistics() if hasattr(self.hybrid_similarity_service, 'get_statistics') else {}
            services_available = stats_info.get('services_available', {})
            active_methods = [k for k, v in services_available.items() if v]
            logger.info(f"✅ Hybrid similarity enabled: {', '.join(active_methods) if active_methods else 'basic'}")
        else:
            logger.info("ℹ️ Hybrid similarity not configured - using RapidFuzz only")

        # Log LLM reranking status (v4.3)
        if self._reranking_enabled:
            rerank_config = self.config.ai.reranking
            logger.info(
                f"✅ LLM Reranking enabled (v4.3): "
                f"uncertain range [{rerank_config.uncertain_min_threshold:.0%}-{rerank_config.uncertain_max_threshold:.0%}], "
                f"llm_weight={rerank_config.llm_weight:.0%}"
            )
            # Reset reranking stats for this run
            self._reranking_stats = {
                'total_reranked': 0,
                'score_improvements': 0,
                'avg_score_boost': 0.0
            }
        else:
            logger.info("ℹ️ LLM Reranking not enabled - uncertain matches use similarity score only")

        advice_map: Dict[str, AnalysisAdvice] = {}
        total = len(clusters)

        # Track statistics per step
        stats = {
            'step0_admin_issues': 0,
            'step05_custom_instructions': 0,  # Custom user instructions match
            'step1_library_match': 0,
            'step2_conditions_match': 0,
            'step2_semantic_match': 0,  # Semantic matches (embedding + LLM verified)
            'step3_fallback': 0,
            'multi_clause': 0
        }

        # TIMING: Track time per phase
        import time
        analysis_start = time.time()
        step_times = {'step0': 0.0, 'step05': 0.0, 'step1': 0.0, 'step2': 0.0, 'step3': 0.0}

        for i, cluster in enumerate(clusters):
            # Progress update
            if progress_callback and i % 20 == 0:
                progress_callback(int(i / total * 100))

            advice = self._analyze_with_waterfall(cluster, stats, step_times)
            advice_map[cluster.id] = advice

            # Log timing every 100 clusters
            if (i + 1) % 100 == 0:
                elapsed = time.time() - analysis_start
                avg_per_cluster = elapsed / (i + 1)
                remaining = avg_per_cluster * (total - i - 1)
                logger.info(f"⏱️ TIMING [{i+1}/{total}]: {elapsed:.1f}s elapsed, ~{remaining:.1f}s remaining")
                logger.info(f"   Step times: s0={step_times['step0']:.1f}s, s0.5={step_times['step05']:.1f}s, s1={step_times['step1']:.1f}s, s2={step_times['step2']:.1f}s, s3={step_times['step3']:.1f}s")

        # Final progress
        if progress_callback:
            progress_callback(100)

        # Log final timing summary
        total_time = time.time() - analysis_start
        logger.info(f"⏱️ ANALYSIS COMPLETE: {total_time:.1f}s for {total} clusters ({total_time/total*1000:.1f}ms/cluster)")
        logger.info(f"   STEP BREAKDOWN: Step0={step_times['step0']:.1f}s, Step0.5={step_times['step05']:.1f}s, Step1={step_times['step1']:.1f}s, Step2={step_times['step2']:.1f}s, Step3={step_times['step3']:.1f}s")

        # Log summary
        self._log_analysis_summary(advice_map, stats)

        # Log performance stats (v3.3)
        if self._hybrid_enabled and hasattr(self.hybrid_similarity_service, 'log_performance_summary'):
            self.hybrid_similarity_service.log_performance_summary()

        return advice_map
    
    def analyze_text_segment(
        self,
        text: str,
        segment_id: str,
        cluster_name: str = "",
        frequency: int = 1,
        policy_sections: Optional[List[PolicyDocumentSection]] = None
    ) -> AnalysisAdvice:
        """
        Analyze a single text segment (for sub-clause analysis).
        
        Creates a temporary cluster and analyzes it using the waterfall pipeline.
        
        Args:
            text: Text segment to analyze
            segment_id: Unique identifier for this segment
            cluster_name: Optional cluster name
            frequency: Frequency (default 1 for segments)
            policy_sections: Optional policy sections for context (uses stored if not provided)
            
        Returns:
            AnalysisAdvice for this segment
        """
        from ..domain.clause import Clause
        
        # Create temporary clause
        temp_clause = Clause(
            id=segment_id,
            raw_text=text,
            simplified_text=simplify_text(text)
        )
        
        # Create temporary cluster
        temp_cluster = Cluster(
            id=segment_id,
            leader_clause=temp_clause,
            member_ids=[],
            frequency=frequency,
            name=cluster_name or f"Segment {segment_id}"
        )
        
        # Use provided policy sections or stored ones
        if policy_sections is None:
            policy_sections = self._policy_sections
        
        # Analyze using waterfall pipeline (without stats tracking)
        stats = {
            'step0_admin_issues': 0,
            'step05_custom_instructions': 0,
            'step1_library_match': 0,
            'step2_conditions_match': 0,
            'step3_fallback': 0,
            'multi_clause': 0
        }
        
        return self._analyze_with_waterfall(temp_cluster, stats)
    
    def _analyze_with_waterfall(
        self,
        cluster: Cluster,
        stats: dict,
        step_times: dict = None
    ) -> AnalysisAdvice:
        """
        Analyze a single cluster using the 4-step waterfall pipeline.

        Args:
            cluster: Cluster to analyze
            stats: Statistics dictionary to update
            step_times: Optional timing dictionary to track time per step

        Returns:
            AnalysisAdvice for this cluster
        """
        # Use strategy pipeline if available and enabled (v4.5)
        if self._use_pipeline and self.pipeline is not None:
            try:
                context = self._build_analysis_context().build()
                advice = self.pipeline.analyze_cluster(cluster, context)
                # Update stats based on advice category
                self._update_stats_from_advice(advice, stats)
                return advice
            except Exception as e:
                logger.warning(f"Pipeline failed for cluster {cluster.id}, falling back: {e}")
                # Fall through to legacy waterfall

        import time
        text = cluster.original_text
        simple_text = cluster.leader_text
        frequency = cluster.frequency

        # ============================================================
        # STEP 0: ADMIN CHECK (Hygiene issues)
        # Checks: empty, placeholders, dates in past, encoding issues
        # ============================================================
        t0 = time.time()
        if self.admin_check_service:
            admin_result, admin_advice = self.admin_check_service.check_cluster(cluster)
            if admin_advice:
                stats['step0_admin_issues'] += 1
                if step_times: step_times['step0'] += time.time() - t0
                logger.debug(f"Step 0 hit: {admin_advice.advice_code} for cluster {cluster.id}")
                return admin_advice
        if step_times: step_times['step0'] += time.time() - t0

        # ============================================================
        # STEP 0.5: CUSTOM INSTRUCTIONS CHECK (User-defined rules)
        # Matches input text against user-provided instructions semantically
        # ============================================================
        t05 = time.time()
        custom_advice = self._step05_custom_instructions_check(cluster)
        if custom_advice:
            stats['step05_custom_instructions'] += 1
            if step_times: step_times['step05'] += time.time() - t05
            return custom_advice
        if step_times: step_times['step05'] += time.time() - t05

        # ============================================================
        # PRE-CHECK: Skip very short texts
        # (Note: this is also checked by AdminCheckService, but kept as fallback)
        # ============================================================
        if len(simple_text) < 10:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason="Tekst te kort voor automatische analyse.",
                confidence=ConfidenceLevel.LAAG.value,
                reference_article="-",
                category="SHORT_TEXT",
                cluster_name=cluster.name,
                frequency=frequency
            )

        # ============================================================
        # PRE-CHECK: Text length check (NEW - simplified)
        # If text is too long, flag for manual check (no automatic splitting)
        # ============================================================
        if len(text) > self.config.analysis_rules.max_text_length:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"Tekst te lang voor automatische analyse ({len(text)} karakters, max {self.config.analysis_rules.max_text_length})",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="-",
                category="LONG_TEXT",
                cluster_name=cluster.name,
                frequency=frequency
            )

        # ============================================================
        # STEP 1: CLAUSE LIBRARY CHECK
        # Check if text matches a standard clause -> REPLACE
        # ============================================================
        t1 = time.time()
        library_advice = self._step1_clause_library_check(cluster)
        if library_advice:
            stats['step1_library_match'] += 1
            if step_times: step_times['step1'] += time.time() - t1
            return library_advice
        if step_times: step_times['step1'] += time.time() - t1

        # ============================================================
        # STEP 2: POLICY CONDITIONS CHECK
        # Check if text is covered by conditions -> DELETE
        # ============================================================
        t2 = time.time()
        conditions_advice = self._step2_conditions_check(cluster)
        if conditions_advice:
            stats['step2_conditions_match'] += 1
            if step_times: step_times['step2'] += time.time() - t2
            return conditions_advice
        if step_times: step_times['step2'] += time.time() - t2
        
        # ============================================================
        # STEP 3: FALLBACK ANALYSIS
        # Keyword rules, frequency, or AI analysis
        # ============================================================
        t3 = time.time()
        stats['step3_fallback'] += 1
        result = self._step3_fallback_analysis(cluster)
        if step_times: step_times['step3'] += time.time() - t3
        return result
    
    def _step05_custom_instructions_check(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """
        STEP 0.5: Check against custom user instructions.
        
        User-defined rules are matched semantically against the input text.
        If a match is found, the custom action from the user is returned.
        
        Args:
            cluster: Cluster to check
            
        Returns:
            AnalysisAdvice with custom action if match found, None otherwise
        """
        if not self.custom_instructions_service or not self.custom_instructions_service.is_loaded:
            logger.debug(f"Step 0.5: Skipped for cluster {cluster.id} (no service or not loaded)")
            return None
        
        text = cluster.original_text
        if not text or len(text) < 10:
            logger.debug(f"Step 0.5: Skipped for cluster {cluster.id} (text too short: {len(text)} chars)")
            return None
        
        logger.debug(f"Step 0.5: Checking cluster {cluster.id} (text: '{text[:80]}...')")
        
        # Find matching custom instruction
        match = self.custom_instructions_service.find_match(text)
        
        if match is None:
            logger.debug(
                f"Step 0.5: ❌ No match for cluster {cluster.id} "
                f"(text: '{text[:50]}...', {self.custom_instructions_service.instruction_count} instructions available)"
            )
            return None
        
        # Create advice with the custom action from the user
        logger.info(
            f"Step 0.5: ✅ MATCH for cluster {cluster.id}! "
            f"(score: {match.score:.2f}, action: '{match.instruction.action}')"
        )
        
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=f"📋 {match.instruction.action}",
            reason=f"Komt overeen met instructie: '{match.instruction.search_text}' ({int(match.score*100)}% match)",
            confidence=ConfidenceLevel.HOOG.value if match.score >= 0.85 else ConfidenceLevel.MIDDEN.value,
            reference_article="Custom instructie",
            category="CUSTOM_INSTRUCTION",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )
    
    def _step1_clause_library_check(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """
        STEP 1: Check against the clause library.
        
        If a free text closely matches a standard clause, recommend replacing
        it with the standard clause code.
        
        Args:
            cluster: Cluster to check
            
        Returns:
            AnalysisAdvice if match found, None otherwise
        """
        if not self.clause_library_service or not self.clause_library_service.is_loaded:
            return None
        
        # Find best match in clause library
        match = self.clause_library_service.find_match(cluster.leader_text)
        
        if match is None:
            return None
        
        # High confidence match (>95%) -> REPLACE
        if match.is_replacement_candidate:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code="🔄 VERVANGEN",
                reason=f"Komt overeen met standaardclausule {match.clause.code} ({int(match.similarity_score*100)}% match). Vervang door deze standaardcode.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article=match.clause.code,
                category="LIBRARY_EXACT_MATCH",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # Medium confidence match (85-95%) -> REVIEW
        if match.is_review_candidate:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code="🔍 CONTROLEER GELIJKENIS",
                reason=f"Lijkt sterk op standaardclausule {match.clause.code} ({int(match.similarity_score*100)}% match). Controleer of vervanging mogelijk is.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=match.clause.code,
                category="LIBRARY_HIGH_SIMILARITY",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # Lower match - don't return advice, continue to step 2
        return None
    
    def _step2_conditions_check(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """
        STEP 2: Check against policy conditions.
        
        If a free text is already covered by the conditions, it's redundant
        and can be deleted.
        
        Args:
            cluster: Cluster to check
            
        Returns:
            AnalysisAdvice if match found, None otherwise
        """
        if not self._policy_sections:
            return None
        
        simple_text = cluster.leader_text
        
        if not simple_text or len(simple_text) < 20:
            return None
        
        # Strategy 1: Exact substring match
        if self._policy_full_text and simple_text in self._policy_full_text:
            matching_section = self._find_matching_section(simple_text)
            # Only return a reference if we can attribute it to a specific section.
            # If the match spans section boundaries (rare but possible due to concatenation),
            # fall back to Strategy 2 to obtain a concrete section reference.
            if matching_section:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst komt EXACT voor in de voorwaarden. Kan verwijderd worden.",
                    confidence=ConfidenceLevel.HOOG.value,
                    reference_article=self._format_section_reference(matching_section),
                    category="CONDITIONS_EXACT",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
        
        # Strategy 2: Fuzzy match per section
        best_match = self._find_best_section_match(simple_text)
        
        if best_match:
            score, section = best_match
            section_ref = self._format_section_reference(section)

            # Score interpretation depends on whether hybrid similarity was used
            # Hybrid similarity (multi-method) typically scores 0.10-0.20 lower than pure RapidFuzz
            # for the same semantic similarity level

            if score >= self.EXACT_MATCH_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst komt bijna letterlijk voor in voorwaarden ({int(score*100)}% match). Kan verwijderd worden.",
                    confidence=ConfidenceLevel.HOOG.value,
                    reference_article=section_ref,
                    category="CONDITIONS_NEAR_EXACT",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )

            elif score >= self.HIGH_SIMILARITY_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst lijkt sterk op {section_ref} ({int(score*100)}% match). Controleer en verwijder indien identiek.",
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=section_ref,
                    category="CONDITIONS_HIGH_SIMILARITY",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )

            elif score >= self.MEDIUM_SIMILARITY_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason=f"Vertoont gelijkenis met {section_ref} ({int(score*100)}% match). Controleer of dit een variant is.",
                    confidence=ConfidenceLevel.LAAG.value,
                    reference_article=section_ref,
                    category="CONDITIONS_MEDIUM_SIMILARITY",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )

            elif score >= 0.50:
                # NEW: Lower threshold for hybrid similarity matches (paraphrases)
                # Scores 0.50-0.75 from hybrid similarity often indicate semantic similarity
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason=f"Mogelijke overlap met {section_ref} ({int(score*100)}% semantische match). Controleer of betekenis identiek is.",
                    confidence=ConfidenceLevel.LAAG.value,
                    reference_article=section_ref,
                    category="CONDITIONS_SEMANTIC_MATCH",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
        
        # Strategy 3: Fragment matching
        fragment_result = self._check_significant_fragments(simple_text)
        if fragment_result and fragment_result.get('match_found'):
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=fragment_result['reason'],
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=fragment_result['reference_article'],
                category="CONDITIONS_FRAGMENTS",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # Strategy 4: SEMANTIC MATCHING (NEW!)
        # Uses embeddings to find texts with same MEANING, even if written differently
        semantic_advice = self._step2b_semantic_check(cluster)
        if semantic_advice:
            return semantic_advice
        
        return None
    
    def _step2b_semantic_check(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """
        STEP 2b: Semantic similarity check.
        
        Uses embeddings to find policy sections with the same MEANING,
        even when the text is written differently.
        
        If a high-confidence semantic match is found, uses LLM to verify
        that the texts truly have the same meaning.
        
        Args:
            cluster: Cluster to check
            
        Returns:
            AnalysisAdvice if semantic match found and verified, None otherwise
        """
        # Check if semantic similarity is available and ready
        if not self.semantic_similarity_service or not self._semantic_index_ready:
            return None
        
        simple_text = cluster.leader_text
        if not simple_text or len(simple_text) < 20:
            return None
        
        # Find semantically similar sections
        matches = self.semantic_similarity_service.find_similar(
            simple_text,
            top_k=3,
            min_score=self.SEMANTIC_MATCH_THRESHOLD
        )
        
        if not matches:
            return None
        
        best_match = matches[0]
        logger.debug(
            f"Semantic match found for cluster {cluster.id}: "
            f"{best_match.text_id} (score: {best_match.score:.2f})"
        )
        
        # If we have an AI analyzer with LLM, verify the match
        if self.ai_analyzer and hasattr(self.ai_analyzer, 'verify_semantic_match'):
            return self._verify_and_create_semantic_advice(cluster, best_match)
        
        # Without LLM verification, only accept very high similarity matches
        if best_match.score >= self.SEMANTIC_HIGH_THRESHOLD:
            # Prefer section lookup (contains document_id/page_number). Fall back to metadata if needed.
            section = self._policy_section_lookup.get(best_match.text_id)
            ref = self._format_section_reference(section) if section else (
                f"{best_match.text_id} – {best_match.metadata.get('title')}" if best_match.metadata and best_match.metadata.get('title') else best_match.text_id
            )
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Semantisch identiek aan {ref} ({int(best_match.score*100)}% betekenis-match). Tekst heeft dezelfde betekenis als de voorwaarden.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=ref,
                category="CONDITIONS_SEMANTIC_MATCH",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # For lower scores without LLM, suggest manual review
        section = self._policy_section_lookup.get(best_match.text_id)
        ref = self._format_section_reference(section) if section else (
            f"{best_match.text_id} – {best_match.metadata.get('title')}" if best_match.metadata and best_match.metadata.get('title') else best_match.text_id
        )
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason=f"Mogelijke semantische overlap met {ref} ({int(best_match.score*100)}% betekenis-match). Controleer of de betekenis identiek is.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article=ref,
            category="CONDITIONS_SEMANTIC_POSSIBLE",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )
    
    def _verify_and_create_semantic_advice(
        self, 
        cluster: Cluster, 
        match: SemanticMatch
    ) -> Optional[AnalysisAdvice]:
        """
        Verify semantic match with LLM and create appropriate advice.
        
        Args:
            cluster: The cluster being analyzed
            match: The semantic match to verify
            
        Returns:
            AnalysisAdvice if verification succeeds, None otherwise
        """
        try:
            # Get the matched section's text
            conditions_text = match.matched_text
            policy_text = cluster.leader_text
            article_ref = match.text_id
            section = self._policy_section_lookup.get(match.text_id)
            formatted_ref = self._format_section_reference(section) if section else article_ref
            
            # Call LLM to verify
            verification = self.ai_analyzer.verify_semantic_match(
                conditions_text=conditions_text,
                policy_text=policy_text,
                article_ref=article_ref
            )
            
            if verification.is_same_meaning:
                # LLM confirms same meaning -> DELETE
                confidence = ConfidenceLevel.HOOG.value if verification.confidence > 0.8 else ConfidenceLevel.MIDDEN.value
                
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Semantisch identiek aan {formatted_ref} ({int(match.score*100)}% match, LLM bevestigd). {verification.explanation}",
                    confidence=confidence,
                    reference_article=formatted_ref,
                    category="CONDITIONS_SEMANTIC_VERIFIED",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            else:
                # LLM says different meaning -> manual check
                if verification.differences:
                    reason = f"Lijkt op {formatted_ref} maar heeft andere betekenis: {verification.differences}"
                else:
                    reason = f"Lijkt op {formatted_ref} maar LLM ziet belangrijke verschillen. {verification.explanation}"
                
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason=reason,
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=formatted_ref,
                    category="CONDITIONS_SEMANTIC_DIFFERENT",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
                
        except Exception as e:
            logger.warning(f"LLM semantic verification failed: {e}")
            # Fall back to embedding-only result
            if match.score >= self.SEMANTIC_HIGH_THRESHOLD:
                section = self._policy_section_lookup.get(match.text_id)
                formatted_ref = self._format_section_reference(section) if section else match.text_id
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Semantisch identiek aan {formatted_ref} ({int(match.score*100)}% betekenis-match). LLM verificatie mislukt, maar score is hoog.",
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=formatted_ref,
                    category="CONDITIONS_SEMANTIC_MATCH",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            return None
    
    def _step3_fallback_analysis(self, cluster: Cluster) -> AnalysisAdvice:
        """
        STEP 3: Fallback analysis when no library/conditions match.
        
        Uses keyword rules, frequency analysis, or AI analysis.
        
        Args:
            cluster: Cluster to analyze
            
        Returns:
            AnalysisAdvice
        """
        text = cluster.original_text
        simple_text = cluster.leader_text
        frequency = cluster.frequency
        
        # NOTE: Long text check is already done in _analyze_with_waterfall (Step PRE-CHECK)
        # This function only handles fallback analysis for normal-length texts
        
        # Keyword-based rules
        keyword_advice = self._check_keyword_rules(cluster, simple_text)
        if keyword_advice:
            return keyword_advice
        
        # Frequency-based standardization (with reference check)
        threshold = self.config.analysis_rules.frequency_standardize_threshold

        # Check reference analysis for frequency inheritance
        ref_match = self._get_reference_match(simple_text)

        # If reference had enough frequency, recommend standardization
        if ref_match and self.reference_service:
            ref_freq = ref_match.reference_clause.frequency
            if ref_freq >= threshold:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.STANDAARDISEREN.value,
                    reason=f"Komt {frequency}x voor (jaaroverzicht: {ref_freq}x). "
                           f"Volgens referentie-analyse standaardiseren.",
                    confidence=ConfidenceLevel.HOOG.value,
                    reference_article="Ref: Standaardiseren",
                    category="FREQUENT_REF",
                    cluster_name=cluster.name,
                    frequency=frequency
                )

        # Original frequency check
        if frequency >= threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.STANDAARDISEREN.value,
                reason=f"Komt vaak voor ({frequency}x). Maak hiervan een standaard clausulecode.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="Nieuw",
                category="FREQUENT",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        # AI analysis (if available)
        if self.ai_analyzer:
            ai_advice = self._try_ai_analysis(cluster)
            if ai_advice:
                return ai_advice
        
        # Final fallback based on mode
        if not self._policy_sections:
            return self._internal_analysis_fallback(cluster, frequency)
        
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason="Geen automatische match gevonden. Beoordeel handmatig of dit maatwerk is.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="NO_MATCH",
            cluster_name=cluster.name,
            frequency=frequency
        )
    
    def _find_best_section_match(
        self,
        text: str
    ) -> Optional[Tuple[float, PolicyDocumentSection]]:
        """
        Find the best matching section in the conditions.

        Uses hybrid similarity's find_best_match for efficient batch processing.
        Falls back to loop-based RapidFuzz if hybrid service not available.

        v4.3: Integrates LLM reranking for uncertain matches (0.70-0.85 range).
        When a match falls in this uncertain range, the reranking service is used
        to boost or penalize the score based on semantic relevance.
        """
        if not self._policy_sections:
            return None

        # OPTIMIZED: Use hybrid service's batch matching
        if self._hybrid_enabled and self.hybrid_similarity_service:
            sections_with_text = [s for s in self._policy_sections if s.simplified_text]
            candidates = [s.simplified_text for s in sections_with_text]
            if not candidates:
                return None

            # FIXED: Lower threshold for hybrid similarity (paraphrases score 0.50-0.70)
            # Hybrid combines multiple methods, so threshold should be lower than pure RapidFuzz
            hybrid_threshold = 0.50  # Was: MEDIUM_SIMILARITY_THRESHOLD (0.75) - too high!

            match_result = self.hybrid_similarity_service.find_best_match(
                query=text,
                candidates=candidates,
                min_score=hybrid_threshold
            )

            if match_result:
                best_idx, best_score, _ = match_result
                # IMPORTANT: best_idx refers to the candidates list, not the full _policy_sections list
                best_section = sections_with_text[best_idx]

                # Also check for substring match (exact match bonus)
                if text in best_section.simplified_text:
                    substring_score = min(1.0, 0.95 + (len(text) / len(best_section.simplified_text)) * 0.05)
                    if substring_score > best_score:
                        best_score = substring_score

                # ============================================================
                # v4.3: LLM RERANKING FOR UNCERTAIN MATCHES
                # If score is in uncertain range (0.70-0.85), use LLM reranking
                # to boost confidence or demote false positives
                # ============================================================
                best_score = self._apply_llm_reranking(
                    text, best_section.simplified_text, best_score
                )

                return (best_score, best_section)

            return None

        # FALLBACK: Loop-based RapidFuzz matching (when hybrid not available)
        # OPTIMIZED v3.3: Two-stage filtering for faster matching
        PRE_SCREEN_THRESHOLD = 0.40
        TOP_CANDIDATES = 10

        # Stage 1: Quick pre-screening
        pre_scores = []
        for idx, section in enumerate(self._policy_sections):
            if not section.simplified_text:
                continue

            # Check substring match first (instant match)
            if text in section.simplified_text:
                substring_score = min(1.0, 0.95 + (len(text) / len(section.simplified_text)) * 0.05)
                return (substring_score, section)

            # Quick RapidFuzz score
            score = self.similarity_service.similarity(text, section.simplified_text)
            if score >= PRE_SCREEN_THRESHOLD:
                pre_scores.append((idx, score, section))

        if not pre_scores:
            return None

        # Sort and take top candidates
        pre_scores.sort(key=lambda x: x[1], reverse=True)
        top_candidates = pre_scores[:TOP_CANDIDATES]

        # Stage 2: Find best among top candidates (already computed)
        best_idx, best_score, best_section = top_candidates[0]

        if best_section and best_score >= self.MEDIUM_SIMILARITY_THRESHOLD:
            # v4.3: Apply LLM reranking for uncertain matches
            best_score = self._apply_llm_reranking(
                text, best_section.simplified_text, best_score
            )
            return (best_score, best_section)

        return None

    def _apply_llm_reranking(
        self,
        query_text: str,
        candidate_text: str,
        similarity_score: float
    ) -> float:
        """
        Apply LLM reranking to boost or penalize uncertain matches (v4.3).

        When a similarity score falls in the uncertain range (default: 0.70-0.85),
        the reranking service uses cross-encoder or LLM-based scoring to determine
        if the match is semantically correct.

        The final score is a weighted blend:
            final = (1 - llm_weight) * similarity + llm_weight * llm_score

        Args:
            query_text: The clause text being analyzed
            candidate_text: The matched policy section text
            similarity_score: The initial similarity score from hybrid matching

        Returns:
            Adjusted similarity score (may be higher or lower than original)
        """
        # Check if reranking is enabled and available
        if not self._reranking_enabled or not self.reranking_service:
            return similarity_score

        # Get config thresholds
        rerank_config = self.config.ai.reranking
        min_threshold = rerank_config.uncertain_min_threshold
        max_threshold = rerank_config.uncertain_max_threshold

        # Only rerank uncertain matches (within the configured range)
        if similarity_score < min_threshold or similarity_score >= max_threshold:
            # Score is either too low (no match) or high enough (confident match)
            # Skip reranking to save time
            return similarity_score

        try:
            # Get LLM/cross-encoder score for this pair
            llm_score = self.reranking_service.score_pair(query_text, candidate_text)

            # Check minimum rerank score
            if llm_score < rerank_config.min_rerank_score:
                # LLM says this is not a good match, don't boost
                logger.debug(
                    f"LLM rerank: demoting match (sim={similarity_score:.2f}, llm={llm_score:.2f})"
                )
                # Reduce score slightly but don't completely discard
                return similarity_score * 0.9

            # Blend similarity score with LLM score
            llm_weight = rerank_config.llm_weight
            final_score = (1 - llm_weight) * similarity_score + llm_weight * llm_score

            # Track statistics
            self._reranking_stats['total_reranked'] += 1
            if final_score > similarity_score:
                self._reranking_stats['score_improvements'] += 1
                boost = final_score - similarity_score
                # Update running average of boost
                n = self._reranking_stats['total_reranked']
                prev_avg = self._reranking_stats['avg_score_boost']
                self._reranking_stats['avg_score_boost'] = prev_avg + (boost - prev_avg) / n

            logger.debug(
                f"LLM rerank: {similarity_score:.2f} -> {final_score:.2f} "
                f"(llm={llm_score:.2f}, weight={llm_weight:.0%})"
            )

            return final_score

        except Exception as e:
            logger.warning(f"LLM reranking failed: {e}, using original score")
            return similarity_score

    def _check_significant_fragments(self, text: str) -> Optional[dict]:
        """Check if significant fragments appear in conditions."""
        if not self._policy_full_text or len(text) < 50:
            return None
        
        sentences = re.split(r'[.!?]\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return None
        
        matches_found = 0
        matching_refs = set()
        
        for sentence in sentences:
            if sentence in self._policy_full_text:
                matches_found += 1
                section = self._find_matching_section(sentence)
                if section:
                    matching_refs.add(self._format_section_reference(section))
        
        match_ratio = matches_found / len(sentences) if sentences else 0
        
        if match_ratio >= 0.5 and matches_found >= 2:
            articles_str = ", ".join(sorted(matching_refs)) if matching_refs else "Voorwaarden"
            return {
                'match_found': True,
                'reason': f"Meerdere zinnen ({matches_found}/{len(sentences)}) komen voor in voorwaarden.",
                'reference_article': articles_str,
                'category': "CONDITIONS_FRAGMENTS"
            }
        
        return None
    
    def _check_keyword_rules(
        self, 
        cluster: Cluster, 
        simple_text: str
    ) -> Optional[AnalysisAdvice]:
        """Check keyword-based rules from configuration."""
        rules = self.config.analysis_rules.keyword_rules
        
        for rule_name, rule_config in rules.items():
            keywords = rule_config.get('keywords', [])
            
            if not any(kw in simple_text for kw in keywords):
                continue
            
            inclusion_keywords = rule_config.get('inclusion_keywords')
            if inclusion_keywords:
                if not any(kw in simple_text for kw in inclusion_keywords):
                    continue
            
            max_length = rule_config.get('max_length')
            if max_length and len(simple_text) > max_length:
                continue
            
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=rule_config.get('advice', 'HANDMATIG CHECKEN'),
                reason=rule_config.get('reason', 'Keyword match'),
                confidence=rule_config.get('confidence', 'Midden'),
                reference_article=rule_config.get('article', '-'),
                category=f"KEYWORD_{rule_name.upper()}",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        return None
    
    def _try_ai_analysis(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """Try AI-enhanced analysis if available."""
        if not self.ai_analyzer:
            return None
        
        try:
            return self.ai_analyzer.analyze_cluster_with_context(
                cluster, 
                self._policy_sections
            )
        except Exception as e:
            logger.warning(f"AI analysis failed for cluster {cluster.id}: {e}")
            return None
    
    def _internal_analysis_fallback(self, cluster: Cluster, frequency: int) -> AnalysisAdvice:
        """Provide useful analysis when no conditions are uploaded."""
        if frequency == 1:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.UNIEK.value,
                reason="Komt slechts 1x voor. Mogelijk maatwerk of eenmalige afwijking.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="UNIQUE",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        if frequency <= 5:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.CONSISTENTIE_CHECK.value,
                reason=f"Komt {frequency}x voor. Controleer of dit varianten zijn van dezelfde clausule.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="LOW_FREQUENCY",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        if frequency < self.config.analysis_rules.frequency_standardize_threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.FREQUENTIE_INFO.value,
                reason=f"Komt {frequency}x voor. Onder standaardisatie-drempel ({self.config.analysis_rules.frequency_standardize_threshold}).",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="MEDIUM_FREQUENCY",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.FREQUENTIE_INFO.value,
            reason=f"Komt {frequency}x voor.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="FREQUENCY_INFO",
            cluster_name=cluster.name,
            frequency=frequency
        )
    
    def _log_analysis_summary(self, advice_map: Dict[str, AnalysisAdvice], stats: dict) -> None:
        """Log summary of analysis results."""
        counts = {}
        categories = {}
        
        # Count semantic matches from categories
        semantic_matches = 0
        
        for advice in advice_map.values():
            code = advice.advice_code
            counts[code] = counts.get(code, 0) + 1
            
            cat = advice.category
            categories[cat] = categories.get(cat, 0) + 1
            
            # Track semantic matches
            if cat and 'SEMANTIC' in cat:
                semantic_matches += 1
        
        logger.info("=" * 60)
        logger.info("WATERFALL PIPELINE SAMENVATTING")
        logger.info("=" * 60)
        logger.info(f"Step 0   - Admin issues (hygiëne): {stats.get('step0_admin_issues', 0)}")
        logger.info(f"Step 0.5 - Custom instructions: {stats.get('step05_custom_instructions', 0)}")
        logger.info(f"Step 1   - Clause Library matches: {stats['step1_library_match']}")
        logger.info(f"Step 2   - Conditions matches: {stats['step2_conditions_match']}")
        logger.info(f"  └─ Waarvan semantische matches: {semantic_matches}")
        logger.info(f"Step 3   - Fallback analysis: {stats['step3_fallback']}")
        logger.info(f"Multi-clause (brei) detected: {stats['multi_clause']}")
        logger.info("")
        logger.info("Per adviestype:")
        for code, count in sorted(counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {code}: {count}")
        
        # Show semantic categories if any
        semantic_cats = {k: v for k, v in categories.items() if k and 'SEMANTIC' in k}
        if semantic_cats:
            logger.info("")
            logger.info("Semantische matches per categorie:")
            for cat, count in sorted(semantic_cats.items(), key=lambda x: -x[1]):
                logger.info(f"  {cat}: {count}")

        # Show LLM reranking statistics (v4.3)
        if self._reranking_enabled and self._reranking_stats['total_reranked'] > 0:
            logger.info("")
            logger.info("LLM Reranking statistieken (v4.3):")
            logger.info(f"  Totaal gereranked: {self._reranking_stats['total_reranked']}")
            logger.info(f"  Score verbeteringen: {self._reranking_stats['score_improvements']}")
            if self._reranking_stats['score_improvements'] > 0:
                logger.info(f"  Gem. score boost: +{self._reranking_stats['avg_score_boost']:.2%}")
    
    def add_keyword_rule(
        self,
        name: str,
        keywords: List[str],
        advice: str,
        reason: str,
        article: str = "-",
        confidence: str = "Midden",
        max_length: Optional[int] = None,
        inclusion_keywords: Optional[List[str]] = None
    ) -> None:
        """Add a new keyword rule dynamically."""
        rule = {
            'keywords': keywords,
            'advice': advice,
            'reason': reason,
            'article': article,
            'confidence': confidence
        }
        
        if max_length:
            rule['max_length'] = max_length
        if inclusion_keywords:
            rule['inclusion_keywords'] = inclusion_keywords
        
        self.config.analysis_rules.keyword_rules[name] = rule
        logger.info(f"Added keyword rule: {name}")
    
    def set_similarity_thresholds(
        self,
        exact: float = 0.95,
        high: float = 0.85,
        medium: float = 0.75
    ) -> None:
        """Adjust similarity thresholds for matching."""
        self.EXACT_MATCH_THRESHOLD = exact
        self.HIGH_SIMILARITY_THRESHOLD = high
        self.MEDIUM_SIMILARITY_THRESHOLD = medium
        logger.info(f"Updated thresholds: exact={exact}, high={high}, medium={medium}")
    
    def set_semantic_thresholds(
        self,
        match_threshold: float = 0.70,
        high_threshold: float = 0.80
    ) -> None:
        """
        Adjust semantic similarity thresholds.
        
        Args:
            match_threshold: Minimum score to consider as potential semantic match
            high_threshold: Score above which match is high confidence (no LLM needed)
        """
        self.SEMANTIC_MATCH_THRESHOLD = match_threshold
        self.SEMANTIC_HIGH_THRESHOLD = high_threshold
        logger.info(f"Updated semantic thresholds: match={match_threshold}, high={high_threshold}")
