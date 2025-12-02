# hienfeld/services/multi_clause_service.py
"""
Service for detecting multi-clause texts ("brei" detection).
"""
import re
from typing import List, Tuple

from ..config import AppConfig
from ..domain.clause import Clause
from ..logging_config import get_logger

logger = get_logger('multi_clause_service')


class MultiClauseDetectionService:
    """
    Detects texts that contain multiple clauses and should be split.
    
    Common patterns:
    - Multiple clause codes (9NX3, 9NY3)
    - Multiple numbered items
    - Extremely long texts
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the multi-clause detection service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.code_pattern = re.compile(config.multi_clause.clause_code_pattern)
        
        # Pattern for multiple numbered items
        self.numbering_patterns = [
            r'^\s*\d+\.\s',         # "1. "
            r'^\s*[a-z]\)\s',       # "a) "
            r'^\s*[-•]\s',          # "- " or "• "
            r'^\s*[ivxIVX]+\.\s'    # Roman numerals
        ]
    
    def is_multi_clause(self, clause: Clause) -> bool:
        """
        Check if a clause contains multiple sub-clauses.
        
        Args:
            clause: Clause to analyze
            
        Returns:
            True if clause should be flagged for splitting
        """
        text = clause.raw_text
        
        if not text:
            return False
        
        # Check 1: Multiple clause codes
        codes = self._extract_clause_codes(text)
        if len(codes) >= self.config.multi_clause.min_codes_for_split:
            logger.debug(f"Multi-clause detected (codes): {codes}")
            return True
        
        # Check 2: Text length
        if len(text) > self.config.multi_clause.max_text_length:
            logger.debug(f"Multi-clause detected (length): {len(text)} chars")
            return True
        
        # Check 3: Multiple numbered items (3+ suggests list)
        if self._count_numbered_items(text) >= 3:
            logger.debug("Multi-clause detected (numbered items)")
            return True
        
        return False
    
    def _extract_clause_codes(self, text: str) -> List[str]:
        """
        Extract clause codes from text.
        
        Args:
            text: Text to search
            
        Returns:
            List of unique clause codes
        """
        matches = self.code_pattern.findall(text)
        return list(set(matches))
    
    def _count_numbered_items(self, text: str) -> int:
        """
        Count numbered/bulleted items in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Count of numbered items
        """
        count = 0
        lines = text.split('\n')
        
        for line in lines:
            for pattern in self.numbering_patterns:
                if re.match(pattern, line):
                    count += 1
                    break
        
        return count
    
    def get_split_reason(self, clause: Clause) -> Tuple[str, str]:
        """
        Get the reason why a clause should be split.
        
        Args:
            clause: Clause to analyze
            
        Returns:
            Tuple of (reason_code, reason_description)
        """
        text = clause.raw_text
        
        if not text:
            return ("EMPTY", "Tekst is leeg")
        
        # Check codes first
        codes = self._extract_clause_codes(text)
        if len(codes) >= self.config.multi_clause.min_codes_for_split:
            codes_str = ", ".join(codes)
            return (
                "MULTI_CODE",
                f"Bevat {len(codes)} verschillende clausules ({codes_str}). Moet handmatig gesplitst worden."
            )
        
        # Check length
        if len(text) > self.config.multi_clause.max_text_length:
            return (
                "LONG_TEXT",
                f"Tekst is erg lang ({len(text)} tekens), bevat mogelijk meerdere onderwerpen."
            )
        
        # Check numbered items
        item_count = self._count_numbered_items(text)
        if item_count >= 3:
            return (
                "NUMBERED_LIST",
                f"Bevat {item_count} genummerde items die mogelijk apart behandeld moeten worden."
            )
        
        return ("NONE", "Geen split nodig")
    
    def mark_multi_clauses(self, clauses: List[Clause]) -> int:
        """
        Mark all multi-clause texts in a list.
        
        Args:
            clauses: List of clauses to process
            
        Returns:
            Count of clauses marked as multi-clause
        """
        count = 0
        for clause in clauses:
            if self.is_multi_clause(clause):
                clause.is_multi_clause = True
                count += 1
        
        logger.info(f"Marked {count} clauses as multi-clause")
        return count

