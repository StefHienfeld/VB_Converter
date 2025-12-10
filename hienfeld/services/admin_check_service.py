# hienfeld/services/admin_check_service.py
"""
Administrative Check Service (Step 0 in the pipeline).

Performs hygiene checks on free text clauses BEFORE content analysis.
Uses a hybrid approach:
- Simple checks: Rule-based, no AI needed (fast, free)
- Complex checks: AI-powered analysis (slower, costs money)

Issues detected:
- Empty/too short text
- Dates in the past
- Placeholders ([INVULLEN], XXX, etc.)
- Encoding problems
- Incomplete sentences (AI)
- Internal contradictions (AI)
"""
from typing import Optional, List, Tuple, Any
from datetime import datetime
import re

from ..config import AppConfig
from ..domain.analysis import (
    AnalysisAdvice, 
    AdviceCode, 
    ConfidenceLevel,
    AdminIssueType,
    AdminCheckResult
)
from ..domain.cluster import Cluster
from ..prompts.admin_prompt import AdminPrompt, AdminPromptResult
from ..logging_config import get_logger

logger = get_logger('admin_check_service')


class AdminCheckService:
    """
    Service for administrative/hygiene checks on policy clauses.
    
    This is Step 0 of the analysis pipeline, running before:
    - Clause library matching (Step 1)
    - Conditions comparison (Step 2)  
    - Compliance analysis (Step 3)
    
    Uses hybrid approach:
    - Simple rule-based checks run first (fast, no AI)
    - Complex AI checks only if simple checks pass
    """
    
    # Minimum text length for analysis
    MIN_TEXT_LENGTH = 10
    
    # Patterns for placeholder detection
    PLACEHOLDER_PATTERNS = [
        r'\[invullen\]',
        r'\[INVULLEN\]',
        r'\[naam\]',
        r'\[adres\]',
        r'\[bedrag\]',
        r'\[datum\]',
        r'\[.*?\]',           # Any [something]
        r'XXX+',              # XXX or XXXX etc
        r'___+',              # ___ underscores
        r'\.{4,}',            # .... many dots
        r'€\s*[\-_]{2,}',     # € ___ or € ---
        r'\?\?\?+',           # ??? 
    ]
    
    # Patterns for encoding problems
    ENCODING_PATTERNS = [
        r'Ã©',               # é encoded wrong
        r'Ã«',               # ë encoded wrong
        r'Ã¶',               # ö encoded wrong
        r'Ã¼',               # ü encoded wrong
        r'â€™',              # ' encoded wrong
        r'â€œ',              # " encoded wrong
        r'â€',               # Various encoding issues
        r'ï»¿',              # BOM character
        r'[\x00-\x08\x0b\x0c\x0e-\x1f]',  # Control characters
    ]
    
    # Pattern for dates (supports multiple formats)
    # Matches: 1-1-2015, 01/01/2015, 1 januari 2015, etc.
    DATE_PATTERNS = [
        # DD-MM-YYYY or DD/MM/YYYY
        r'\b(\d{1,2})[-/](\d{1,2})[-/]((?:19|20)\d{2})\b',
        # YYYY-MM-DD
        r'\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b',
        # "1 januari 2015" etc.
        r'\b(\d{1,2})\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+((?:19|20)\d{2})\b',
    ]
    
    MONTH_MAP = {
        'januari': 1, 'februari': 2, 'maart': 3, 'april': 4,
        'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'december': 12
    }
    
    def __init__(
        self,
        config: AppConfig,
        llm_client: Any = None,
        model_name: str = "gpt-4",
        enable_ai_checks: bool = True
    ):
        """
        Initialize the admin check service.
        
        Args:
            config: Application configuration
            llm_client: Optional LLM client for complex checks
            model_name: Model name for AI checks
            enable_ai_checks: Whether to use AI for complex checks
        """
        self.config = config
        self.llm_client = llm_client
        self.model_name = model_name
        self.enable_ai_checks = enable_ai_checks
        
        # Compile regex patterns for performance
        self._placeholder_regex = re.compile(
            '|'.join(self.PLACEHOLDER_PATTERNS), 
            re.IGNORECASE
        )
        self._encoding_regex = re.compile(
            '|'.join(self.ENCODING_PATTERNS)
        )
    
    def check_cluster(self, cluster: Cluster) -> Tuple[AdminCheckResult, Optional[AnalysisAdvice]]:
        """
        Perform administrative checks on a cluster.
        
        Returns:
            Tuple of (AdminCheckResult, Optional[AnalysisAdvice])
            If advice is returned, the cluster should skip further analysis.
        """
        text = cluster.original_text
        
        # Run simple checks first
        result = self._run_simple_checks(text)
        
        if result.has_issues:
            # Convert to advice and return
            advice = self._result_to_advice(result, cluster)
            return result, advice
        
        # If simple checks pass AND AI is enabled, run complex checks
        if self.enable_ai_checks and self.llm_client is not None:
            ai_result = self._run_ai_checks(text)
            if ai_result.has_issues:
                advice = self._result_to_advice(ai_result, cluster)
                return ai_result, advice
        
        # All checks passed
        return AdminCheckResult.ok(), None
    
    def _run_simple_checks(self, text: str) -> AdminCheckResult:
        """
        Run simple rule-based checks (no AI).
        
        Checks:
        1. Empty text
        2. Too short text
        3. Placeholders
        4. Encoding problems
        5. Dates in the past
        """
        result = AdminCheckResult(has_issues=False, issues=[])
        
        # Check 1: Empty text
        if not text or not text.strip():
            return AdminCheckResult.with_issue(
                issue_type=AdminIssueType.LEEG,
                description="Tekst is leeg",
                recommendation=AdviceCode.LEEG
            )
        
        stripped = text.strip()
        
        # Check 2: Too short
        if len(stripped) < self.MIN_TEXT_LENGTH:
            return AdminCheckResult.with_issue(
                issue_type=AdminIssueType.TE_KORT,
                description=f"Tekst is te kort ({len(stripped)} tekens)",
                recommendation=AdviceCode.HANDMATIG_CHECKEN
            )
        
        # Check 3: Placeholders
        placeholder_match = self._placeholder_regex.search(text)
        if placeholder_match:
            return AdminCheckResult.with_issue(
                issue_type=AdminIssueType.PLACEHOLDER,
                description=f"Tekst bevat placeholder: '{placeholder_match.group()}'",
                recommendation=AdviceCode.AANVULLEN,
                details=placeholder_match.group()
            )
        
        # Check 4: Encoding problems
        encoding_match = self._encoding_regex.search(text)
        if encoding_match:
            return AdminCheckResult.with_issue(
                issue_type=AdminIssueType.ENCODING,
                description=f"Tekst bevat encoding-fouten: '{encoding_match.group()}'",
                recommendation=AdviceCode.OPSCHONEN,
                details=encoding_match.group()
            )
        
        # Check 5: Dates in the past (only expiry dates and old taxaties)
        past_date = self._find_past_date(text)
        if past_date:
            date_str, parsed_date = past_date
            text_lower = text.lower()
            
            # Check if it's a taxatie date (special handling)
            taxatie_keywords = ['taxatie', 'rapport', 'waardebepaling', '7:960', 'getaxeerd']
            is_taxatie = any(kw in text_lower for kw in taxatie_keywords)
            
            if is_taxatie:
                return AdminCheckResult.with_issue(
                    issue_type=AdminIssueType.VEROUDERD,
                    description=f"Taxatierapport ouder dan 3 jaar ({date_str}). Controleer of hertaxatie nodig is.",
                    recommendation=AdviceCode.HANDMATIG_CHECKEN,  # Suggest check, not delete
                    details=date_str
                )
            else:
                return AdminCheckResult.with_issue(
                    issue_type=AdminIssueType.VEROUDERD,
                    description=f"Verlopen deadline/termijn gevonden: {date_str}",
                    recommendation=AdviceCode.VERWIJDEREN_VERLOPEN,
                    details=date_str
                )
        
        # All simple checks passed
        result.passed_simple_checks = True
        return result
    
    def _find_past_date(self, text: str) -> Optional[Tuple[str, datetime]]:
        """
        Find dates in the text that are in the past, with context-aware validation.
        
        IMPROVED v2.1: Much more conservative - only flags actual deadlines/expiry dates.
        
        Uses context windows to determine if a past date is actually problematic:
        - WHITELIST (never flag):
          - Reference dates (specificatie, d.d., Christie's, overzicht, lijst)
          - Birth dates (geboren, geboortedatum)
          - Legal references (Wet van, artikel, BW)
          - Taxatie dates (< 3 years = valid)
        - GREYLIST (informational only):
          - Taxatie dates (> 3 years) -> suggest review, not delete
          - Version/model references
        - BLACKLIST (flag as problematic):
          - Actual expiry dates (uiterlijk, geldig tot, vervalt per) in the past
        
        Returns:
            Tuple of (date_string, parsed_date) if problematic date found, None otherwise
        """
        today = datetime.now()
        current_year = today.year
        text_lower = text.lower()
        
        for pattern in self.DATE_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            
            for match in matches:
                try:
                    date_str = match.group(0)
                    parsed_date = self._parse_date(match, pattern)
                    
                    if parsed_date and parsed_date < today:
                        # Get context window (100 chars before and after for better context)
                        match_start = match.start()
                        match_end = match.end()
                        context_start = max(0, match_start - 100)
                        context_end = min(len(text), match_end + 100)
                        context_snippet = text_lower[context_start:context_end]
                        
                        # Calculate age
                        date_year = parsed_date.year
                        age_in_years = current_year - date_year
                        
                        # ============================================================
                        # WHITELIST 1: Reference dates (specificatie, d.d., etc.)
                        # These are NEVER problematic - they reference when something
                        # was created/documented, not when it expires
                        # ============================================================
                        reference_keywords = [
                            'd.d.', 'specificatie', 'christie', 'sotheby', 'overzicht',
                            'lijst', 'conform', 'volgens', 'ontvangen op', 'opgesteld',
                            'gedateerd', 'de dato', 'dd.', 'dd ', 'per datum'
                        ]
                        if any(kw in context_snippet for kw in reference_keywords):
                            logger.debug(f"Date {date_str} is a reference date, skipping")
                            continue
                        
                        # ============================================================
                        # WHITELIST 2: Birth dates (never expire)
                        # ============================================================
                        birth_keywords = [
                            'geboren', 'geboortedatum', 'geboorte', 'birth', 'dob'
                        ]
                        if any(kw in context_snippet for kw in birth_keywords):
                            logger.debug(f"Date {date_str} is a birth date, skipping")
                            continue
                        
                        # ============================================================
                        # WHITELIST 3: Legal/law references (never expire)
                        # ============================================================
                        legal_keywords = [
                            'wet van', 'wetgeving', 'staatsblad', 'artikel', 'bw',
                            'burgerlijk wetboek', 'wft', 'awb', 'besluit', 'regeling',
                            'richtlijn', 'verordening'
                        ]
                        if any(kw in context_snippet for kw in legal_keywords):
                            logger.debug(f"Date {date_str} is a legal reference, skipping")
                            continue
                        
                        # ============================================================
                        # WHITELIST 4: Taxatie/rapport dates (valid for 3 years)
                        # ============================================================
                        taxatie_keywords = [
                            'taxatie', 'rapport', 'waardebepaling', 'deskundige',
                            '7:960', 'taxatierapport', 'taxatiedatum', 'getaxeerd',
                            'hertaxatie', 'waardering'
                        ]
                        if any(kw in context_snippet for kw in taxatie_keywords):
                            if age_in_years <= 3:
                                # Taxatie is still valid (< 3 years)
                                logger.debug(f"Date {date_str} in taxatie context, still valid (age: {age_in_years} years)")
                                continue
                            else:
                                # Taxatie > 3 years old - this IS a problem for taxaties
                                logger.info(f"Taxatie date {date_str} is > 3 years old (age: {age_in_years} years)")
                                return (date_str, parsed_date)
                        
                        # ============================================================
                        # WHITELIST 5: Version/model/voorwaarden references
                        # These reference document versions, not expiry dates
                        # ============================================================
                        version_keywords = [
                            'versie', 'model', 'gedeponeerd', 'kenmerk', 'voorwaarden',
                            'clausuleblad', 'depot', 'ingediend', 'polisvoorwaarden',
                            'algemene voorwaarden', 'van toepassing'
                        ]
                        if any(kw in context_snippet for kw in version_keywords):
                            logger.debug(f"Date {date_str} is a version reference, skipping")
                            continue
                        
                        # ============================================================
                        # BLACKLIST: Actual expiry/deadline dates = CRITICAL
                        # Only these should be flagged as problematic
                        # ============================================================
                        expiry_keywords = [
                            'uiterlijk', 'voor ', 'dient te zijn', 'operationeel',
                            'einddatum', 'vervalt per', 'geldig tot', 'geldig tot en met',
                            'looptijd tot', 'vervaldatum', 'eindigt op', 'tot uiterlijk',
                            'ten laatste', 'deadline'
                        ]
                        if any(kw in context_snippet for kw in expiry_keywords):
                            # This is an actual expiry/deadline date in the past - CRITICAL
                            logger.warning(f"Expiry/deadline date {date_str} found in past (age: {age_in_years} years)")
                            return (date_str, parsed_date)
                        
                        # ============================================================
                        # DEFAULT: Date in past without clear context
                        # Be CONSERVATIVE - do NOT flag unless clearly problematic
                        # ============================================================
                        # Don't flag dates without clear expiry context
                        logger.debug(f"Date {date_str} in past but no expiry context, skipping (age: {age_in_years} years)")
                        continue
                            
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _parse_date(self, match: re.Match, pattern: str) -> Optional[datetime]:
        """Parse a date from a regex match."""
        groups = match.groups()
        
        try:
            # DD-MM-YYYY or DD/MM/YYYY pattern
            if 'januari' not in pattern and len(groups) == 3:
                if int(groups[0]) > 31:  # YYYY-MM-DD format
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                else:  # DD-MM-YYYY format
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                return datetime(year, month, day)
            
            # "1 januari 2015" pattern
            elif len(groups) == 3 and groups[1].lower() in self.MONTH_MAP:
                day = int(groups[0])
                month = self.MONTH_MAP[groups[1].lower()]
                year = int(groups[2])
                return datetime(year, month, day)
                
        except (ValueError, TypeError):
            return None
        
        return None
    
    def _run_ai_checks(self, text: str) -> AdminCheckResult:
        """
        Run complex AI-powered checks.
        
        Checks:
        - Incomplete sentences
        - Internal contradictions
        - General quality issues
        """
        if self.llm_client is None:
            return AdminCheckResult.ok()
        
        try:
            messages = AdminPrompt.build_messages(text)
            
            # Call LLM
            if hasattr(self.llm_client, 'chat') and hasattr(self.llm_client.chat, 'completions'):
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.0
                )
                response_text = response.choices[0].message.content
            elif callable(self.llm_client):
                prompt = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
                response_text = self.llm_client(prompt)
            else:
                logger.warning("Unsupported LLM client type")
                return AdminCheckResult.ok()
            
            # Parse response
            ai_result = AdminPromptResult.from_json(response_text, raw_response=response_text)
            
            # Convert to AdminCheckResult
            if ai_result.has_issues:
                result = AdminCheckResult(has_issues=True, issues=[])
                result.summary = ai_result.summary
                
                for issue in ai_result.issues:
                    issue_type = self._map_ai_issue_type(issue.get('type', 'UNKNOWN'))
                    result.add_issue(
                        issue_type=issue_type,
                        description=issue.get('description', 'Onbekend probleem')
                    )
                
                # Map recommendation
                result.recommendation = self._map_ai_recommendation(ai_result.recommendation)
                return result
            
            # No issues from AI
            result = AdminCheckResult.ok()
            result.summary = ai_result.summary
            return result
            
        except Exception as e:
            logger.error(f"AI admin check failed: {e}")
            return AdminCheckResult.ok()  # Fail gracefully
    
    def _map_ai_issue_type(self, issue_type: str) -> AdminIssueType:
        """Map AI issue type string to AdminIssueType enum."""
        mapping = {
            'INCOMPLEET': AdminIssueType.INCOMPLEET,
            'VEROUDERD': AdminIssueType.VEROUDERD,
            'TEGENSTRIJDIG': AdminIssueType.TEGENSTRIJDIG,
            'ONLEESBAAR': AdminIssueType.ONLEESBAAR,
        }
        return mapping.get(issue_type.upper(), AdminIssueType.INCOMPLEET)
    
    def _map_ai_recommendation(self, recommendation: str) -> AdviceCode:
        """Map AI recommendation string to AdviceCode enum."""
        mapping = {
            'OPSCHONEN': AdviceCode.OPSCHONEN,
            'AANVULLEN': AdviceCode.AANVULLEN,
            'VERWIJDEREN': AdviceCode.VERWIJDEREN_VERLOPEN,
            'OK': None
        }
        return mapping.get(recommendation.upper())
    
    def _result_to_advice(
        self, 
        result: AdminCheckResult, 
        cluster: Cluster
    ) -> AnalysisAdvice:
        """
        Convert AdminCheckResult to AnalysisAdvice.
        
        Args:
            result: The admin check result
            cluster: The cluster being analyzed
            
        Returns:
            AnalysisAdvice for the cluster
        """
        primary_issue = result.primary_issue
        
        if result.recommendation:
            advice_code = result.recommendation.value
        elif primary_issue:
            # Map issue type to advice code
            issue_to_advice = {
                AdminIssueType.LEEG: AdviceCode.LEEG.value,
                AdminIssueType.TE_KORT: AdviceCode.HANDMATIG_CHECKEN.value,
                AdminIssueType.VEROUDERD: AdviceCode.VERWIJDEREN_VERLOPEN.value,
                AdminIssueType.PLACEHOLDER: AdviceCode.AANVULLEN.value,
                AdminIssueType.ENCODING: AdviceCode.OPSCHONEN.value,
                AdminIssueType.INCOMPLEET: AdviceCode.AANVULLEN.value,
                AdminIssueType.TEGENSTRIJDIG: AdviceCode.HANDMATIG_CHECKEN.value,
                AdminIssueType.ONLEESBAAR: AdviceCode.ONLEESBAAR.value,
            }
            advice_code = issue_to_advice.get(
                primary_issue.issue_type, 
                AdviceCode.HANDMATIG_CHECKEN.value
            )
        else:
            advice_code = AdviceCode.HANDMATIG_CHECKEN.value
        
        # Build reason from issues
        if result.issues:
            reasons = [f"{i.issue_type.value}: {i.description}" for i in result.issues]
            reason = "; ".join(reasons)
        else:
            reason = "Administratief probleem gedetecteerd"
        
        # Determine confidence based on check type
        if result.passed_simple_checks:
            # AI check - medium confidence
            confidence = ConfidenceLevel.MIDDEN.value
        else:
            # Simple check - high confidence (rule-based)
            confidence = ConfidenceLevel.HOOG.value
        
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=advice_code,
            reason=reason,
            confidence=confidence,
            reference_article="-",
            category="ADMIN_CHECK",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )
    
    @property
    def is_ai_available(self) -> bool:
        """Check if AI checks are available."""
        return self.enable_ai_checks and self.llm_client is not None

