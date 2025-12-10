# hienfeld/services/document_similarity_service.py
"""
TF-IDF based document similarity service.

Provides:
- Fast keyword-based similarity (faster than embeddings)
- BM25 ranking for document retrieval
- Corpus training for domain-specific weighting

No external APIs required - runs entirely locally.
"""
from typing import List, Tuple, Optional, Dict
import numpy as np
from functools import lru_cache

from ..config import AppConfig
from ..logging_config import get_logger

logger = get_logger('document_similarity_service')


class DocumentSimilarityService:
    """
    TF-IDF and keyword-based document similarity.
    
    Advantages over embeddings:
    - Much faster (no neural network inference)
    - Works well for keyword-overlap matching
    - Can be trained on domain-specific corpus
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the document similarity service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self._dictionary = None
        self._tfidf_model = None
        self._corpus_tfidf = None
        self._corpus_texts: List[str] = []
        self._is_trained = False
        self._available = False
        
        if config.semantic.enable_tfidf:
            self._init_gensim()
    
    def _init_gensim(self) -> None:
        """Initialize gensim components."""
        try:
            from gensim import corpora
            from gensim.models import TfidfModel
            self._gensim_corpora = corpora
            self._TfidfModel = TfidfModel
            self._available = True
            logger.info("Gensim TF-IDF initialized")
        except ImportError:
            logger.warning("Gensim not installed. Install with: pip install gensim")
            self._available = False
    
    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available
    
    @property
    def is_trained(self) -> bool:
        """Check if model has been trained on a corpus."""
        return self._is_trained
    
    def train_on_corpus(self, documents: List[str]) -> None:
        """
        Train TF-IDF model on a corpus of documents.
        
        This should be called with the policy conditions/voorwaarden
        to learn domain-specific term weights.
        
        Args:
            documents: List of document texts
        """
        if not self._available:
            logger.warning("Cannot train: gensim not available")
            return
        
        if not documents:
            logger.warning("Cannot train: empty document list")
            return
        
        try:
            # Tokenize documents
            texts = [self._tokenize(doc) for doc in documents]
            
            # Filter empty texts
            texts = [t for t in texts if t]
            
            if not texts:
                logger.warning("No valid texts after tokenization")
                return
            
            # Create dictionary (word -> id mapping)
            self._dictionary = self._gensim_corpora.Dictionary(texts)
            
            # Filter extremes (optional: remove very rare/common words)
            self._dictionary.filter_extremes(
                no_below=1,  # Keep words appearing at least once
                no_above=0.9,  # Remove words appearing in >90% of docs
                keep_n=10000  # Keep top 10k words
            )
            
            # Create bag-of-words corpus
            corpus = [self._dictionary.doc2bow(text) for text in texts]
            
            # Train TF-IDF model
            self._tfidf_model = self._TfidfModel(corpus)
            
            # Store TF-IDF corpus for similarity lookups
            self._corpus_tfidf = self._tfidf_model[corpus]
            self._corpus_texts = documents
            self._is_trained = True
            
            logger.info(f"TF-IDF trained on {len(documents)} documents, "
                       f"vocabulary size: {len(self._dictionary)}")
            
        except Exception as e:
            logger.error(f"TF-IDF training failed: {e}")
            self._is_trained = False
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for TF-IDF.
        
        Args:
            text: Input text
            
        Returns:
            List of tokens
        """
        if not text:
            return []
        
        # Simple tokenization: lowercase, split on whitespace
        # Remove very short tokens
        tokens = [
            word.lower().strip() 
            for word in text.split() 
            if len(word.strip()) > 2
        ]
        return tokens
    
    def similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute TF-IDF similarity between two texts.
        
        Args:
            text_a: First text
            text_b: Second text
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not self._available or not self._is_trained:
            return 0.0
        
        if not text_a or not text_b:
            return 0.0
        
        try:
            # Tokenize
            tokens_a = self._tokenize(text_a)
            tokens_b = self._tokenize(text_b)
            
            if not tokens_a or not tokens_b:
                return 0.0
            
            # Convert to bag-of-words
            bow_a = self._dictionary.doc2bow(tokens_a)
            bow_b = self._dictionary.doc2bow(tokens_b)
            
            # Convert to TF-IDF
            tfidf_a = dict(self._tfidf_model[bow_a])
            tfidf_b = dict(self._tfidf_model[bow_b])
            
            # Compute cosine similarity
            return self._cosine_similarity_dict(tfidf_a, tfidf_b)
            
        except Exception as e:
            logger.debug(f"TF-IDF similarity failed: {e}")
            return 0.0
    
    def _cosine_similarity_dict(self, vec_a: Dict[int, float], vec_b: Dict[int, float]) -> float:
        """
        Compute cosine similarity between two sparse vectors.
        
        Args:
            vec_a: First vector as {id: weight}
            vec_b: Second vector as {id: weight}
            
        Returns:
            Cosine similarity score
        """
        if not vec_a or not vec_b:
            return 0.0
        
        # Get common keys
        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        
        if not common_keys:
            return 0.0
        
        # Compute dot product
        dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
        
        # Compute magnitudes
        mag_a = np.sqrt(sum(v ** 2 for v in vec_a.values()))
        mag_b = np.sqrt(sum(v ** 2 for v in vec_b.values()))
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot_product / (mag_a * mag_b)
    
    def find_similar_documents(
        self, 
        query: str, 
        top_k: int = 3
    ) -> List[Tuple[int, float, str]]:
        """
        Find most similar documents in the trained corpus.
        
        Args:
            query: Query text
            top_k: Number of results to return
            
        Returns:
            List of (index, score, text) tuples, sorted by score descending
        """
        if not self._available or not self._is_trained:
            return []
        
        try:
            from gensim.similarities import MatrixSimilarity
            
            # Create similarity index on demand
            index = MatrixSimilarity(self._corpus_tfidf)
            
            # Convert query to TF-IDF
            query_tokens = self._tokenize(query)
            query_bow = self._dictionary.doc2bow(query_tokens)
            query_tfidf = self._tfidf_model[query_bow]
            
            # Get similarities
            sims = index[query_tfidf]
            
            # Sort and get top-k
            top_indices = np.argsort(sims)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                score = float(sims[idx])
                if score > 0:
                    text = self._corpus_texts[idx] if idx < len(self._corpus_texts) else ""
                    results.append((int(idx), score, text))
            
            return results
            
        except Exception as e:
            logger.debug(f"Find similar documents failed: {e}")
            return []
    
    def keyword_overlap(self, text_a: str, text_b: str) -> float:
        """
        Compute simple keyword overlap ratio.
        
        Faster than TF-IDF, useful as a quick filter.
        
        Args:
            text_a: First text
            text_b: Second text
            
        Returns:
            Overlap ratio (Jaccard similarity)
        """
        tokens_a = set(self._tokenize(text_a))
        tokens_b = set(self._tokenize(text_b))
        
        if not tokens_a or not tokens_b:
            return 0.0
        
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        
        return len(intersection) / len(union) if union else 0.0
    
    def get_important_terms(self, text: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Get the most important terms in a text based on TF-IDF weights.
        
        Args:
            text: Input text
            top_k: Number of terms to return
            
        Returns:
            List of (term, weight) tuples
        """
        if not self._available or not self._is_trained:
            return []
        
        try:
            tokens = self._tokenize(text)
            bow = self._dictionary.doc2bow(tokens)
            tfidf = self._tfidf_model[bow]
            
            # Sort by weight
            sorted_terms = sorted(tfidf, key=lambda x: x[1], reverse=True)[:top_k]
            
            # Convert ids back to words
            results = []
            for term_id, weight in sorted_terms:
                word = self._dictionary.get(term_id)
                if word:
                    results.append((word, weight))
            
            return results
            
        except Exception:
            return []
    
    def clear(self) -> None:
        """Clear the trained model and corpus."""
        self._dictionary = None
        self._tfidf_model = None
        self._corpus_tfidf = None
        self._corpus_texts = []
        self._is_trained = False

