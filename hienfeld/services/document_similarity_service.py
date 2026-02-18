# hienfeld/services/document_similarity_service.py
"""
TF-IDF based document similarity service using sklearn.

Provides:
- Fast keyword-based similarity (faster than embeddings)
- Cosine similarity for document retrieval
- Corpus training for domain-specific weighting

No external APIs required - runs entirely locally.

Performance note: sklearn TfidfVectorizer is 2-3x faster than gensim
and provides sparse matrix operations optimized with scipy.
"""
from typing import List, Tuple, Optional, Dict
import numpy as np
from functools import lru_cache

from ..config import AppConfig
from ..logging_config import get_logger

logger = get_logger('document_similarity_service')


class DocumentSimilarityService:
    """
    TF-IDF and keyword-based document similarity using sklearn.

    Advantages over embeddings:
    - Much faster (no neural network inference)
    - Works well for keyword-overlap matching
    - Can be trained on domain-specific corpus

    Advantages of sklearn over gensim:
    - 2-3x faster vectorization and similarity computation
    - Optimized sparse matrix operations via scipy
    - More active maintenance and better documentation
    """

    def __init__(self, config: AppConfig):
        """
        Initialize the document similarity service.

        Args:
            config: Application configuration
        """
        self.config = config
        self._vectorizer = None
        self._corpus_tfidf = None  # sparse matrix
        self._corpus_texts: List[str] = []
        self._is_trained = False
        self._available = False

        if config.semantic.enable_tfidf:
            self._init_sklearn()

    def _init_sklearn(self) -> None:
        """Initialize sklearn TF-IDF components."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            # Store references for later use
            self._TfidfVectorizer = TfidfVectorizer
            self._cosine_similarity = cosine_similarity
            self._available = True
            logger.info("sklearn TF-IDF initialized (faster than gensim)")
        except ImportError:
            logger.warning("sklearn not installed. Install with: pip install scikit-learn")
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
            logger.warning("Cannot train: sklearn not available")
            return

        if not documents:
            logger.warning("Cannot train: empty document list")
            return

        try:
            # Filter empty documents
            valid_documents = [doc for doc in documents if doc and doc.strip()]

            if not valid_documents:
                logger.warning("No valid texts after filtering")
                return

            # Create TF-IDF vectorizer with optimized settings
            # - max_features=5000: Limit vocabulary for speed
            # - min_df=1: Keep words appearing at least once
            # - max_df=0.9: Remove words appearing in >90% of docs
            # - norm='l2': L2 normalize for cosine similarity
            # - sublinear_tf=True: Apply log scaling to term frequency
            self._vectorizer = self._TfidfVectorizer(
                max_features=5000,
                min_df=1,
                max_df=0.9,
                norm='l2',
                sublinear_tf=True,
                lowercase=True,
                token_pattern=r'(?u)\b\w{3,}\b'  # Words with 3+ chars
            )

            # Fit and transform corpus (creates sparse matrix)
            self._corpus_tfidf = self._vectorizer.fit_transform(valid_documents)
            self._corpus_texts = valid_documents
            self._is_trained = True

            vocab_size = len(self._vectorizer.vocabulary_)
            logger.info(f"TF-IDF trained on {len(valid_documents)} documents, "
                       f"vocabulary size: {vocab_size}")

        except Exception as e:
            logger.error(f"TF-IDF training failed: {e}")
            self._is_trained = False

    def similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute TF-IDF cosine similarity between two texts.

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
            # Transform both texts using fitted vectorizer
            # This uses the vocabulary learned from the corpus
            tfidf_a = self._vectorizer.transform([text_a])
            tfidf_b = self._vectorizer.transform([text_b])

            # Compute cosine similarity (sklearn returns 2D array)
            sim_matrix = self._cosine_similarity(tfidf_a, tfidf_b)

            # Return scalar similarity value
            return float(sim_matrix[0, 0])

        except Exception as e:
            logger.debug(f"TF-IDF similarity failed: {e}")
            return 0.0

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
            # Transform query using fitted vectorizer
            query_tfidf = self._vectorizer.transform([query])

            # Compute cosine similarity with entire corpus (efficient sparse operation)
            similarities = self._cosine_similarity(query_tfidf, self._corpus_tfidf)

            # Get similarity scores as 1D array
            sims = similarities[0]

            # Get top-k indices (argsort in descending order)
            # Note: np.argsort returns ascending order, so we take last k and reverse
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

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for keyword overlap.

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        if not text:
            return []

        # Simple tokenization: lowercase, split on whitespace
        # Remove very short tokens (matching vectorizer's pattern)
        tokens = [
            word.lower().strip()
            for word in text.split()
            if len(word.strip()) > 2
        ]
        return tokens

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
            # Transform text
            tfidf_vector = self._vectorizer.transform([text])

            # Get feature names (vocabulary)
            feature_names = self._vectorizer.get_feature_names_out()

            # Get non-zero entries from sparse matrix
            # csr_matrix.nonzero() returns (row_indices, col_indices)
            _, col_indices = tfidf_vector.nonzero()

            # Collect term weights
            term_weights = []
            for col_idx in col_indices:
                weight = float(tfidf_vector[0, col_idx])
                term = feature_names[col_idx]
                term_weights.append((term, weight))

            # Sort by weight descending and return top_k
            term_weights.sort(key=lambda x: x[1], reverse=True)
            return term_weights[:top_k]

        except Exception:
            return []

    def clear(self) -> None:
        """Clear the trained model and corpus."""
        self._vectorizer = None
        self._corpus_tfidf = None
        self._corpus_texts = []
        self._is_trained = False
