# hienfeld/services/nlp_service.py
"""
NLP preprocessing service using SpaCy for Dutch text analysis.

Provides:
- Lemmatization (verzekering → verzekeren)
- Named Entity Recognition (detect companies, locations)
- POS tagging
- Noun phrase extraction

No external APIs required - runs entirely locally.
"""
from typing import List, Tuple, Optional, Set
from functools import lru_cache

from ..config import AppConfig
from ..logging_config import get_logger

logger = get_logger('nlp_service')


class NLPService:
    """
    NLP preprocessing service for Dutch texts.
    
    Uses SpaCy's Dutch language model for advanced text analysis.
    Falls back gracefully if SpaCy is not available.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the NLP service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self._nlp = None
        self._available = False
        self._model_name = config.semantic.spacy_model
        
        if config.semantic.enable_nlp:
            self._init_spacy()
    
    def _init_spacy(self) -> None:
        """Initialize SpaCy with Dutch model."""
        try:
            import spacy
            
            # Try to load the model
            try:
                self._nlp = spacy.load(self._model_name)
                self._available = True
                logger.info(f"SpaCy loaded with model: {self._model_name}")
            except OSError:
                # Model not installed, try smaller model
                try:
                    self._nlp = spacy.load("nl_core_news_sm")
                    self._available = True
                    logger.warning(f"Model {self._model_name} not found, using nl_core_news_sm")
                except OSError:
                    logger.warning(
                        f"No Dutch SpaCy model found. Install with: "
                        f"python -m spacy download {self._model_name}"
                    )
                    self._available = False
                    
        except ImportError:
            logger.warning("SpaCy not installed. Install with: pip install spacy")
            self._available = False
    
    @property
    def is_available(self) -> bool:
        """Check if NLP service is available."""
        return self._available
    
    def lemmatize_text(self, text: str) -> str:
        """
        Convert words to their base/lemma form.
        
        Examples:
            "auto's verzekerd" → "auto verzekeren"
            "verzekeringen" → "verzekering"
        
        Args:
            text: Input text to lemmatize
            
        Returns:
            Text with words converted to lemmas
        """
        if not self._available or not text:
            return text
        
        try:
            doc = self._nlp(text)
            lemmas = [token.lemma_.lower() for token in doc if not token.is_space]
            return " ".join(lemmas)
        except Exception as e:
            logger.debug(f"Lemmatization failed: {e}")
            return text
    
    @lru_cache(maxsize=5000)
    def lemmatize_cached(self, text: str) -> str:
        """
        Cached version of lemmatize_text for repeated calls.
        
        Args:
            text: Input text to lemmatize
            
        Returns:
            Text with words converted to lemmas
        """
        return self.lemmatize_text(text)
    
    def get_lemma(self, word: str) -> str:
        """
        Get the lemma of a single word.
        
        Args:
            word: Single word to lemmatize
            
        Returns:
            Lemma of the word
        """
        if not self._available or not word:
            return word.lower()
        
        try:
            doc = self._nlp(word)
            if len(doc) > 0:
                return doc[0].lemma_.lower()
            return word.lower()
        except Exception:
            return word.lower()
    
    def extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text
            
        Returns:
            List of (entity_text, entity_label) tuples
            Labels: ORG (organization), LOC (location), PER (person), etc.
        """
        if not self._available or not text:
            return []
        
        try:
            doc = self._nlp(text)
            return [(ent.text, ent.label_) for ent in doc.ents]
        except Exception as e:
            logger.debug(f"Entity extraction failed: {e}")
            return []
    
    def get_noun_phrases(self, text: str) -> List[str]:
        """
        Extract noun phrases (key concepts) from text.
        
        Args:
            text: Input text
            
        Returns:
            List of noun phrases
        """
        if not self._available or not text:
            return []
        
        try:
            doc = self._nlp(text)
            return [chunk.text.lower() for chunk in doc.noun_chunks]
        except Exception as e:
            logger.debug(f"Noun phrase extraction failed: {e}")
            return []
    
    def get_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        Extract important keywords from text.
        
        Focuses on nouns and verbs that carry semantic meaning.
        
        Args:
            text: Input text
            top_k: Maximum number of keywords to return
            
        Returns:
            List of important keywords
        """
        if not self._available or not text:
            return text.lower().split()[:top_k] if text else []
        
        try:
            doc = self._nlp(text)
            
            # Filter for nouns and verbs, skip stopwords
            keywords = []
            for token in doc:
                if (
                    token.pos_ in ('NOUN', 'VERB', 'ADJ') 
                    and not token.is_stop 
                    and len(token.text) > 2
                ):
                    keywords.append(token.lemma_.lower())
            
            # Remove duplicates while preserving order
            seen = set()
            unique_keywords = []
            for kw in keywords:
                if kw not in seen:
                    seen.add(kw)
                    unique_keywords.append(kw)
            
            return unique_keywords[:top_k]
        except Exception as e:
            logger.debug(f"Keyword extraction failed: {e}")
            return text.lower().split()[:top_k]
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        if not self._available or not text:
            return text.split() if text else []
        
        try:
            doc = self._nlp(text)
            return [token.text.lower() for token in doc if not token.is_space]
        except Exception:
            return text.split()
    
    def normalize_with_lemmas(self, text: str, keep_stopwords: bool = True) -> str:
        """
        Normalize text using lemmatization and optional stopword removal.
        
        Args:
            text: Input text
            keep_stopwords: Whether to keep stopwords
            
        Returns:
            Normalized text
        """
        if not self._available or not text:
            return text.lower() if text else ""
        
        try:
            doc = self._nlp(text)
            
            tokens = []
            for token in doc:
                if token.is_space:
                    continue
                if not keep_stopwords and token.is_stop:
                    continue
                tokens.append(token.lemma_.lower())
            
            return " ".join(tokens)
        except Exception:
            return text.lower()
    
    def clear_cache(self) -> None:
        """Clear the lemmatization cache."""
        self.lemmatize_cached.cache_clear()

