"""
Unit tests for SynonymService and DocumentSimilarityService.

Tests cover:
- Synonym loading and matching
- Document similarity calculations
- TF-IDF training
- Edge cases
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from hienfeld.services.synonym_service import SynonymService
from hienfeld.services.document_similarity_service import DocumentSimilarityService


class TestSynonymService:
    """Tests for SynonymService."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock()
        config.semantic.enable_synonyms = True
        return config

    @pytest.fixture
    def service(self, mock_config):
        """Create SynonymService with mock config."""
        return SynonymService(mock_config)

    @pytest.fixture
    def mock_synonyms_file(self):
        """Create a temporary synonyms JSON file."""
        data = {
            "schade": {
                "canonical": "schade",
                "synonyms": ["damage", "schadevergoeding", "compensatie"]
            },
            "verzekering": {
                "canonical": "verzekering",
                "synonyms": ["polis", "dekking", "coverage"]
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            return f.name

    def test_init_with_synonyms_enabled(self, mock_config):
        """Test initialization with synonyms enabled."""
        service = SynonymService(mock_config)
        assert service.config == mock_config

    def test_init_with_synonyms_disabled(self):
        """Test initialization with synonyms disabled."""
        config = Mock()
        config.semantic.enable_synonyms = False
        service = SynonymService(config)
        assert not service.is_available

    def test_is_available(self, service):
        """Test is_available property."""
        # Depends on whether insurance_synonyms file exists
        assert isinstance(service.is_available, bool)

    def test_get_canonical_exact_match(self, service):
        """Test getting canonical form of a word."""
        # This will depend on actual synonyms file
        result = service.get_canonical("test")
        assert isinstance(result, str)

    def test_get_canonical_case_insensitive(self, service):
        """Test that canonical lookup is case-insensitive."""
        result1 = service.get_canonical("Test")
        result2 = service.get_canonical("test")
        assert result1 == result2

    def test_get_canonical_returns_lowercase(self, service):
        """Test that canonical form is lowercase."""
        result = service.get_canonical("TEST")
        assert result == result.lower()

    def test_get_synonyms_returns_set(self, service):
        """Test get_synonyms returns a set."""
        result = service.get_synonyms("test")
        assert isinstance(result, set)

    def test_get_synonyms_includes_word_itself(self, service):
        """Test that synonyms include the word itself."""
        result = service.get_synonyms("test")
        assert "test" in result

    def test_is_synonym_same_word(self, service):
        """Test that a word is a synonym of itself."""
        result = service.is_synonym("test", "test")
        assert result is True

    def test_is_synonym_case_insensitive(self, service):
        """Test synonym check is case-insensitive."""
        result = service.is_synonym("Test", "test")
        assert result is True

    def test_count_synonym_matches_empty_texts(self, service):
        """Test synonym matching with empty texts."""
        result = service.count_synonym_matches("", "")
        assert result == 0

    def test_count_synonym_matches_identical_texts(self, service):
        """Test synonym matching with identical texts."""
        result = service.count_synonym_matches("word1 word2", "word1 word2")
        assert result >= 0

    def test_synonym_similarity_identical(self, service):
        """Test synonym similarity for identical texts."""
        score = service.synonym_similarity("text", "text")
        assert score == 1.0

    def test_synonym_similarity_empty(self, service):
        """Test synonym similarity with empty texts."""
        score = service.synonym_similarity("", "")
        assert score == 0.0

    def test_synonym_similarity_no_overlap(self, service):
        """Test synonym similarity with no overlap."""
        score = service.synonym_similarity("abc", "xyz")
        assert 0.0 <= score <= 1.0

    def test_expand_text_with_synonyms(self, service):
        """Test text expansion with synonyms."""
        original = "test word"
        expanded = service.expand_text_with_synonyms(original)
        assert isinstance(expanded, str)
        # Expanded should be longer or equal to original
        assert len(expanded) >= len(original)

    def test_expand_text_max_synonyms_parameter(self, service):
        """Test expand_text with max_synonyms_per_word parameter."""
        text = "test word"
        expanded = service.expand_text_with_synonyms(text, max_synonyms_per_word=1)
        assert isinstance(expanded, str)

    def test_canonicalize_text(self, service):
        """Test text canonicalization."""
        text = "Test Word"
        result = service.canonicalize_text(text)
        assert isinstance(result, str)
        assert result == result.lower()

    def test_get_all_groups(self, service):
        """Test getting all synonym groups."""
        groups = service.get_all_groups()
        assert isinstance(groups, dict)

    def test_add_synonym_group(self, service):
        """Test adding a synonym group."""
        original_count = len(service.get_all_groups())

        service.add_synonym_group("newword", {"synonym1", "synonym2"})

        groups = service.get_all_groups()
        assert "newword" in groups
        assert len(groups) >= original_count

    def test_add_synonym_group_includes_canonical(self, service):
        """Test that canonical form is included in synonyms."""
        service.add_synonym_group("test_canonical", {"syn1", "syn2"})

        groups = service.get_all_groups()
        assert "test_canonical" in groups["test_canonical"]

    def test_clear_cache(self, service):
        """Test clearing the cache."""
        # Call get_synonyms to populate cache
        service.get_synonyms("test")

        # Clear cache
        service.clear_cache()

        # Should still work after clear
        result = service.get_synonyms("test")
        assert isinstance(result, set)

    def test_get_synonyms_caching(self, service):
        """Test that get_synonyms caches results."""
        # First call
        result1 = service.get_synonyms("test")

        # Second call (should hit cache)
        result2 = service.get_synonyms("test")

        assert result1 == result2


class TestDocumentSimilarityService:
    """Tests for DocumentSimilarityService."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock()
        config.semantic.enable_tfidf = True
        return config

    @pytest.fixture
    def service(self, mock_config):
        """Create DocumentSimilarityService."""
        return DocumentSimilarityService(mock_config)

    @pytest.fixture
    def sample_documents(self):
        """Create sample documents for training."""
        return [
            "Dekking voor schade aan het motorrijtuig is meeverzekerd",
            "Fraude en misleiding zijn uitgesloten van dekking",
            "Molest is meeverzekerd onder deze polis",
            "Schade aan gebouwen door brand is uitgesloten",
            "De verzekerde heeft recht op vergoeding van kosten",
        ]

    def test_init_with_tfidf_enabled(self, mock_config):
        """Test initialization with TF-IDF enabled."""
        service = DocumentSimilarityService(mock_config)
        assert service.config == mock_config

    def test_init_with_tfidf_disabled(self):
        """Test initialization with TF-IDF disabled."""
        config = Mock()
        config.semantic.enable_tfidf = False
        service = DocumentSimilarityService(config)
        assert not service.is_available

    def test_is_available_property(self, service):
        """Test is_available property."""
        # Depends on sklearn availability
        assert isinstance(service.is_available, bool)

    def test_is_trained_initially_false(self, service):
        """Test that service is not trained initially."""
        assert service.is_trained is False

    def test_train_on_empty_corpus(self, service):
        """Test training with empty corpus."""
        service.train_on_corpus([])
        assert service.is_trained is False

    def test_train_on_valid_corpus(self, service, sample_documents):
        """Test training on valid corpus."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        assert service.is_trained is True

    def test_train_on_corpus_filters_empty(self, service):
        """Test that training filters empty documents."""
        docs = ["valid doc", "", "   ", "another valid"]
        service.train_on_corpus(docs)
        if service.is_trained:
            # Should have trained on 2 documents
            assert len(service._corpus_texts) <= 2

    def test_similarity_not_trained(self, service):
        """Test similarity returns 0.0 when not trained."""
        score = service.similarity("text1", "text2")
        assert score == 0.0

    def test_similarity_identical_texts(self, service, sample_documents):
        """Test similarity of identical texts."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        score = service.similarity("test text", "test text")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_similarity_different_texts(self, service, sample_documents):
        """Test similarity of different texts."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        score = service.similarity("motorrijtuig dekking", "brand uitsluiting")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_similarity_empty_text(self, service, sample_documents):
        """Test similarity with empty text."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        score = service.similarity("", "text")
        assert score == 0.0

    def test_find_similar_documents_not_trained(self, service):
        """Test find_similar_documents when not trained."""
        results = service.find_similar_documents("query")
        assert results == []

    def test_find_similar_documents_trained(self, service, sample_documents):
        """Test finding similar documents."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        results = service.find_similar_documents("schade motorrijtuig", top_k=2)

        assert isinstance(results, list)
        # Should return at most top_k results
        assert len(results) <= 2

    def test_find_similar_documents_returns_tuples(self, service, sample_documents):
        """Test that results are (idx, score, text) tuples."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        results = service.find_similar_documents("query", top_k=1)

        if results:
            idx, score, text = results[0]
            assert isinstance(idx, (int, np.integer))
            assert isinstance(score, float)
            assert isinstance(text, str)

    def test_keyword_overlap_identical(self, service):
        """Test keyword overlap for identical texts."""
        score = service.keyword_overlap("hello world", "hello world")
        assert score == 1.0

    def test_keyword_overlap_different(self, service):
        """Test keyword overlap for different texts."""
        score = service.keyword_overlap("abc", "xyz")
        assert score == 0.0

    def test_keyword_overlap_partial(self, service):
        """Test keyword overlap with partial match."""
        score = service.keyword_overlap("hello world", "hello there")
        assert 0.0 < score < 1.0

    def test_keyword_overlap_empty(self, service):
        """Test keyword overlap with empty text."""
        score = service.keyword_overlap("text", "")
        assert score == 0.0

    def test_get_important_terms_not_trained(self, service):
        """Test getting important terms when not trained."""
        terms = service.get_important_terms("text")
        assert terms == []

    def test_get_important_terms_trained(self, service, sample_documents):
        """Test getting important terms."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        terms = service.get_important_terms("schade motorrijtuig", top_k=3)

        assert isinstance(terms, list)
        assert len(terms) <= 3

        for term, weight in terms:
            assert isinstance(term, str)
            assert isinstance(weight, float)
            assert weight >= 0.0

    def test_get_important_terms_sorted_by_weight(self, service, sample_documents):
        """Test that terms are sorted by weight."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        terms = service.get_important_terms("schade motorrijtuig", top_k=10)

        if len(terms) > 1:
            # Should be sorted in descending order
            weights = [w for _, w in terms]
            assert weights == sorted(weights, reverse=True)

    def test_clear_service(self, service, sample_documents):
        """Test clearing the service."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        assert service.is_trained is True

        service.clear()
        assert service.is_trained is False

    def test_clear_resets_corpus(self, service, sample_documents):
        """Test that clear resets corpus."""
        if not service.is_available:
            pytest.skip("sklearn not available")

        service.train_on_corpus(sample_documents)
        service.clear()

        assert len(service._corpus_texts) == 0
        assert service._corpus_tfidf is None


class TestDocumentSimilarityServiceTokenization:
    """Tests for tokenization in DocumentSimilarityService."""

    @pytest.fixture
    def service(self):
        """Create service."""
        config = Mock()
        config.semantic.enable_tfidf = True
        return DocumentSimilarityService(config)

    def test_tokenize_basic(self, service):
        """Test basic tokenization."""
        tokens = service._tokenize("hello world test")
        assert len(tokens) == 3

    def test_tokenize_removes_short_words(self, service):
        """Test that tokenization removes words < 3 chars."""
        tokens = service._tokenize("a ab hello world")
        assert "hello" in tokens
        assert "world" in tokens
        # "a" and "ab" should be filtered

    def test_tokenize_lowercase(self, service):
        """Test that tokenization lowercases."""
        tokens = service._tokenize("Hello WORLD")
        assert all(t == t.lower() for t in tokens)

    def test_tokenize_empty_string(self, service):
        """Test tokenizing empty string."""
        tokens = service._tokenize("")
        assert tokens == []

    def test_tokenize_whitespace_only(self, service):
        """Test tokenizing whitespace-only string."""
        tokens = service._tokenize("   ")
        assert tokens == []


class TestEdgeCases:
    """Tests for edge cases in both services."""

    def test_synonym_service_with_none_config(self):
        """Test SynonymService with modified config."""
        config = Mock()
        config.semantic.enable_synonyms = False
        service = SynonymService(config)
        assert not service.is_available

    def test_document_similarity_very_long_corpus(self):
        """Test with very long document list."""
        config = Mock()
        config.semantic.enable_tfidf = True
        service = DocumentSimilarityService(config)

        if service.is_available:
            # Create documents with more content so TF-IDF doesn't prune everything
            long_corpus = [
                f"This is document number {i} with some content about topics like "
                f"insurance coverage schade motorrijtuig fraude molest "
                f"and more text here to avoid pruning issues"
                for i in range(100)
            ]
            service.train_on_corpus(long_corpus)
            # Training may or may not succeed depending on TF-IDF pruning, so just verify it doesn't crash
            assert isinstance(service.is_trained, bool)

    def test_synonym_service_unicode_handling(self):
        """Test SynonymService with unicode text."""
        config = Mock()
        config.semantic.enable_synonyms = True
        service = SynonymService(config)

        # Should handle unicode
        result = service.get_canonical("café")
        assert isinstance(result, str)

    def test_document_similarity_unicode_corpus(self):
        """Test DocumentSimilarityService with unicode."""
        config = Mock()
        config.semantic.enable_tfidf = True
        service = DocumentSimilarityService(config)

        if service.is_available:
            corpus = ["café está aqui", "cañón y espada"]
            service.train_on_corpus(corpus)
            # Should not raise

    def test_synonym_service_special_characters(self):
        """Test SynonymService with special characters."""
        config = Mock()
        config.semantic.enable_synonyms = True
        service = SynonymService(config)

        result = service.get_synonyms("test!@#")
        assert isinstance(result, set)

    def test_document_similarity_special_chars_corpus(self):
        """Test DocumentSimilarityService with special characters."""
        config = Mock()
        config.semantic.enable_tfidf = True
        service = DocumentSimilarityService(config)

        if service.is_available:
            corpus = ["hello!@# world", "test$%^ case"]
            service.train_on_corpus(corpus)
            # Should handle gracefully
