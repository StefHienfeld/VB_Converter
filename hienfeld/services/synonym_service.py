# hienfeld/services/synonym_service.py
"""
Synonym expansion service for insurance terminology.

Provides:
- Domain-specific insurance synonyms (fast, curated)
- Open Dutch WordNet integration (broader coverage)
- Synonym matching and text expansion

No external APIs required - runs entirely locally.
"""
import json
import os
from typing import Dict, Set, List, Optional
from functools import lru_cache
from pathlib import Path

from ..config import AppConfig
from ..logging_config import get_logger

logger = get_logger('synonym_service')


class SynonymService:
    """
    Synonym expansion service combining domain-specific and general synonyms.
    
    Uses:
    1. Insurance-specific synonym database (fast, curated)
    2. Open Dutch WordNet for broader coverage (optional)
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the synonym service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self._insurance_synonyms: Dict[str, Set[str]] = {}
        self._reverse_lookup: Dict[str, str] = {}  # word -> canonical
        self._wordnet = None
        self._wordnet_available = False
        
        if config.semantic.enable_synonyms:
            self._load_insurance_synonyms()
            self._init_wordnet()
    
    def _load_insurance_synonyms(self) -> None:
        """Load insurance-specific synonyms from JSON file."""
        try:
            # Find the synonyms file
            base_path = Path(__file__).parent.parent / "data" / "insurance_synonyms.json"
            
            if not base_path.exists():
                logger.warning(f"Insurance synonyms file not found at {base_path}")
                return
            
            with open(base_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Build synonym sets and reverse lookup
            for group_name, group_data in data.items():
                canonical = group_data.get('canonical', group_name)
                synonyms = set(group_data.get('synonyms', []))
                synonyms.add(canonical)  # Include canonical in set
                
                # Store the complete synonym set
                self._insurance_synonyms[canonical] = synonyms
                
                # Build reverse lookup (any word -> canonical)
                for word in synonyms:
                    self._reverse_lookup[word.lower()] = canonical
            
            logger.info(f"Loaded {len(self._insurance_synonyms)} insurance synonym groups")
            
        except Exception as e:
            logger.error(f"Failed to load insurance synonyms: {e}")
    
    def _init_wordnet(self) -> None:
        """Initialize Open Dutch WordNet for broader synonym coverage."""
        try:
            import wn
            
            # Try to load Dutch WordNet
            try:
                # Check if Dutch WordNet is downloaded
                self._wordnet = wn.Wordnet('odwn:nl')
                self._wordnet_available = True
                logger.info("Open Dutch WordNet loaded successfully")
            except wn.Error:
                # Try to download it
                try:
                    logger.info("Downloading Open Dutch WordNet...")
                    wn.download('odwn:nl')
                    self._wordnet = wn.Wordnet('odwn:nl')
                    self._wordnet_available = True
                    logger.info("Open Dutch WordNet downloaded and loaded")
                except Exception as e:
                    logger.warning(f"Could not download Dutch WordNet: {e}")
                    self._wordnet_available = False
                    
        except ImportError:
            logger.warning("wn package not installed. Install with: pip install wn")
            self._wordnet_available = False
    
    @property
    def is_available(self) -> bool:
        """Check if synonym service has any data loaded."""
        return bool(self._insurance_synonyms) or self._wordnet_available
    
    def get_canonical(self, word: str) -> str:
        """
        Get the canonical form of a word.
        
        Args:
            word: Word to look up
            
        Returns:
            Canonical form if found, otherwise the original word (lowercased)
        """
        word_lower = word.lower().strip()
        return self._reverse_lookup.get(word_lower, word_lower)
    
    @lru_cache(maxsize=1000)
    def get_synonyms(self, word: str) -> Set[str]:
        """
        Get all synonyms for a word.
        
        Args:
            word: Word to find synonyms for
            
        Returns:
            Set of synonyms (including the word itself)
        """
        word_lower = word.lower().strip()
        synonyms = {word_lower}
        
        # Check insurance synonyms first (fast, domain-specific)
        canonical = self._reverse_lookup.get(word_lower)
        if canonical and canonical in self._insurance_synonyms:
            synonyms.update(self._insurance_synonyms[canonical])
        
        # Check WordNet for additional synonyms
        if self._wordnet_available and self._wordnet:
            try:
                for synset in self._wordnet.synsets(word_lower):
                    for lemma in synset.lemmas():
                        synonyms.add(lemma.lower())
            except Exception:
                pass  # WordNet lookup failed, use insurance synonyms only
        
        return synonyms
    
    def is_synonym(self, word1: str, word2: str) -> bool:
        """
        Check if two words are synonyms.
        
        Args:
            word1: First word
            word2: Second word
            
        Returns:
            True if the words are synonyms
        """
        word1_lower = word1.lower().strip()
        word2_lower = word2.lower().strip()
        
        # Same word
        if word1_lower == word2_lower:
            return True
        
        # Check if they share the same canonical form (fast path)
        canonical1 = self._reverse_lookup.get(word1_lower)
        canonical2 = self._reverse_lookup.get(word2_lower)
        
        if canonical1 and canonical2 and canonical1 == canonical2:
            return True
        
        # Check full synonym sets
        syns1 = self.get_synonyms(word1)
        return word2_lower in syns1
    
    def count_synonym_matches(self, text1: str, text2: str) -> int:
        """
        Count how many words in text1 have synonyms in text2.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Number of synonym matches found
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        matches = 0
        for word1 in words1:
            syns = self.get_synonyms(word1)
            if syns & words2:  # Any overlap
                matches += 1
        
        return matches
    
    def synonym_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate synonym-based similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Count words in text1 that have synonyms in text2
        matches = 0
        for word1 in words1:
            syns = self.get_synonyms(word1)
            if syns & words2:
                matches += 1
        
        # Normalize by the smaller set size
        min_size = min(len(words1), len(words2))
        return matches / min_size if min_size > 0 else 0.0
    
    def expand_text_with_synonyms(self, text: str, max_synonyms_per_word: int = 2) -> str:
        """
        Expand text by adding synonyms.
        
        This creates a "fat" version of the text that includes synonyms,
        which can help with fuzzy matching.
        
        Args:
            text: Input text
            max_synonyms_per_word: Maximum synonyms to add per word
            
        Returns:
            Expanded text with synonyms included
        """
        words = text.lower().split()
        expanded = []
        
        for word in words:
            expanded.append(word)
            
            # Get synonyms (excluding the word itself)
            syns = self.get_synonyms(word) - {word}
            
            # Add top synonyms
            for syn in list(syns)[:max_synonyms_per_word]:
                expanded.append(syn)
        
        return " ".join(expanded)
    
    def canonicalize_text(self, text: str) -> str:
        """
        Replace words with their canonical forms.
        
        This normalizes text by replacing synonyms with their
        standard/canonical form.
        
        Args:
            text: Input text
            
        Returns:
            Text with words replaced by canonical forms
        """
        words = text.lower().split()
        canonical_words = []
        
        for word in words:
            canonical = self.get_canonical(word)
            canonical_words.append(canonical)
        
        return " ".join(canonical_words)
    
    def get_all_groups(self) -> Dict[str, Set[str]]:
        """Get all synonym groups."""
        return dict(self._insurance_synonyms)
    
    def add_synonym_group(self, canonical: str, synonyms: Set[str]) -> None:
        """
        Add or update a synonym group.
        
        Args:
            canonical: Canonical form
            synonyms: Set of synonyms
        """
        all_synonyms = set(synonyms)
        all_synonyms.add(canonical)
        
        self._insurance_synonyms[canonical] = all_synonyms
        
        for word in all_synonyms:
            self._reverse_lookup[word.lower()] = canonical
        
        # Clear the cache since we added new data
        self.get_synonyms.cache_clear()
    
    def clear_cache(self) -> None:
        """Clear the synonym lookup cache."""
        self.get_synonyms.cache_clear()

