# hienfeld/services/analysis_service.py
"""
Service for analyzing clusters and generating advice.

Implements a 4-step WATERFALL PIPELINE:
0. ADMIN CHECK - Hygiene issues (empty, outdated, placeholders) -> CLEAN/COMPLETE/DELETE
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
from ..logging_config import get_logger

logger = get_logger('analysis_service')


class AnalysisService:
    """
    Analyzes clusters and generates actionable advice.
    
    WATERFALL PIPELINE (4 STEPS):
    
    ┌─────────────────────────────────────────────────────────────┐
    │  STEP 0: ADMIN CHECK (NEW)                                  │
    │  Hygiene issues: empty, outdated dates, placeholders        │
    │  Issue found? → OPSCHONEN/AANVULLEN/VERWIJDEREN             │
    │  No issues? → Continue to Step 1                            │
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
    
    # Thresholds for matching
    EXACT_MATCH_THRESHOLD = 0.95      # Almost identical -> REPLACE/DELETE
    HIGH_SIMILARITY_THRESHOLD = 0.85   # Very similar -> REVIEW
    MEDIUM_SIMILARITY_THRESHOLD = 0.75 # Similar -> POSSIBLE MATCH
    
    # Semantic similarity thresholds
    SEMANTIC_MATCH_THRESHOLD = 0.70   # Threshold for semantic similarity (embeddings)
    SEMANTIC_HIGH_THRESHOLD = 0.80    # High confidence semantic match
    
    # Brei-detection settings
    BREI_MIN_LENGTH = 800  # Minimum text length for brei detection
    
    def __init__(
        self, 
        config: AppConfig, 
        ai_analyzer=None,
        similarity_service: Optional[SimilarityService] = None,
        semantic_similarity_service: Optional[SemanticSimilarityService] = None,
        clause_library_service=None,
        admin_check_service=None
    ):
        """
        Initialize the analysis service.
        
        Args:
            config: Application configuration
            ai_analyzer: Optional AI analyzer service for enhanced analysis
            similarity_service: Service for computing text similarity (RapidFuzz)
            semantic_similarity_service: Service for semantic/meaning-based comparison
            clause_library_service: Service for clause library lookups
            admin_check_service: Service for administrative/hygiene checks (Step 0)
        """
        self.config = config
        self.ai_analyzer = ai_analyzer
        self.clause_library_service = clause_library_service
        self.admin_check_service = admin_check_service
        
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
        
        # Cache for policy sections
        self._policy_sections: List[PolicyDocumentSection] = []
        self._policy_full_text: str = ""
    
    def set_clause_library_service(self, service) -> None:
        """
        Set the clause library service for Step 1 of the pipeline.
        
        Args:
            service: ClauseLibraryService instance
        """
        self.clause_library_service = service
        logger.info("Clause library service configured for analysis")
    
    def set_semantic_similarity_service(self, service: SemanticSimilarityService) -> None:
        """
        Set the semantic similarity service for meaning-based comparison.
        
        Args:
            service: SemanticSimilarityService instance
        """
        self.semantic_similarity_service = service
        logger.info("Semantic similarity service configured for analysis")
    
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
        
        # Build combined policy text for substring matching
        if self._policy_sections:
            self._policy_full_text = " ".join(
                s.simplified_text for s in self._policy_sections if s.simplified_text
            )
            logger.info(f"Loaded {len(self._policy_sections)} policy sections for comparison")
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
        
        # Index sections for semantic search (Step 2b)
        if self.semantic_similarity_service:
            self._index_sections_for_semantic_search()
            if self._semantic_index_ready:
                logger.info("✅ Semantic similarity enabled (Step 2b active)")
            else:
                logger.warning("⚠️ Semantic indexing failed - Step 2b wordt overgeslagen")
        else:
            logger.info("ℹ️ Semantic similarity service not configured - alleen tekstuele matching")
        
        advice_map: Dict[str, AnalysisAdvice] = {}
        total = len(clusters)
        
        # Track statistics per step
        stats = {
            'step0_admin_issues': 0,
            'step1_library_match': 0,
            'step2_conditions_match': 0,
            'step2_semantic_match': 0,  # Semantic matches (embedding + LLM verified)
            'step3_fallback': 0,
            'multi_clause': 0
        }
        
        for i, cluster in enumerate(clusters):
            # Progress update
            if progress_callback and i % 20 == 0:
                progress_callback(int(i / total * 100))
            
            advice = self._analyze_with_waterfall(cluster, stats)
            advice_map[cluster.id] = advice
        
        # Final progress
        if progress_callback:
            progress_callback(100)
        
        # Log summary
        self._log_analysis_summary(advice_map, stats)
        
        return advice_map
    
    def _analyze_with_waterfall(
        self, 
        cluster: Cluster,
        stats: dict
    ) -> AnalysisAdvice:
        """
        Analyze a single cluster using the 4-step waterfall pipeline.
        
        Args:
            cluster: Cluster to analyze
            stats: Statistics dictionary to update
            
        Returns:
            AnalysisAdvice for this cluster
        """
        text = cluster.original_text
        simple_text = cluster.leader_text
        frequency = cluster.frequency
        
        # ============================================================
        # STEP 0: ADMIN CHECK (Hygiene issues)
        # Checks: empty, placeholders, dates in past, encoding issues
        # ============================================================
        if self.admin_check_service:
            admin_result, admin_advice = self.admin_check_service.check_cluster(cluster)
            if admin_advice:
                stats['step0_admin_issues'] += 1
                logger.debug(f"Step 0 hit: {admin_advice.advice_code} for cluster {cluster.id}")
                return admin_advice
        
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
        # PRE-CHECK: Multi-clause detection (BREI) - IMPROVED
        # Now requires BOTH length > 800 AND multiple codes
        # ============================================================
        codes = re.findall(r'\b[0-9][A-Z]{2}[0-9]\b', text)
        unique_codes = set(codes)
        
        # Only flag as BREI if text is long enough AND has multiple codes
        if len(unique_codes) > 1 and len(text) > self.BREI_MIN_LENGTH:
            stats['multi_clause'] += 1
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.SPLITSEN.value,
                reason=f"Lange tekst ({len(text)} tekens) bevat {len(unique_codes)} clausulecodes ({', '.join(unique_codes)}). Splitsen aanbevolen.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="Diverse",
                category="MULTI_CLAUSE_BREI",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        # ============================================================
        # STEP 1: CLAUSE LIBRARY CHECK
        # Check if text matches a standard clause -> REPLACE
        # ============================================================
        library_advice = self._step1_clause_library_check(cluster)
        if library_advice:
            stats['step1_library_match'] += 1
            return library_advice
        
        # ============================================================
        # STEP 2: POLICY CONDITIONS CHECK
        # Check if text is covered by conditions -> DELETE
        # ============================================================
        conditions_advice = self._step2_conditions_check(cluster)
        if conditions_advice:
            stats['step2_conditions_match'] += 1
            return conditions_advice
        
        # ============================================================
        # STEP 3: FALLBACK ANALYSIS
        # Keyword rules, frequency, or AI analysis
        # ============================================================
        stats['step3_fallback'] += 1
        return self._step3_fallback_analysis(cluster)
    
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
            matching_article = self._find_matching_article(simple_text)
            
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Tekst komt EXACT voor in de voorwaarden. Kan verwijderd worden.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article=matching_article or "Voorwaarden",
                category="CONDITIONS_EXACT",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # Strategy 2: Fuzzy match per section
        best_match = self._find_best_section_match(simple_text)
        
        if best_match:
            score, section = best_match
            
            if score >= self.EXACT_MATCH_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst komt bijna letterlijk voor in voorwaarden ({int(score*100)}% match). Kan verwijderd worden.",
                    confidence=ConfidenceLevel.HOOG.value,
                    reference_article=section.id,
                    category="CONDITIONS_NEAR_EXACT",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            
            elif score >= self.HIGH_SIMILARITY_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst lijkt sterk op {section.id} ({int(score*100)}% match). Controleer en verwijder indien identiek.",
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=section.id,
                    category="CONDITIONS_HIGH_SIMILARITY",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            
            elif score >= self.MEDIUM_SIMILARITY_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason=f"Vertoont gelijkenis met {section.id} ({int(score*100)}% match). Controleer of dit een variant is.",
                    confidence=ConfidenceLevel.LAAG.value,
                    reference_article=section.id,
                    category="CONDITIONS_MEDIUM_SIMILARITY",
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
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Semantisch identiek aan {best_match.text_id} ({int(best_match.score*100)}% betekenis-match). Tekst heeft dezelfde betekenis als de voorwaarden.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=best_match.text_id,
                category="CONDITIONS_SEMANTIC_MATCH",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # For lower scores without LLM, suggest manual review
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason=f"Mogelijke semantische overlap met {best_match.text_id} ({int(best_match.score*100)}% betekenis-match). Controleer of de betekenis identiek is.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article=best_match.text_id,
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
                    reason=f"Semantisch identiek aan {article_ref} ({int(match.score*100)}% match, LLM bevestigd). {verification.explanation}",
                    confidence=confidence,
                    reference_article=article_ref,
                    category="CONDITIONS_SEMANTIC_VERIFIED",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            else:
                # LLM says different meaning -> manual check
                if verification.differences:
                    reason = f"Lijkt op {article_ref} maar heeft andere betekenis: {verification.differences}"
                else:
                    reason = f"Lijkt op {article_ref} maar LLM ziet belangrijke verschillen. {verification.explanation}"
                
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason=reason,
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=article_ref,
                    category="CONDITIONS_SEMANTIC_DIFFERENT",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
                
        except Exception as e:
            logger.warning(f"LLM semantic verification failed: {e}")
            # Fall back to embedding-only result
            if match.score >= self.SEMANTIC_HIGH_THRESHOLD:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Semantisch identiek aan {match.text_id} ({int(match.score*100)}% betekenis-match). LLM verificatie mislukt, maar score is hoog.",
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=match.text_id,
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
        
        # Check for long text that might need splitting
        if len(text) > self.config.multi_clause.max_text_length:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.SPLITSEN_CONTROLEREN.value,
                reason=f"Tekst is erg lang ({len(text)} tekens), bevat mogelijk meerdere onderwerpen.",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="LONG_TEXT",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        # Keyword-based rules
        keyword_advice = self._check_keyword_rules(cluster, simple_text)
        if keyword_advice:
            return keyword_advice
        
        # Frequency-based standardization
        threshold = self.config.analysis_rules.frequency_standardize_threshold
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
        """Find the best matching section in the conditions."""
        if not self._policy_sections:
            return None
        
        best_score = 0.0
        best_section = None
        
        for section in self._policy_sections:
            if not section.simplified_text:
                continue
            
            score = self.similarity_service.similarity(text, section.simplified_text)
            
            if score > best_score:
                best_score = score
                best_section = section
            
            # Also check substring match
            if text in section.simplified_text:
                substring_score = min(1.0, 0.95 + (len(text) / len(section.simplified_text)) * 0.05)
                if substring_score > best_score:
                    best_score = substring_score
                    best_section = section
        
        if best_section and best_score >= self.MEDIUM_SIMILARITY_THRESHOLD:
            return (best_score, best_section)
        
        return None
    
    def _find_matching_article(self, text: str) -> Optional[str]:
        """Find the article where the text appears."""
        for section in self._policy_sections:
            if section.simplified_text and text in section.simplified_text:
                return section.id
        return None
    
    def _check_significant_fragments(self, text: str) -> Optional[dict]:
        """Check if significant fragments appear in conditions."""
        if not self._policy_full_text or len(text) < 50:
            return None
        
        sentences = re.split(r'[.!?]\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return None
        
        matches_found = 0
        matching_articles = set()
        
        for sentence in sentences:
            if sentence in self._policy_full_text:
                matches_found += 1
                article = self._find_matching_article(sentence)
                if article:
                    matching_articles.add(article)
        
        match_ratio = matches_found / len(sentences) if sentences else 0
        
        if match_ratio >= 0.5 and matches_found >= 2:
            articles_str = ", ".join(matching_articles) if matching_articles else "Voorwaarden"
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
        logger.info(f"Step 0 - Admin issues (hygiëne): {stats.get('step0_admin_issues', 0)}")
        logger.info(f"Step 1 - Clause Library matches: {stats['step1_library_match']}")
        logger.info(f"Step 2 - Conditions matches: {stats['step2_conditions_match']}")
        logger.info(f"  └─ Waarvan semantische matches: {semantic_matches}")
        logger.info(f"Step 3 - Fallback analysis: {stats['step3_fallback']}")
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
