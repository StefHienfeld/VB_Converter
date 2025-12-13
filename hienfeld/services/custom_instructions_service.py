# hienfeld/services/custom_instructions_service.py
"""
Service for parsing and matching custom user instructions.

Custom instructions allow users to define their own rules for handling
specific types of text. Each instruction has:
- A search text (what to look for, matched semantically)
- An action (what to do when found)

Format:
    meeverzekerde ondernemingen
    → Vullen in partijenkaart

    sanctieclausule of embargo bepalingen
    → Verwijderen - mag weg

The service treats each instruction as a "virtual clause" and uses
the existing similarity services for semantic matching.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any
import re

from ..logging_config import get_logger

logger = get_logger('custom_instructions_service')


@dataclass
class CustomInstruction:
    """
    A single custom instruction from the user.
    
    Attributes:
        search_text: Text to search for (matched semantically)
        action: Custom action to return when matched
        original_text: Original text from user input (for debugging)
    """
    search_text: str
    action: str
    original_text: str = ""
    
    def __post_init__(self):
        # Clean up search text
        self.search_text = self.search_text.strip()
        self.action = self.action.strip()


@dataclass
class CustomInstructionMatch:
    """
    Result of a custom instruction match.
    
    Attributes:
        instruction: The matched instruction
        score: Similarity score (0.0 to 1.0)
        matched_text: The input text that was matched
    """
    instruction: CustomInstruction
    score: float
    matched_text: str


class CustomInstructionsService:
    """
    Service for parsing and matching custom user instructions.
    
    Uses existing similarity services for matching:
    - RapidFuzz for fuzzy text matching
    - SemanticSimilarityService for embedding-based matching (if available)
    - HybridSimilarityService for combined matching (if available)
    """
    
    # Default matching thresholds
    DEFAULT_FUZZY_THRESHOLD = 0.75
    DEFAULT_SEMANTIC_THRESHOLD = 0.70
    
    # Patterns for parsing instructions
    ACTION_ARROW_PATTERN = re.compile(r'^[→\->]+\s*', re.MULTILINE)
    
    def __init__(
        self,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
        fuzzy_service: Optional[Any] = None,
        semantic_service: Optional[Any] = None,
        hybrid_service: Optional[Any] = None
    ):
        """
        Initialize the custom instructions service.
        
        Args:
            fuzzy_threshold: Minimum score for fuzzy matching
            semantic_threshold: Minimum score for semantic matching
            fuzzy_service: RapidFuzzSimilarityService instance (optional)
            semantic_service: SemanticSimilarityService instance (optional)
            hybrid_service: HybridSimilarityService instance (optional)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold
        
        self._fuzzy_service = fuzzy_service
        self._semantic_service = semantic_service
        self._hybrid_service = hybrid_service
        
        self._instructions: List[CustomInstruction] = []
        self._indexed = False
    
    def parse_instructions(self, raw_text: str) -> List[CustomInstruction]:
        """
        Parse raw instruction text into structured instructions.
        
        Expected format:
            search text line 1
            → action line 1
            
            search text line 2
            → action line 2
        
        Arrow can be: → or -> or >
        
        Args:
            raw_text: Raw instruction text from user
            
        Returns:
            List of parsed CustomInstruction objects
        """
        if not raw_text or not raw_text.strip():
            return []
        
        instructions = []
        
        # Split by empty lines to get instruction blocks
        blocks = re.split(r'\n\s*\n', raw_text.strip())
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            instruction = self._parse_single_block(block)
            if instruction:
                instructions.append(instruction)
        
        logger.info(f"Parsed {len(instructions)} custom instructions")
        return instructions
    
    def _parse_single_block(self, block: str) -> Optional[CustomInstruction]:
        """
        Parse a single instruction block.
        
        Args:
            block: Text block containing one instruction
            
        Returns:
            CustomInstruction or None if parsing failed
        """
        lines = block.strip().split('\n')
        
        if len(lines) < 2:
            # Try to parse single line with arrow
            return self._parse_single_line(block)
        
        # Find the action line (starts with arrow)
        search_lines = []
        action_line = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is an action line
            if self._is_action_line(line):
                action_line = self._extract_action(line)
            else:
                search_lines.append(line)
        
        if not search_lines or not action_line:
            logger.debug(f"Could not parse instruction block: {block[:50]}...")
            return None
        
        search_text = ' '.join(search_lines)
        
        return CustomInstruction(
            search_text=search_text,
            action=action_line,
            original_text=block
        )
    
    def _parse_single_line(self, line: str) -> Optional[CustomInstruction]:
        """
        Try to parse a single line instruction.
        
        Format: search text → action
        
        Args:
            line: Single line of text
            
        Returns:
            CustomInstruction or None
        """
        # Try different arrow patterns
        for pattern in [' → ', ' -> ', ' > ']:
            if pattern in line:
                parts = line.split(pattern, 1)
                if len(parts) == 2:
                    return CustomInstruction(
                        search_text=parts[0].strip(),
                        action=parts[1].strip(),
                        original_text=line
                    )
        return None
    
    def _is_action_line(self, line: str) -> bool:
        """Check if a line is an action line (starts with arrow)."""
        line = line.strip()
        return (
            line.startswith('→') or 
            line.startswith('->') or 
            line.startswith('>')
        )
    
    def _extract_action(self, line: str) -> str:
        """Extract action text from action line."""
        line = line.strip()
        # Remove arrow prefix
        for prefix in ['→', '->', '>']:
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return line
    
    def load_instructions(self, raw_text: str) -> int:
        """
        Parse and load instructions for matching.
        
        Args:
            raw_text: Raw instruction text from user
            
        Returns:
            Number of instructions loaded
        """
        self._instructions = self.parse_instructions(raw_text)
        self._indexed = False
        
        # Index for semantic search if service is available
        if self._semantic_service and self._instructions:
            self._index_for_semantic_search()
        
        return len(self._instructions)
    
    def _index_for_semantic_search(self) -> None:
        """Index instructions for semantic search."""
        if not self._semantic_service or not self._instructions:
            return
        
        try:
            # Create dict of search texts
            texts = {
                f"instr_{i}": instr.search_text 
                for i, instr in enumerate(self._instructions)
            }
            self._semantic_service.index_texts(texts)
            self._indexed = True
            logger.info(f"Indexed {len(texts)} instructions for semantic search")
        except Exception as e:
            logger.warning(f"Failed to index instructions for semantic search: {e}")
            self._indexed = False
    
    def find_match(
        self, 
        input_text: str,
        use_semantic: bool = True,
        use_fuzzy: bool = True
    ) -> Optional[CustomInstructionMatch]:
        """
        Find the best matching instruction for input text.
        
        Tries matching in order:
        1. Hybrid similarity (if available) - best of both worlds
        2. Semantic similarity (if available and enabled)
        3. Fuzzy text similarity (always available)
        
        Args:
            input_text: Text to match against instructions
            use_semantic: Whether to use semantic matching
            use_fuzzy: Whether to use fuzzy matching
            
        Returns:
            CustomInstructionMatch or None if no match found
        """
        if not self._instructions:
            return None
        
        if not input_text or not input_text.strip():
            return None
        
        input_text = input_text.strip()
        best_match: Optional[CustomInstructionMatch] = None
        best_score = 0.0
        
        # Try hybrid matching first (combines fuzzy + semantic)
        if self._hybrid_service:
            match = self._match_with_hybrid(input_text)
            if match and match.score > best_score:
                best_match = match
                best_score = match.score
        
        # Try semantic matching if not using hybrid
        elif use_semantic and self._semantic_service and self._indexed:
            match = self._match_with_semantic(input_text)
            if match and match.score > best_score:
                best_match = match
                best_score = match.score
        
        # Try fuzzy matching as fallback or primary
        if use_fuzzy and self._fuzzy_service:
            match = self._match_with_fuzzy(input_text)
            if match and match.score > best_score:
                best_match = match
                best_score = match.score
        
        # Last resort: simple fuzzy without service
        if not best_match and use_fuzzy:
            match = self._match_with_simple_fuzzy(input_text)
            if match:
                best_match = match
        
        if best_match:
            logger.debug(
                f"Custom instruction match: '{input_text[:50]}...' -> "
                f"'{best_match.instruction.action}' (score: {best_match.score:.2f})"
            )
        
        return best_match
    
    def _match_with_hybrid(self, input_text: str) -> Optional[CustomInstructionMatch]:
        """Match using hybrid similarity service."""
        if not self._hybrid_service:
            return None
        
        best_match = None
        best_score = 0.0
        
        for instr in self._instructions:
            try:
                score = self._hybrid_service.similarity(input_text, instr.search_text)
                if score > best_score and score >= self.semantic_threshold:
                    best_score = score
                    best_match = CustomInstructionMatch(
                        instruction=instr,
                        score=score,
                        matched_text=input_text
                    )
            except Exception as e:
                logger.debug(f"Hybrid match failed: {e}")
        
        return best_match
    
    def _match_with_semantic(self, input_text: str) -> Optional[CustomInstructionMatch]:
        """Match using semantic similarity service."""
        if not self._semantic_service or not self._indexed:
            return None
        
        try:
            match = self._semantic_service.find_best_match(
                input_text, 
                min_score=self.semantic_threshold
            )
            if match:
                # Extract instruction index from ID
                idx = int(match.text_id.replace('instr_', ''))
                instr = self._instructions[idx]
                return CustomInstructionMatch(
                    instruction=instr,
                    score=match.score,
                    matched_text=input_text
                )
        except Exception as e:
            logger.debug(f"Semantic match failed: {e}")
        
        return None
    
    def _match_with_fuzzy(self, input_text: str) -> Optional[CustomInstructionMatch]:
        """Match using fuzzy similarity service."""
        if not self._fuzzy_service:
            return None
        
        best_match = None
        best_score = 0.0
        
        for instr in self._instructions:
            try:
                score = self._fuzzy_service.similarity(input_text, instr.search_text)
                if score > best_score and score >= self.fuzzy_threshold:
                    best_score = score
                    best_match = CustomInstructionMatch(
                        instruction=instr,
                        score=score,
                        matched_text=input_text
                    )
            except Exception as e:
                logger.debug(f"Fuzzy match failed: {e}")
        
        return best_match
    
    def _match_with_simple_fuzzy(self, input_text: str) -> Optional[CustomInstructionMatch]:
        """Simple substring/keyword matching as last resort."""
        input_lower = input_text.lower()
        
        for instr in self._instructions:
            search_lower = instr.search_text.lower()
            
            # Check if search text is contained in input
            if search_lower in input_lower:
                # Calculate a rough score based on coverage
                score = len(search_lower) / len(input_lower)
                score = min(0.9, score + 0.3)  # Boost but cap
                
                if score >= self.fuzzy_threshold:
                    return CustomInstructionMatch(
                        instruction=instr,
                        score=score,
                        matched_text=input_text
                    )
            
            # Check if input is contained in search text
            if input_lower in search_lower:
                score = len(input_lower) / len(search_lower)
                score = min(0.85, score + 0.2)
                
                if score >= self.fuzzy_threshold:
                    return CustomInstructionMatch(
                        instruction=instr,
                        score=score,
                        matched_text=input_text
                    )
        
        return None
    
    @property
    def instruction_count(self) -> int:
        """Get number of loaded instructions."""
        return len(self._instructions)
    
    @property
    def instructions(self) -> List[CustomInstruction]:
        """Get list of loaded instructions."""
        return self._instructions.copy()
    
    @property
    def is_loaded(self) -> bool:
        """Check if instructions have been loaded."""
        return len(self._instructions) > 0
    
    @property
    def has_semantic_matching(self) -> bool:
        """Check if semantic matching is available."""
        return self._semantic_service is not None and self._indexed
    
    def clear(self) -> None:
        """Clear all loaded instructions."""
        self._instructions = []
        self._indexed = False

