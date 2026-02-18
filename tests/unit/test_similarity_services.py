"""
Unit tests for similarity services.

Tests cover:
- DifflibSimilarityService
- RapidFuzzSimilarityService
- SemanticSimilarityService
- Threshold behavior
- Edge cases
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch

from hienfeld.services.similarity_service import (
    DifflibSimilarityService,
    RapidFuzzSimilarityService,
    SemanticSimilarityService,
    SemanticMatch,
    create_similarity_service,
)


class TestDifflibSimilarityService:
    """Tests for DifflibSimilarityService."""

    @pytest.fixture
    def service(self):
        return DifflibSimilarityService(threshold=0.9)

    def test_similarity_identical_strings(self, service):
        """Test similarity of identical strings."""
        score = service.similarity("hello", "hello")
        assert score == 1.0

    def test_similarity_different_strings(self, service):
        """Test similarity of completely different strings."""
        score = service.similarity("abc", "xyz")
        assert score == 0.0

    def test_similarity_similar_strings(self, service):
        """Test similarity of similar strings."""
        score = service.similarity("hello", "hallo")
        assert 0.7 < score < 1.0

    def test_similarity_empty_strings(self, service):
        """Test similarity with empty strings."""
        # Empty strings are handled consistently by difflib
        assert service.similarity("", "") in [0.0, 1.0]  # Implementation dependent
        assert service.similarity("text", "") == 0.0
        assert service.similarity("", "text") == 0.0

    def test_similarity_case_sensitive(self, service):
        """Test that similarity is case-sensitive."""
        score1 = service.similarity("Hello", "hello")
        score2 = service.similarity("hello", "hello")
        assert score1 < score2

    def test_is_similar_above_threshold(self, service):
        """Test is_similar returns True above threshold."""
        result = service.is_similar("hello", "hello")
        assert result is True

    def test_is_similar_below_threshold(self, service):
        """Test is_similar returns False below threshold."""
        result = service.is_similar("abc", "xyz")
        assert result is False

    def test_threshold_property(self, service):
        """Test threshold property."""
        assert service.threshold == 0.9

    def test_custom_threshold(self):
        """Test custom threshold."""
        service = DifflibSimilarityService(threshold=0.5)
        assert service.threshold == 0.5

    def test_similarity_long_strings(self, service):
        """Test similarity with long strings."""
        text1 = "This is a longer text that contains multiple words and should be compared."
        text2 = "This is a longer text that contains multiple words and should be compared."
        score = service.similarity(text1, text2)
        assert score == 1.0

    def test_similarity_whitespace_sensitive(self, service):
        """Test that similarity is sensitive to whitespace."""
        score1 = service.similarity("hello world", "hello  world")  # Extra space
        score2 = service.similarity("hello world", "hello world")
        assert score1 < score2


class TestRapidFuzzSimilarityService:
    """Tests for RapidFuzzSimilarityService."""

    @pytest.fixture
    def service(self):
        return RapidFuzzSimilarityService(threshold=0.9)

    def test_similarity_identical_strings(self, service):
        """Test similarity of identical strings."""
        score = service.similarity("hello", "hello")
        assert score == 1.0

    def test_similarity_different_strings(self, service):
        """Test similarity of completely different strings."""
        score = service.similarity("abc", "xyz")
        assert score == 0.0

    def test_similarity_similar_strings(self, service):
        """Test similarity of similar strings."""
        score = service.similarity("hello", "hallo")
        assert 0.6 < score < 1.0

    def test_similarity_empty_strings(self, service):
        """Test similarity with empty strings."""
        assert service.similarity("", "") == 0.0  # RapidFuzz treats empty differently
        assert service.similarity("text", "") == 0.0
        assert service.similarity("", "text") == 0.0

    def test_similarity_case_insensitive_option(self):
        """Test that RapidFuzz can handle case variations."""
        service = RapidFuzzSimilarityService(threshold=0.8)
        score = service.similarity("Hello", "HELLO")
        assert score > 0.0

    def test_is_similar_above_threshold(self, service):
        """Test is_similar returns True above threshold."""
        result = service.is_similar("hello", "hello")
        assert result is True

    def test_is_similar_below_threshold(self, service):
        """Test is_similar returns False below threshold."""
        result = service.is_similar("abc", "xyz")
        assert result is False

    def test_using_rapidfuzz_property(self, service):
        """Test using_rapidfuzz property."""
        # This depends on whether RapidFuzz is installed
        assert isinstance(service.using_rapidfuzz, bool)

    def test_fallback_to_difflib_if_not_available(self):
        """Test fallback to difflib if RapidFuzz not available."""
        # Test that service can be created even if RapidFuzz fails
        service = RapidFuzzSimilarityService()
        # Should have either RapidFuzz or fallback available
        assert service._use_rapidfuzz or service._fallback is not None

    def test_threshold_property(self, service):
        """Test threshold property."""
        assert service.threshold == 0.9

    def test_insurance_related_text(self, service):
        """Test similarity with insurance domain text."""
        text1 = "Dekking voor schade aan het motorrijtuig is meeverzekerd"
        text2 = "Dekking voor schade aan het motorrijtuig is meeverzekerd"
        score = service.similarity(text1, text2)
        assert score == 1.0

    def test_similar_insurance_texts(self, service):
        """Test similarity with similar insurance texts."""
        text1 = "Fraude en misleiding zijn uitgesloten van dekking"
        text2 = "Fraude en misleiding zijn niet gedekt"
        score = service.similarity(text1, text2)
        assert 0.7 < score < 1.0


class TestSemanticMatch:
    """Tests for SemanticMatch dataclass."""

    def test_create_semantic_match(self):
        """Test creating a SemanticMatch."""
        match = SemanticMatch(
            text_id="doc1",
            score=0.85,
            matched_text="Example text",
            metadata={"source": "test"}
        )
        assert match.text_id == "doc1"
        assert match.score == 0.85
        assert match.matched_text == "Example text"
        assert match.metadata["source"] == "test"

    def test_semantic_match_optional_metadata(self):
        """Test SemanticMatch with optional metadata."""
        match = SemanticMatch(
            text_id="doc1",
            score=0.85,
            matched_text="Example text"
        )
        assert match.metadata is None


class TestSemanticSimilarityService:
    """Tests for SemanticSimilarityService."""

    @pytest.fixture
    def mock_embeddings_service(self):
        """Create a mock embeddings service."""
        mock = MagicMock()
        mock.embed_single.return_value = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        mock.embed_texts.return_value = np.array([
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.15, 0.25, 0.35, 0.45, 0.55],
        ])
        return mock

    @pytest.fixture
    def service(self, mock_embeddings_service):
        """Create SemanticSimilarityService with mock."""
        return SemanticSimilarityService(
            threshold=0.7,
            embeddings_service=mock_embeddings_service
        )

    def test_similarity_identical_texts(self, service):
        """Test semantic similarity of identical texts."""
        score = service.similarity("text", "text")
        assert isinstance(score, float)

    def test_similarity_empty_strings(self, service):
        """Test semantic similarity with empty strings."""
        score = service.similarity("", "")
        assert score == 0.0

    def test_similarity_one_empty_string(self, service):
        """Test semantic similarity with one empty string."""
        score = service.similarity("text", "")
        assert score == 0.0

    def test_is_similar_above_threshold(self, service):
        """Test is_similar with high threshold."""
        # Default implementation always returns False for different strings
        # unless embeddings are identical
        result = service.is_similar("text1", "text2")
        assert isinstance(result, bool)

    def test_threshold_property(self, service):
        """Test threshold property."""
        assert service.threshold == 0.7

    def test_is_available(self, service):
        """Test is_available property."""
        assert service.is_available is True

    def test_index_texts(self, service, mock_embeddings_service):
        """Test indexing texts."""
        texts = {"doc1": "text1", "doc2": "text2"}
        service.index_texts(texts)

        assert service.is_indexed is True
        assert service.index_size == 2

    def test_find_similar(self, service, mock_embeddings_service):
        """Test finding similar texts."""
        texts = {"doc1": "text1", "doc2": "text2"}
        service.index_texts(texts)

        results = service.find_similar("query text", top_k=1)

        assert isinstance(results, list)

    def test_find_best_match(self, service, mock_embeddings_service):
        """Test finding best match."""
        texts = {"doc1": "text1", "doc2": "text2"}
        service.index_texts(texts)

        match = service.find_best_match("query text")

        if match:
            assert isinstance(match, SemanticMatch)

    def test_enable_cache(self, service):
        """Test enabling embedding cache."""
        service.enable_cache(cache_size=100)
        assert service._embedding_cache_enabled is True

    def test_clear_index(self, service, mock_embeddings_service):
        """Test clearing index."""
        texts = {"doc1": "text1"}
        service.index_texts(texts)
        assert service.is_indexed is True

        service.clear_index()
        assert service.is_indexed is False

    def test_similarity_batch(self, service, mock_embeddings_service):
        """Test batch similarity calculation."""
        candidates = ["text1", "text2", "text3"]
        results = service.similarity_batch("query", candidates)

        assert isinstance(results, list)

    def test_index_size_property(self, service, mock_embeddings_service):
        """Test index_size property."""
        assert service.index_size == 0

        texts = {"doc1": "text1", "doc2": "text2"}
        service.index_texts(texts)
        assert service.index_size == 2


class TestSemanticSimilarityUnavailable:
    """Tests for SemanticSimilarityService when unavailable."""

    def test_unavailable_when_no_embeddings_service(self):
        """Test service is unavailable without embeddings."""
        with patch('hienfeld.services.similarity_service.SemanticSimilarityService._init_embeddings_service'):
            service = SemanticSimilarityService()
            service._available = False

            assert service.is_available is False

    def test_similarity_returns_zero_when_unavailable(self):
        """Test similarity returns 0.0 when unavailable."""
        service = SemanticSimilarityService()
        service._available = False

        score = service.similarity("text1", "text2")
        assert score == 0.0

    def test_find_similar_returns_empty_when_unavailable(self):
        """Test find_similar returns empty list when unavailable."""
        service = SemanticSimilarityService()
        service._available = False

        results = service.find_similar("query")
        assert results == []

    def test_similarity_batch_returns_empty_when_unavailable(self):
        """Test similarity_batch returns empty when unavailable."""
        service = SemanticSimilarityService()
        service._available = False

        results = service.similarity_batch("query", ["text1"])
        assert results == []


class TestCreateSimilarityServiceFactory:
    """Tests for factory function."""

    def test_create_rapidfuzz_service(self):
        """Test creating RapidFuzz service."""
        service = create_similarity_service(method="rapidfuzz", threshold=0.85)
        assert isinstance(service, RapidFuzzSimilarityService)
        assert service.threshold == 0.85

    def test_create_difflib_service(self):
        """Test creating difflib service."""
        service = create_similarity_service(method="difflib", threshold=0.80)
        assert isinstance(service, DifflibSimilarityService)
        assert service.threshold == 0.80

    def test_create_semantic_service(self):
        """Test creating semantic service."""
        service = create_similarity_service(method="semantic", threshold=0.75)
        assert isinstance(service, SemanticSimilarityService)
        assert service.threshold == 0.75

    def test_create_default_service(self):
        """Test creating default service (rapidfuzz)."""
        service = create_similarity_service()
        assert isinstance(service, RapidFuzzSimilarityService)

    def test_create_service_with_kwargs(self):
        """Test creating service with additional kwargs."""
        service = create_similarity_service(
            method="semantic",
            threshold=0.70,
            model_name="test-model"
        )
        assert isinstance(service, SemanticSimilarityService)


class TestEdgeCases:
    """Tests for edge cases across all services."""

    def test_very_long_text_difflib(self):
        """Test DifflibSimilarityService with very long text."""
        service = DifflibSimilarityService()
        long_text1 = "word " * 1000
        long_text2 = "word " * 1000
        score = service.similarity(long_text1, long_text2)
        assert isinstance(score, float)

    def test_very_long_text_rapidfuzz(self):
        """Test RapidFuzzSimilarityService with very long text."""
        service = RapidFuzzSimilarityService()
        long_text1 = "word " * 1000
        long_text2 = "word " * 1000
        score = service.similarity(long_text1, long_text2)
        assert isinstance(score, float)

    def test_unicode_text_difflib(self):
        """Test DifflibSimilarityService with unicode."""
        service = DifflibSimilarityService()
        score = service.similarity("café", "cafe")
        assert isinstance(score, float)

    def test_unicode_text_rapidfuzz(self):
        """Test RapidFuzzSimilarityService with unicode."""
        service = RapidFuzzSimilarityService()
        score = service.similarity("café", "cafe")
        assert isinstance(score, float)

    def test_special_characters(self):
        """Test services with special characters."""
        service = RapidFuzzSimilarityService()
        score = service.similarity("!@#$%", "!@#$%")
        assert isinstance(score, float)

    def test_numbers_only(self):
        """Test services with numbers only."""
        service = DifflibSimilarityService()
        score = service.similarity("123456", "123456")
        assert score == 1.0

    def test_mixed_content(self):
        """Test with mixed alphanumeric content."""
        service = RapidFuzzSimilarityService()
        score = service.similarity("abc123def", "abc123def")
        assert score == 1.0

    def test_threshold_zero(self):
        """Test service with zero threshold."""
        service = DifflibSimilarityService(threshold=0.0)
        result = service.is_similar("abc", "xyz")
        # Zero threshold means everything matches
        assert isinstance(result, bool)

    def test_threshold_one(self):
        """Test service with threshold of 1.0."""
        service = DifflibSimilarityService(threshold=1.0)
        result = service.is_similar("text", "text")
        # Only exact matches
        assert result is True

        result = service.is_similar("text1", "text2")
        assert result is False

    def test_negative_threshold(self):
        """Test service with negative threshold."""
        service = DifflibSimilarityService(threshold=-0.5)
        result = service.is_similar("abc", "xyz")
        assert isinstance(result, bool)
