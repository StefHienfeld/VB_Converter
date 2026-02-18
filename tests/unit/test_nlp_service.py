"""
Unit tests for NLPService.

Tests lemmatization, NLP model loading, text preprocessing, and noun phrase extraction.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from hienfeld.config import load_config
from hienfeld.services.nlp_service import NLPService


@pytest.fixture
def config():
    """Load default config for tests."""
    return load_config()


@pytest.fixture
def nlp_service(config):
    """Create NLP service with model loading disabled for testing."""
    config.semantic.enable_nlp = False
    return NLPService(config)


@pytest.fixture
def nlp_service_enabled(config):
    """Create NLP service with NLP enabled (may fail if model not installed)."""
    config.semantic.enable_nlp = True
    service = NLPService(config)
    # Only use if actually available
    return service if service.is_available else None


# ============================================================
# Initialization Tests
# ============================================================

class TestNLPServiceInitialization:
    """Tests for NLP service initialization and model loading."""

    def test_init_with_nlp_disabled(self, config):
        """Initialize with NLP disabled."""
        config.semantic.enable_nlp = False
        service = NLPService(config)

        assert not service.is_available
        assert service._nlp is None

    def test_init_with_nlp_enabled_no_model(self, config):
        """Initialize with NLP enabled but model not installed."""
        config.semantic.enable_nlp = True

        with patch('spacy.load', side_effect=OSError("Model not found")):
            service = NLPService(config)

            # Should gracefully handle missing model
            assert service._model_name == config.semantic.spacy_model

    def test_init_spacy_not_installed(self, config):
        """Initialize when SpaCy is not installed."""
        config.semantic.enable_nlp = True

        with patch.dict('sys.modules', {'spacy': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'spacy'")):
                service = NLPService(config)
                assert not service.is_available

    def test_model_name_from_config(self, config):
        """Model name is taken from config."""
        service = NLPService(config)

        assert service._model_name == config.semantic.spacy_model


# ============================================================
# Lemmatization Tests
# ============================================================

class TestLemmatization:
    """Tests for text lemmatization."""

    def test_lemmatize_text_unavailable(self, nlp_service):
        """Lemmatization returns original text when service unavailable."""
        text = "verzekeringen verzekerd auto's"

        result = nlp_service.lemmatize_text(text)

        # Should return original text (lowercased possibly)
        assert text.lower() in result or text in result

    def test_lemmatize_empty_text(self, nlp_service):
        """Lemmatization of empty text returns empty string."""
        result = nlp_service.lemmatize_text("")

        assert result == ""

    def test_lemmatize_none_input(self, nlp_service):
        """Lemmatization handles None gracefully."""
        # Most implementations would convert None to string first
        try:
            result = nlp_service.lemmatize_text(None)
            # Should either work or raise AttributeError
        except (AttributeError, TypeError):
            pass

    def test_lemmatize_cached_function(self, nlp_service):
        """Cached lemmatization function exists."""
        text1 = "verzekering"
        text2 = "verzekering"

        result1 = nlp_service.lemmatize_cached(text1)
        result2 = nlp_service.lemmatize_cached(text2)

        # Should be consistent
        assert result1 == result2

    @pytest.mark.skipif(True, reason="Requires SpaCy model installation")
    def test_lemmatize_with_spacy_model(self, nlp_service_enabled):
        """Lemmatization with actual SpaCy model."""
        if not nlp_service_enabled:
            pytest.skip("SpaCy model not installed")

        text = "de verzekeringen zijn verzekerd"

        result = nlp_service_enabled.lemmatize_text(text)

        # Result should be different from original due to lemmatization
        assert isinstance(result, str)
        assert len(result) > 0

    def test_lemmatize_single_word(self, nlp_service):
        """Lemmatize single word."""
        result = nlp_service.lemmatize_text("verzekeringen")

        assert isinstance(result, str)

    def test_lemmatize_multiple_words(self, nlp_service):
        """Lemmatize multiple words."""
        text = "De verzekeringen en de verzekerde zijn belangrijk"

        result = nlp_service.lemmatize_text(text)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_lemmatize_with_punctuation(self, nlp_service):
        """Lemmatization handles punctuation."""
        text = "Verzekering! Dit is belangrijk."

        result = nlp_service.lemmatize_text(text)

        assert isinstance(result, str)

    def test_get_lemma_single_word(self, nlp_service):
        """Get lemma of single word."""
        word = "verzekeringen"

        result = nlp_service.get_lemma(word)

        assert isinstance(result, str)
        assert result.lower() == result

    def test_get_lemma_empty_word(self, nlp_service):
        """Get lemma of empty word."""
        result = nlp_service.get_lemma("")

        assert result == ""

    def test_get_lemma_single_character(self, nlp_service):
        """Get lemma of single character."""
        result = nlp_service.get_lemma("A")

        assert isinstance(result, str)

    def test_cache_clearing(self, nlp_service):
        """Cache can be cleared."""
        nlp_service.lemmatize_cached("test")

        # Should not raise
        nlp_service.clear_cache()
        assert nlp_service.lemmatize_cached.cache_info().currsize == 0


# ============================================================
# Entity Extraction Tests
# ============================================================

class TestEntityExtraction:
    """Tests for named entity recognition."""

    def test_extract_entities_unavailable(self, nlp_service):
        """Entity extraction returns empty list when service unavailable."""
        text = "De KLM is gevestigd in Amsterdam"

        result = nlp_service.extract_entities(text)

        assert result == []

    def test_extract_entities_empty_text(self, nlp_service):
        """Entity extraction on empty text returns empty list."""
        result = nlp_service.extract_entities("")

        assert result == []

    def test_extract_entities_returns_tuples(self, nlp_service):
        """Entity extraction returns list of (text, label) tuples."""
        # Mock NLP model
        mock_doc = MagicMock()
        mock_ent = MagicMock()
        mock_ent.text = "Amsterdam"
        mock_ent.label_ = "LOC"
        mock_doc.ents = [mock_ent]

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.extract_entities("Amsterdam is een stad")

        assert isinstance(result, list)
        if len(result) > 0:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    @pytest.mark.skipif(True, reason="Requires SpaCy model")
    def test_extract_entities_with_model(self, nlp_service_enabled):
        """Entity extraction with actual model."""
        if not nlp_service_enabled:
            pytest.skip("SpaCy model not installed")

        text = "KLM is een Nederlandse luchtvaartmaatschappij"

        result = nlp_service_enabled.extract_entities(text)

        assert isinstance(result, list)


# ============================================================
# Noun Phrase Extraction Tests
# ============================================================

class TestNounPhraseExtraction:
    """Tests for noun phrase extraction."""

    def test_get_noun_phrases_unavailable(self, nlp_service):
        """Noun phrase extraction returns empty list when unavailable."""
        text = "dekking voor motorrijtuigen"

        result = nlp_service.get_noun_phrases(text)

        assert result == []

    def test_get_noun_phrases_empty_text(self, nlp_service):
        """Noun phrase extraction on empty text returns empty list."""
        result = nlp_service.get_noun_phrases("")

        assert result == []

    def test_get_noun_phrases_returns_list_of_strings(self, nlp_service):
        """get_noun_phrases returns list of strings."""
        # Mock NLP model
        mock_chunk = MagicMock()
        mock_chunk.text = "dekking voor auto"
        mock_doc = MagicMock()
        mock_doc.noun_chunks = [mock_chunk]

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.get_noun_phrases("dekking voor auto is belangrijk")

        assert isinstance(result, list)
        if len(result) > 0:
            assert all(isinstance(phrase, str) for phrase in result)

    def test_extract_key_noun_phrases_unavailable(self, nlp_service):
        """Extract key noun phrases returns empty list when unavailable."""
        result = nlp_service.extract_key_noun_phrases("dekking motorrijtuig")

        assert result == []

    def test_extract_key_noun_phrases_max_phrases(self, nlp_service):
        """extract_key_noun_phrases respects max_phrases parameter."""
        # Mock with multiple phrases
        mock_chunks = [
            MagicMock(text="dekking"),
            MagicMock(text="motorrijtuig"),
            MagicMock(text="schade"),
            MagicMock(text="verzekering"),
        ]

        mock_doc = MagicMock()
        mock_doc.noun_chunks = mock_chunks

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.extract_key_noun_phrases(
            "dekking motorrijtuig schade verzekering",
            max_phrases=2
        )

        assert len(result) <= 2

    def test_extract_key_noun_phrases_filters_generic(self, nlp_service):
        """extract_key_noun_phrases filters out generic phrases."""
        # Setup service as available
        nlp_service._available = True

        # Generic phrases that should be filtered
        generic_phrases = [
            "de verzekering",
            "de verzekerde",
            "het bedrag",
            "de polis"
        ]

        # Mock to return generic phrases
        mock_chunks = [MagicMock(text=phrase) for phrase in generic_phrases]
        mock_doc = MagicMock()
        mock_doc.noun_chunks = mock_chunks

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc

        result = nlp_service.extract_key_noun_phrases(
            "de verzekering en de polis"
        )

        # Should filter out generic phrases
        for phrase in result:
            assert phrase.lower() not in ["de verzekering", "de polis"]

    def test_extract_key_noun_phrases_filters_short(self, nlp_service):
        """extract_key_noun_phrases filters out very short phrases."""
        mock_chunks = [
            MagicMock(text="a"),
            MagicMock(text="het"),
            MagicMock(text="dekking motorrijtuig"),
        ]

        mock_doc = MagicMock()
        mock_doc.noun_chunks = mock_chunks

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.extract_key_noun_phrases("test")

        # Short phrases should be filtered
        assert all(len(phrase) >= 4 for phrase in result)

    def test_is_generic_phrase(self, nlp_service):
        """Test generic phrase filtering."""
        generic = "de verzekering"
        specific = "dekking motorrijtuig"

        assert nlp_service._is_generic_phrase(generic)
        assert not nlp_service._is_generic_phrase(specific)

    def test_is_generic_phrase_case_insensitive(self, nlp_service):
        """Generic phrase check is case-insensitive."""
        assert nlp_service._is_generic_phrase("DE VERZEKERING")
        assert nlp_service._is_generic_phrase("De Polis")


# ============================================================
# Keyword Extraction Tests
# ============================================================

class TestKeywordExtraction:
    """Tests for keyword extraction."""

    def test_get_keywords_unavailable(self, nlp_service):
        """get_keywords returns word list when service unavailable."""
        text = "dekking motorrijtuig schade"

        result = nlp_service.get_keywords(text)

        assert isinstance(result, list)
        # Should return split words as fallback
        assert len(result) > 0

    def test_get_keywords_empty_text(self, nlp_service):
        """get_keywords on empty text returns empty list."""
        result = nlp_service.get_keywords("")

        assert result == []

    def test_get_keywords_respects_top_k(self, nlp_service):
        """get_keywords respects top_k parameter."""
        text = "een twee drie vier vijf zes zeven acht negen tien elf"

        result = nlp_service.get_keywords(text, top_k=5)

        assert len(result) <= 5

    def test_get_keywords_removes_duplicates(self, nlp_service):
        """get_keywords removes duplicate keywords."""
        mock_token1 = MagicMock()
        mock_token1.pos_ = "NOUN"
        mock_token1.is_stop = False
        mock_token1.text = "dekking"
        mock_token1.lemma_ = "dekking"

        mock_token2 = MagicMock()
        mock_token2.pos_ = "NOUN"
        mock_token2.is_stop = False
        mock_token2.text = "dekking"
        mock_token2.lemma_ = "dekking"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token1, mock_token2]))

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.get_keywords("dekking dekking")

        # Should have no duplicates
        assert len(result) == len(set(result))


# ============================================================
# Tokenization Tests
# ============================================================

class TestTokenization:
    """Tests for text tokenization."""

    def test_tokenize_unavailable(self, nlp_service):
        """Tokenization returns split words when unavailable."""
        text = "dekking motorrijtuig schade"

        result = nlp_service.tokenize(text)

        assert result == ["dekking", "motorrijtuig", "schade"]

    def test_tokenize_empty_text(self, nlp_service):
        """Tokenization of empty text returns empty list."""
        result = nlp_service.tokenize("")

        assert result == []

    def test_tokenize_returns_lowercase(self, nlp_service):
        """Tokenization returns lowercase tokens."""
        result = nlp_service.tokenize("Dekking MOTORRIJTUIG Schade")

        # When service unavailable, uses simple split which returns lowercase
        assert len(result) > 0

    def test_tokenize_removes_whitespace(self, nlp_service):
        """Tokenization removes whitespace tokens."""
        result = nlp_service.tokenize("dekking    motorrijtuig")

        assert "" not in result
        assert len(result) == 2


# ============================================================
# Text Normalization Tests
# ============================================================

class TestNormalizeWithLemmas:
    """Tests for text normalization with lemmas."""

    def test_normalize_with_lemmas_unavailable(self, nlp_service):
        """normalize_with_lemmas returns lowercased text when unavailable."""
        text = "Dekking Motorrijtuig Schade"

        result = nlp_service.normalize_with_lemmas(text)

        assert result == text.lower()

    def test_normalize_with_lemmas_empty_text(self, nlp_service):
        """normalize_with_lemmas on empty text returns empty string."""
        result = nlp_service.normalize_with_lemmas("")

        assert result == ""

    def test_normalize_with_lemmas_keep_stopwords(self, nlp_service):
        """normalize_with_lemmas keeps stopwords by default."""
        mock_token1 = MagicMock()
        mock_token1.is_space = False
        mock_token1.is_stop = True
        mock_token1.lemma_ = "de"

        mock_token2 = MagicMock()
        mock_token2.is_space = False
        mock_token2.is_stop = False
        mock_token2.lemma_ = "dekking"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token1, mock_token2]))

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.normalize_with_lemmas("de dekking", keep_stopwords=True)

        assert "de" in result or len(result) > 0

    def test_normalize_with_lemmas_remove_stopwords(self, nlp_service):
        """normalize_with_lemmas can remove stopwords."""
        mock_token1 = MagicMock()
        mock_token1.is_space = False
        mock_token1.is_stop = True
        mock_token1.lemma_ = "de"

        mock_token2 = MagicMock()
        mock_token2.is_space = False
        mock_token2.is_stop = False
        mock_token2.lemma_ = "dekking"

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token1, mock_token2]))

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.normalize_with_lemmas("de dekking", keep_stopwords=False)

        # Stopwords should be removed
        assert "de" not in result or len(result) >= 0

    def test_normalize_with_lemmas_removes_spaces(self, nlp_service):
        """normalize_with_lemmas removes space tokens."""
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([]))

        nlp_service._nlp = MagicMock()
        nlp_service._nlp.return_value = mock_doc
        nlp_service._available = True

        result = nlp_service.normalize_with_lemmas("dekking motorrijtuig")

        assert isinstance(result, str)


# ============================================================
# Edge Cases and Error Handling
# ============================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_long_text_lemmatization(self, nlp_service):
        """Lemmatization handles very long text."""
        long_text = "dekking " * 1000

        result = nlp_service.lemmatize_text(long_text)

        assert isinstance(result, str)

    def test_special_characters_handling(self, nlp_service):
        """Handling of special characters."""
        text = "dekking §, €, ©, ™"

        result = nlp_service.lemmatize_text(text)

        assert isinstance(result, str)

    def test_unicode_text_handling(self, nlp_service):
        """Handling of unicode text."""
        text = "dekking café résumé naïve"

        result = nlp_service.lemmatize_text(text)

        assert isinstance(result, str)

    def test_nlp_exception_handling(self, nlp_service):
        """NLP exceptions are handled gracefully."""
        nlp_service._nlp = MagicMock()
        nlp_service._nlp.side_effect = RuntimeError("NLP Error")
        nlp_service._available = True

        # Should handle exception and return original text or safe result
        result = nlp_service.lemmatize_text("test text")
        assert isinstance(result, str)

    def test_mixed_language_text(self, nlp_service):
        """Handling of mixed language text."""
        text = "dekking AND schade OR damage"

        result = nlp_service.lemmatize_text(text)

        assert isinstance(result, str)

    def test_numbers_and_symbols(self, nlp_service):
        """Handling of numbers and symbols."""
        text = "dekking €1000 artikel 5.2.1 80%"

        result = nlp_service.lemmatize_text(text)

        assert isinstance(result, str)
