# hienfeld/services/analysis_service.py
"""
Service for analyzing clusters and generating advice.

KRITIEK: Deze service vergelijkt vrije teksten DAADWERKELIJK tegen de 
geüploade voorwaarden en clausules om te bepalen of ze verwijderd kunnen worden.
"""
from typing import Dict, List, Optional, Callable, Tuple
import re

from ..config import AppConfig
from ..domain.cluster import Cluster
from ..domain.policy_document import PolicyDocumentSection
from ..domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from ..utils.text_normalization import simplify_text
from ..services.similarity_service import RapidFuzzSimilarityService, SimilarityService
from ..logging_config import get_logger

logger = get_logger('analysis_service')


class AnalysisService:
    """
    Analyzes clusters and generates actionable advice.
    
    KRITIEKE FUNCTIONALITEIT:
    Deze service vergelijkt vrije teksten tegen geüploade voorwaarden/clausules
    om te bepalen of teksten al gedekt zijn en dus verwijderd kunnen worden.
    
    Rules cascade in priority order:
    1. Multi-clause detection (SPLITSEN) - tekst bevat meerdere clausules
    2. *** VOORWAARDEN CHECK *** - staat tekst al in voorwaarden? -> VERWIJDEREN
    3. Keyword-based rules (VERWIJDEREN, BEHOUDEN) - specifieke termen
    4. Frequency-based rules (STANDAARDISEREN) - vaak voorkomende teksten
    5. Fallback (HANDMATIG CHECKEN)
    """
    
    # Thresholds voor matching tegen voorwaarden
    EXACT_MATCH_THRESHOLD = 0.95      # Bijna identiek
    HIGH_SIMILARITY_THRESHOLD = 0.85  # Zeer vergelijkbaar
    MEDIUM_SIMILARITY_THRESHOLD = 0.75  # Vergelijkbaar
    
    def __init__(
        self, 
        config: AppConfig, 
        ai_analyzer=None,
        similarity_service: Optional[SimilarityService] = None
    ):
        """
        Initialize the analysis service.
        
        Args:
            config: Application configuration
            ai_analyzer: Optional AI analyzer service for enhanced analysis
            similarity_service: Service for computing text similarity
        """
        self.config = config
        self.ai_analyzer = ai_analyzer
        
        # Similarity service voor vergelijking met voorwaarden
        if similarity_service is None:
            self.similarity_service = RapidFuzzSimilarityService(
                threshold=self.HIGH_SIMILARITY_THRESHOLD
            )
        else:
            self.similarity_service = similarity_service
        
        # Cache voor policy sections
        self._policy_sections: List[PolicyDocumentSection] = []
        self._policy_full_text: str = ""
    
    def analyze_clusters(
        self,
        clusters: List[Cluster],
        policy_sections: Optional[List[PolicyDocumentSection]] = None,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, AnalysisAdvice]:
        """
        Analyze all clusters and generate advice.
        
        BELANGRIJK: Deze methode vergelijkt elke cluster DAADWERKELIJK tegen
        de geüploade voorwaarden en clausules!
        
        Args:
            clusters: List of Cluster objects
            policy_sections: List of policy document sections (voorwaarden/clausules)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping cluster_id -> AnalysisAdvice
        """
        logger.info(f"Analyzing {len(clusters)} clusters")
        
        # Store policy sections for comparison
        self._policy_sections = policy_sections or []
        
        # Build combined policy text for substring matching
        if self._policy_sections:
            self._policy_full_text = " ".join(
                s.simplified_text for s in self._policy_sections if s.simplified_text
            )
            logger.info(f"Loaded {len(self._policy_sections)} policy sections for comparison")
            logger.info(f"Total policy text length: {len(self._policy_full_text)} characters")
        else:
            self._policy_full_text = ""
            logger.warning("⚠️ GEEN VOORWAARDEN GELADEN - vergelijking niet mogelijk!")
        
        advice_map: Dict[str, AnalysisAdvice] = {}
        total = len(clusters)
        
        # Track statistics
        found_in_conditions = 0
        
        for i, cluster in enumerate(clusters):
            # Progress update
            if progress_callback and i % 20 == 0:
                progress_callback(int(i / total * 100))
            
            advice = self._analyze_single_cluster(cluster)
            advice_map[cluster.id] = advice
            
            # Track matches
            if "VOORWAARDEN" in advice.category or "voorwaarden" in advice.reason.lower():
                found_in_conditions += 1
        
        # Final progress
        if progress_callback:
            progress_callback(100)
        
        # Log summary
        self._log_analysis_summary(advice_map)
        
        if self._policy_sections:
            logger.info(f"✅ {found_in_conditions} clusters gevonden in voorwaarden/clausules")
        
        return advice_map
    
    def _analyze_single_cluster(self, cluster: Cluster) -> AnalysisAdvice:
        """
        Analyze a single cluster and generate advice.
        
        BELANGRIJK: Controleert EERST of de tekst voorkomt in de voorwaarden!
        
        Args:
            cluster: Cluster to analyze
            
        Returns:
            AnalysisAdvice for this cluster
        """
        text = cluster.original_text
        simple_text = cluster.leader_text
        frequency = cluster.frequency
        
        # ============================================================
        # RULE 0: SKIP zeer korte teksten
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
        # RULE 1: Multi-clause detection (SPLITSEN)
        # ============================================================
        codes = re.findall(r'\b[0-9][A-Z]{2}[0-9]\b', text)
        if len(set(codes)) > 1:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.SPLITSEN.value,
                reason=f"Bevat {len(set(codes))} verschillende clausules ({', '.join(set(codes))}). Moet handmatig gesplitst worden.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="Diverse",
                category="MULTI_CLAUSE",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        # ============================================================
        # RULE 2: *** KRITIEK *** CHECK TEGEN VOORWAARDEN/CLAUSULES
        # Dit is de BELANGRIJKSTE functionaliteit!
        # ============================================================
        if self._policy_sections:
            conditions_match = self._check_against_conditions(cluster)
            if conditions_match:
                return conditions_match
        
        # ============================================================
        # RULE 3: Long text check -> mogelijk splitsen
        # ============================================================
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
        
        # ============================================================
        # RULE 4: Keyword-based rules (hardcoded bekende patronen)
        # ============================================================
        keyword_advice = self._check_keyword_rules(cluster, simple_text)
        if keyword_advice:
            return keyword_advice
        
        # ============================================================
        # RULE 5: Frequency-based standardization
        # ============================================================
        threshold = self.config.analysis_rules.frequency_standardize_threshold
        if frequency >= threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.STANDAARDISEREN.value,
                reason=f"Komt vaak voor ({frequency}x). Maak hiervan een standaard clausulecode in het systeem.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article="Nieuw",
                category="FREQUENT",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        # ============================================================
        # RULE 6: AI analysis (if available)
        # ============================================================
        if self.ai_analyzer:
            ai_advice = self._try_ai_analysis(cluster)
            if ai_advice:
                return ai_advice
        
        # ============================================================
        # FALLBACK: Different behavior based on mode
        # ============================================================
        
        # If we're in "internal only" mode (no conditions), give useful info
        if not self._policy_sections:
            return self._internal_analysis_fallback(cluster, frequency)
        
        # With conditions but no match found
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason="Geen automatische match gevonden in voorwaarden. Beoordeel handmatig of dit maatwerk is.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="UNKNOWN",
            cluster_name=cluster.name,
            frequency=frequency
        )
    
    def _internal_analysis_fallback(self, cluster: Cluster, frequency: int) -> AnalysisAdvice:
        """
        Provide useful analysis when no conditions are uploaded.
        
        Instead of just "HANDMATIG CHECKEN", we give actionable info
        based on frequency and text characteristics.
        
        Args:
            cluster: Cluster to analyze
            frequency: How often this text appears
            
        Returns:
            AnalysisAdvice with useful information
        """
        # Unique texts (only appears once)
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
        
        # Low frequency (2-5x) - might be variants
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
        
        # Medium frequency (6-19x) - worth investigating
        if frequency < self.config.analysis_rules.frequency_standardize_threshold:
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.FREQUENTIE_INFO.value,
                reason=f"Komt {frequency}x voor. Relatief vaak, maar onder standaardisatie-drempel ({self.config.analysis_rules.frequency_standardize_threshold}).",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article="-",
                category="MEDIUM_FREQUENCY",
                cluster_name=cluster.name,
                frequency=frequency
            )
        
        # This shouldn't happen (high frequency should be caught earlier)
        # but just in case
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
    
    def _check_against_conditions(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """
        *** KRITIEKE FUNCTIE ***
        
        Controleert of een vrije tekst voorkomt in de geüploade voorwaarden/clausules.
        
        Gebruikt meerdere matching strategieën:
        1. Exacte substring match in volledige voorwaarden
        2. Fuzzy match per sectie/artikel
        3. Significante overlap detectie
        
        Args:
            cluster: Cluster to check
            
        Returns:
            AnalysisAdvice if match found, None otherwise
        """
        simple_text = cluster.leader_text
        
        if not simple_text or len(simple_text) < 20:
            return None
        
        # ============================================================
        # STRATEGY 1: Exacte substring match in volledige voorwaarden
        # ============================================================
        if self._policy_full_text and simple_text in self._policy_full_text:
            # Zoek welk artikel het betreft
            matching_article = self._find_matching_article(simple_text)
            
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=f"Tekst komt EXACT voor in de voorwaarden. Kan verwijderd worden als vrije tekst.",
                confidence=ConfidenceLevel.HOOG.value,
                reference_article=matching_article or "Voorwaarden",
                category="VOORWAARDEN_EXACT",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        # ============================================================
        # STRATEGY 2: Fuzzy match per sectie/artikel
        # ============================================================
        best_match = self._find_best_section_match(simple_text)
        
        if best_match:
            score, section = best_match
            
            if score >= self.EXACT_MATCH_THRESHOLD:
                # Bijna identiek (>95%)
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst komt bijna letterlijk voor in voorwaarden ({int(score*100)}% match). Kan verwijderd worden.",
                    confidence=ConfidenceLevel.HOOG.value,
                    reference_article=section.id,
                    category="VOORWAARDEN_EXACT",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            
            elif score >= self.HIGH_SIMILARITY_THRESHOLD:
                # Zeer vergelijkbaar (85-95%)
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Tekst lijkt sterk op voorwaarden ({int(score*100)}% match met {section.id}). Controleer en verwijder indien identiek.",
                    confidence=ConfidenceLevel.MIDDEN.value,
                    reference_article=section.id,
                    category="VOORWAARDEN_HIGH",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            
            elif score >= self.MEDIUM_SIMILARITY_THRESHOLD:
                # Vergelijkbaar (75-85%) - rapporteer maar geen automatisch advies
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                    reason=f"Tekst vertoont gelijkenis met {section.id} ({int(score*100)}% match). Controleer of dit een variant is.",
                    confidence=ConfidenceLevel.LAAG.value,
                    reference_article=section.id,
                    category="VOORWAARDEN_MEDIUM",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
        
        # ============================================================
        # STRATEGY 3: Check op significante tekstfragmenten
        # ============================================================
        fragment_result = self._check_significant_fragments(simple_text)
        if fragment_result and fragment_result.get('match_found'):
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.VERWIJDEREN.value,
                reason=fragment_result['reason'],
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=fragment_result['reference_article'],
                category=fragment_result['category'],
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        return None
    
    def _find_best_section_match(
        self, 
        text: str
    ) -> Optional[Tuple[float, PolicyDocumentSection]]:
        """
        Vind de best matchende sectie in de voorwaarden.
        
        Args:
            text: Simplified text to match
            
        Returns:
            Tuple of (similarity_score, section) or None
        """
        if not self._policy_sections:
            return None
        
        best_score = 0.0
        best_section = None
        
        for section in self._policy_sections:
            if not section.simplified_text:
                continue
            
            # Bereken similarity
            score = self.similarity_service.similarity(text, section.simplified_text)
            
            if score > best_score:
                best_score = score
                best_section = section
            
            # Ook check op substring match binnen sectie
            if text in section.simplified_text:
                # Exacte substring = hoge score
                substring_score = min(1.0, 0.95 + (len(text) / len(section.simplified_text)) * 0.05)
                if substring_score > best_score:
                    best_score = substring_score
                    best_section = section
        
        if best_section and best_score >= self.MEDIUM_SIMILARITY_THRESHOLD:
            return (best_score, best_section)
        
        return None
    
    def _find_matching_article(self, text: str) -> Optional[str]:
        """
        Vind het artikel waar de tekst in voorkomt.
        
        Args:
            text: Text to find
            
        Returns:
            Article ID or None
        """
        for section in self._policy_sections:
            if section.simplified_text and text in section.simplified_text:
                return section.id
        return None
    
    def _check_significant_fragments(self, text: str) -> Optional[dict]:
        """
        Check of significante fragmenten van de tekst in voorwaarden voorkomen.
        
        Splitst de tekst in zinnen en controleert elke zin.
        
        Args:
            text: Text to check
            
        Returns:
            Dictionary with match info if significant overlap found, None otherwise
        """
        if not self._policy_full_text or len(text) < 50:
            return None
        
        # Split in zinnen (simpele benadering)
        sentences = re.split(r'[.!?]\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return None
        
        # Tel hoeveel zinnen in voorwaarden voorkomen
        matches_found = 0
        matching_articles = set()
        
        for sentence in sentences:
            if sentence in self._policy_full_text:
                matches_found += 1
                article = self._find_matching_article(sentence)
                if article:
                    matching_articles.add(article)
        
        # Als meer dan 50% van de zinnen matcht
        match_ratio = matches_found / len(sentences) if sentences else 0
        
        if match_ratio >= 0.5 and matches_found >= 2:
            articles_str = ", ".join(matching_articles) if matching_articles else "Voorwaarden"
            # Return partial advice - caller will fill in cluster details
            return {
                'match_found': True,
                'reason': f"Meerdere zinnen ({matches_found}/{len(sentences)}) komen voor in voorwaarden. Kan verwijderd worden.",
                'reference_article': articles_str,
                'category': "VOORWAARDEN_FRAGMENTS"
            }
        
        return None
    
    def _check_keyword_rules(
        self, 
        cluster: Cluster, 
        simple_text: str
    ) -> Optional[AnalysisAdvice]:
        """
        Check keyword-based rules from configuration.
        
        Args:
            cluster: Cluster being analyzed
            simple_text: Simplified text for matching
            
        Returns:
            AnalysisAdvice if a rule matches, None otherwise
        """
        rules = self.config.analysis_rules.keyword_rules
        
        for rule_name, rule_config in rules.items():
            keywords = rule_config.get('keywords', [])
            
            # Check if any keyword matches
            if not any(kw in simple_text for kw in keywords):
                continue
            
            # Special handling for rules with inclusion keywords (e.g., molest)
            inclusion_keywords = rule_config.get('inclusion_keywords')
            if inclusion_keywords:
                if not any(kw in simple_text for kw in inclusion_keywords):
                    continue
            
            # Check max length constraint if specified
            max_length = rule_config.get('max_length')
            if max_length and len(simple_text) > max_length:
                continue
            
            # Rule matches - create advice
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=rule_config.get('advice', 'HANDMATIG CHECKEN'),
                reason=rule_config.get('reason', 'Keyword match'),
                confidence=rule_config.get('confidence', 'Midden'),
                reference_article=rule_config.get('article', '-'),
                category=rule_name.upper(),
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
        
        return None
    
    def _try_ai_analysis(self, cluster: Cluster) -> Optional[AnalysisAdvice]:
        """
        Try AI-enhanced analysis (if available).
        
        Args:
            cluster: Cluster to analyze
            
        Returns:
            AnalysisAdvice from AI or None
        """
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
    
    def _log_analysis_summary(self, advice_map: Dict[str, AnalysisAdvice]) -> None:
        """
        Log summary of analysis results.
        
        Args:
            advice_map: All generated advice
        """
        # Count by advice code
        counts = {}
        categories = {}
        
        for advice in advice_map.values():
            code = advice.advice_code
            counts[code] = counts.get(code, 0) + 1
            
            cat = advice.category
            categories[cat] = categories.get(cat, 0) + 1
        
        logger.info("=" * 50)
        logger.info("ANALYSE SAMENVATTING")
        logger.info("=" * 50)
        logger.info("Per adviestype:")
        for code, count in sorted(counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {code}: {count}")
        
        logger.info("\nPer categorie:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            logger.info(f"  {cat}: {count}")
        
        # Highlight voorwaarden matches
        voorwaarden_cats = [c for c in categories if 'VOORWAARDEN' in c]
        if voorwaarden_cats:
            total_voorwaarden = sum(categories[c] for c in voorwaarden_cats)
            logger.info(f"\n✅ TOTAAL GEVONDEN IN VOORWAARDEN: {total_voorwaarden}")
    
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
        """
        Add a new keyword rule dynamically.
        
        Args:
            name: Rule name
            keywords: Keywords to match
            advice: Advice code to return
            reason: Reason text
            article: Reference article
            confidence: Confidence level
            max_length: Optional max text length
            inclusion_keywords: Optional secondary keywords required
        """
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
        """
        Adjust similarity thresholds for conditions matching.
        
        Args:
            exact: Threshold for exact match (default 0.95)
            high: Threshold for high similarity (default 0.85)
            medium: Threshold for medium similarity (default 0.75)
        """
        self.EXACT_MATCH_THRESHOLD = exact
        self.HIGH_SIMILARITY_THRESHOLD = high
        self.MEDIUM_SIMILARITY_THRESHOLD = medium
        logger.info(f"Updated thresholds: exact={exact}, high={high}, medium={medium}")
