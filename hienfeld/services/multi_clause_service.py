# hienfeld/services/multi_clause_service.py
"""
Service for detecting multi-clause texts ("brei" detection).

IMPROVED v2.1:
- Better split detection using multiple strategies
- Topic-based splitting (keywords like "Rubriek", "Ten aanzien van")
- Paragraph-based splitting for long texts
- Minimum segment length enforcement
- Per-segment analysis support
"""
import re
from typing import List, Tuple, Optional, Any

from ..config import AppConfig
from ..domain.clause import Clause
from ..logging_config import get_logger

logger = get_logger('multi_clause_service')


class MultiClauseDetectionService:
    """
    Detects texts that contain multiple clauses and should be split.
    
    IMPROVED v2.1: Better splitting with multiple strategies.
    
    Common patterns:
    - Multiple clause codes (9NX3, 9NY3)
    - Multiple numbered items
    - Multiple topics (Rubriek X, Ten aanzien van, etc.)
    - Paragraph-separated sections
    - Extremely long texts
    """
    
    # Minimum segment length to avoid micro-segments
    MIN_SEGMENT_LENGTH = 50
    
    def __init__(self, config: AppConfig, llm_service: Optional[Any] = None):
        """
        Initialize the multi-clause detection service.
        
        Args:
            config: Application configuration
            llm_service: Optional LLM service for intelligent splitting fallback
        """
        self.config = config
        self.code_pattern = re.compile(config.multi_clause.clause_code_pattern)
        self.llm_service = llm_service
        
        # Pattern for multiple numbered items
        self.numbering_patterns = [
            r'^\s*\d+\.\s',         # "1. "
            r'^\s*\d+\)\s',         # "1) "
            r'^\s*[a-z]\)\s',       # "a) "
            r'^\s*[a-z]\.\s',       # "a. "
            r'^\s*[-•]\s',          # "- " or "• "
            r'^\s*[ivxIVX]+\.\s',   # Roman numerals
            r'^\s*[ivxIVX]+\)\s',   # Roman numerals with )
        ]
        
        # Topic-starting keywords (indicate new section)
        self.topic_keywords = [
            r'rubriek\s+\w+',           # "Rubriek Reis"
            r'ten\s+aanzien\s+van',     # "Ten aanzien van"
            r'voor\s+de\s+rubriek',     # "Voor de rubriek"
            r'met\s+betrekking\s+tot',  # "Met betrekking tot"
            r'de\s+volgende\s+\w+',     # "De volgende bepalingen"
            r'uitgesloten\s+is',        # "Uitgesloten is"
            r'niet\s+verzekerd\s+is',   # "Niet verzekerd is"
            r'wel\s+verzekerd\s+is',    # "Wel verzekerd is"
            r'gedekt\s+is',             # "Gedekt is"
            r'in\s+afwijking\s+van',    # "In afwijking van"
            r'in\s+aanvulling\s+op',    # "In aanvulling op"
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
    
    def split_clause(self, text: str) -> List[str]:
        """
        Split a multi-clause text into logical segments (sub-clauses).
        
        IMPROVED v2.1: Multiple strategies with better fallbacks.
        
        Uses multiple strategies in order:
        1. Clause codes (9NX3 patterns)
        2. Topic keywords (Rubriek, Ten aanzien van, etc.)
        3. Numbering patterns (1., a), -)
        4. Paragraph-based splitting (double newlines)
        5. Sentence-based splitting for very long texts
        6. LLM fallback if available
        
        Args:
            text: Text to split
            
        Returns:
            List of text segments (sub-clauses)
        """
        if not text or len(text.strip()) == 0:
            return [text]
        
        # Strategy 1: Try splitting on clause codes
        code_pattern = re.compile(self.config.multi_clause.clause_code_pattern)
        code_matches = list(code_pattern.finditer(text))
        
        if len(code_matches) >= 2:
            segments = self._split_on_codes(text, code_matches)
            if len(segments) > 1:
                logger.debug(f"Split on clause codes: {len(segments)} segments")
                return self._filter_segments(segments)
        
        # Strategy 2: Try splitting on topic keywords
        topic_segments = self._split_on_topics(text)
        if len(topic_segments) >= 2:
            logger.debug(f"Split on topics: {len(topic_segments)} segments")
            return self._filter_segments(topic_segments)
        
        # Strategy 3: Try splitting on numbering patterns
        numbered_segments = self._split_on_numbering(text)
        if len(numbered_segments) >= 2:
            logger.debug(f"Split on numbering: {len(numbered_segments)} segments")
            return self._filter_segments(numbered_segments)
        
        # Strategy 4: Try splitting on headers/keywords
        header_segments = self._split_on_headers(text)
        if len(header_segments) >= 2:
            logger.debug(f"Split on headers: {len(header_segments)} segments")
            return self._filter_segments(header_segments)
        
        # Strategy 5: For long texts, try paragraph-based splitting
        if len(text) > 800:
            para_segments = self._split_on_paragraphs(text)
            if len(para_segments) >= 2:
                logger.debug(f"Split on paragraphs: {len(para_segments)} segments")
                return self._filter_segments(para_segments)
        
        # Strategy 6: For very long texts, try sentence-based splitting
        if len(text) > 1500:
            sentence_segments = self._split_on_sentences(text)
            if len(sentence_segments) >= 2:
                logger.debug(f"Split on sentences: {len(sentence_segments)} segments")
                return self._filter_segments(sentence_segments)
        
        # Strategy 7: LLM fallback if available
        if len(text) > 800 and self.llm_service and hasattr(self.llm_service, 'intelligent_split'):
            try:
                logger.info(f"Regex split failed for text ({len(text)} chars), trying LLM split")
                llm_segments = self.llm_service.intelligent_split(text)
                if len(llm_segments) > 1:
                    logger.info(f"LLM split successful: {len(llm_segments)} segments")
                    return self._filter_segments(llm_segments)
            except Exception as e:
                logger.error(f"LLM split failed: {e}")
        
        # No split possible - return original text
        logger.debug(f"No split possible for text ({len(text)} chars)")
        return [text]
    
    def _filter_segments(self, segments: List[str]) -> List[str]:
        """
        Filter and clean segments, merging small segments with neighbors.
        
        Args:
            segments: Raw segments from splitting
            
        Returns:
            Cleaned segments with minimum length enforced
        """
        if not segments:
            return segments
        
        # Clean segments
        cleaned = [s.strip() for s in segments if s and s.strip()]
        
        if not cleaned:
            return segments
        
        # Merge small segments with previous segment
        result = []
        for seg in cleaned:
            if len(seg) < self.MIN_SEGMENT_LENGTH and result:
                # Merge with previous segment
                result[-1] = result[-1] + "\n\n" + seg
            else:
                result.append(seg)
        
        return result if result else segments
    
    def _split_on_topics(self, text: str) -> List[str]:
        """
        Split text on topic-starting keywords.
        
        Args:
            text: Text to split
            
        Returns:
            List of segments
        """
        # Build combined pattern
        combined_pattern = '|'.join(f'({p})' for p in self.topic_keywords)
        
        # Find all topic boundaries
        segments = []
        last_end = 0
        
        for match in re.finditer(combined_pattern, text, re.IGNORECASE):
            start = match.start()
            
            # Find start of line containing the match
            line_start = text.rfind('\n', 0, start)
            line_start = line_start + 1 if line_start >= 0 else 0
            
            # Only split if we have content before this point
            if line_start > last_end:
                segment = text[last_end:line_start].strip()
                if segment:
                    segments.append(segment)
                last_end = line_start
        
        # Add final segment
        if last_end < len(text):
            segment = text[last_end:].strip()
            if segment:
                segments.append(segment)
        
        return segments if len(segments) >= 2 else [text]
    
    def _split_on_paragraphs(self, text: str) -> List[str]:
        """
        Split text on paragraph boundaries (double newlines).
        
        Args:
            text: Text to split
            
        Returns:
            List of segments
        """
        # Split on double newlines
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Filter empty paragraphs
        segments = [p.strip() for p in paragraphs if p.strip()]
        
        # Group small paragraphs together (minimum ~200 chars per segment)
        result = []
        current = []
        current_len = 0
        
        for para in segments:
            current.append(para)
            current_len += len(para)
            
            if current_len >= 200:
                result.append('\n\n'.join(current))
                current = []
                current_len = 0
        
        # Don't forget remaining content
        if current:
            if result:
                # Merge with last segment if small
                result[-1] = result[-1] + '\n\n' + '\n\n'.join(current)
            else:
                result.append('\n\n'.join(current))
        
        return result if len(result) >= 2 else [text]
    
    def _split_on_sentences(self, text: str) -> List[str]:
        """
        Split very long texts on sentence boundaries, grouping into chunks.
        
        Args:
            text: Text to split
            
        Returns:
            List of segments (~500 chars each)
        """
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Group sentences into chunks of ~500 chars
        result = []
        current = []
        current_len = 0
        target_size = 500
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            current.append(sentence)
            current_len += len(sentence)
            
            if current_len >= target_size:
                result.append(' '.join(current))
                current = []
                current_len = 0
        
        # Don't forget remaining content
        if current:
            if result and current_len < 100:
                # Merge very small remainder with last segment
                result[-1] = result[-1] + ' ' + ' '.join(current)
            else:
                result.append(' '.join(current))
        
        return result if len(result) >= 2 else [text]
    
    def _split_on_codes(self, text: str, code_matches: List[re.Match]) -> List[str]:
        """
        Split text on clause code positions.
        
        Args:
            text: Text to split
            code_matches: List of regex matches for clause codes
            
        Returns:
            List of segments
        """
        if len(code_matches) < 2:
            return [text]
        
        segments = []
        start = 0
        
        # Split before each code (except the first one)
        for i, match in enumerate(code_matches[1:], 1):
            # Find a good split point (before the code, after previous segment)
            split_pos = match.start()
            
            # Try to find a newline or sentence boundary before the code
            # Look back up to 50 chars for a good split point
            lookback = min(50, split_pos - start)
            for j in range(split_pos, max(start, split_pos - lookback), -1):
                if text[j] == '\n' or (text[j] == '.' and j < len(text) - 1 and text[j+1] == ' '):
                    split_pos = j + 1
                    break
            
            segment = text[start:split_pos].strip()
            if segment:
                segments.append(segment)
            start = split_pos
        
        # Add final segment
        final_segment = text[start:].strip()
        if final_segment:
            segments.append(final_segment)
        
        return segments if len(segments) > 1 else [text]
    
    def _split_on_numbering(self, text: str) -> List[str]:
        """
        Split text on numbered items (1., 2., a), b), etc.).
        
        Args:
            text: Text to split
            
        Returns:
            List of segments
        """
        lines = text.split('\n')
        segments = []
        current_segment = []
        
        for line in lines:
            # Check if line starts with numbering pattern
            is_numbered = False
            for pattern in self.numbering_patterns:
                if re.match(pattern, line):
                    is_numbered = True
                    break
            
            if is_numbered:
                # Save previous segment if it exists
                if current_segment:
                    seg_text = '\n'.join(current_segment).strip()
                    if seg_text:
                        segments.append(seg_text)
                    current_segment = []
            
            current_segment.append(line)
        
        # Add final segment
        if current_segment:
            seg_text = '\n'.join(current_segment).strip()
            if seg_text:
                segments.append(seg_text)
        
        # Only return if we found multiple numbered items
        return segments if len(segments) >= 2 else [text]
    
    def _split_on_headers(self, text: str) -> List[str]:
        """
        Split text on headers/keywords (Artikel, Lid, etc.).
        
        Args:
            text: Text to split
            
        Returns:
            List of segments
        """
        # Patterns for headers
        header_patterns = [
            r'^(Artikel|ARTIKEL)\s+\d+',
            r'^(Lid|LID)\s+\d+',
            r'^###\s+',  # Markdown headers
            r'^[A-Z][A-Z\s]{10,}',  # ALL CAPS lines (likely headers)
        ]
        
        lines = text.split('\n')
        segments = []
        current_segment = []
        
        for line in lines:
            is_header = False
            for pattern in header_patterns:
                if re.match(pattern, line.strip()):
                    is_header = True
                    break
            
            if is_header:
                # Save previous segment
                if current_segment:
                    seg_text = '\n'.join(current_segment).strip()
                    if seg_text:
                        segments.append(seg_text)
                    current_segment = []
            
            current_segment.append(line)
        
        # Add final segment
        if current_segment:
            seg_text = '\n'.join(current_segment).strip()
            if seg_text:
                segments.append(seg_text)
        
        return segments if len(segments) >= 2 else [text]

