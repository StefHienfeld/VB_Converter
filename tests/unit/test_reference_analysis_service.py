"""
Unit tests for ReferenceAnalysisService.

Tests cover:
- Loading reference files from Excel
- Reference matching (exact, fuzzy, semantic)
- Frequency calculations
- Statistics tracking
- Edge cases and error handling
"""

import pytest
from io import BytesIO
import pandas as pd
from unittest.mock import Mock, MagicMock, patch

from hienfeld.services.reference_analysis_service import ReferenceAnalysisService
from hienfeld.domain.reference import (
    ReferenceClause,
    ReferenceMatch,
    ComparisonStatus,
)


@pytest.fixture
def mock_similarity_service():
    """Create a mock similarity service."""
    mock = Mock()
    mock.similarity.return_value = 0.85
    return mock


@pytest.fixture
def mock_hybrid_similarity_service():
    """Create a mock hybrid similarity service."""
    mock = Mock()
    mock.similarity.return_value = 0.80
    return mock


@pytest.fixture
def config():
    """Create a mock config object."""
    mock = Mock()
    return mock


@pytest.fixture
def reference_service(config, mock_similarity_service):
    """Create a ReferenceAnalysisService instance."""
    return ReferenceAnalysisService(config, mock_similarity_service)


@pytest.fixture
def sample_excel_bytes():
    """Create sample Excel file bytes for testing."""
    data = {
        'Tekst': [
            'Dekking voor schade aan het motorrijtuig is meeverzekerd',
            'Fraude en misleiding zijn uitgesloten',
            'Molest is meeverzekerd',
            'nan',  # Empty row
            '',  # Empty row
        ],
        'Frequentie': [5, 3, 2, 1, 1],
        'Advies': ['BEHOUDEN', 'VERWIJDEREN', 'BEHOUDEN', 'SKIP', 'SKIP'],
        'Vertrouwen': ['Hoog', 'Hoog', 'Midden', 'Laag', 'Laag'],
        'Artikel': ['Art 5', 'Art 2.8', 'Art 2.14', 'Art 0', 'Art 0'],
    }
    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name='Sheet1')
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def sample_excel_with_policy():
    """Create Excel file with policy numbers."""
    data = {
        'Tekst': [
            'Policy A text',
            'Policy B text',
            'Policy A text',  # Same text, different policy
        ],
        'Frequentie': [5, 3, 2],
        'Advies': ['BEHOUDEN', 'VERWIJDEREN', 'BEHOUDEN'],
        'Polisnummer': ['POL-001', 'POL-002', 'POL-002'],
    }
    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name='Sheet1')
    buffer.seek(0)
    return buffer.getvalue()


class TestReferenceAnalysisServiceInit:
    """Tests for service initialization."""

    def test_init_with_required_params(self, config, mock_similarity_service):
        """Test initialization with required parameters."""
        service = ReferenceAnalysisService(config, mock_similarity_service)
        assert service.config == config
        assert service.similarity_service == mock_similarity_service
        assert not service.is_loaded

    def test_init_with_hybrid_service(self, config, mock_similarity_service, mock_hybrid_similarity_service):
        """Test initialization with hybrid similarity service."""
        service = ReferenceAnalysisService(
            config,
            mock_similarity_service,
            mock_hybrid_similarity_service
        )
        assert service.hybrid_similarity_service == mock_hybrid_similarity_service

    def test_is_loaded_false_initially(self, reference_service):
        """Test that is_loaded property is False initially."""
        assert not reference_service.is_loaded


class TestLoadReferenceFile:
    """Tests for loading reference Excel files."""

    def test_load_valid_reference_file(self, reference_service, sample_excel_bytes):
        """Test loading a valid reference Excel file."""
        ref_data = reference_service.load_reference_file(sample_excel_bytes, "test_ref.xlsx")

        assert reference_service.is_loaded
        assert ref_data is not None
        assert len(ref_data.clauses) == 3  # 2 valid rows + 0 empty
        assert ref_data.source_filename == "test_ref.xlsx"

    def test_load_file_clears_caches(self, reference_service, sample_excel_bytes):
        """Test that loading file clears previous match caches."""
        # Load first time
        reference_service.load_reference_file(sample_excel_bytes, "test1.xlsx")
        cache_size_1 = len(reference_service._match_cache)

        # Manually add something to cache
        reference_service._match_cache['test_key'] = None
        assert len(reference_service._match_cache) > cache_size_1

        # Load again
        reference_service.load_reference_file(sample_excel_bytes, "test2.xlsx")
        assert len(reference_service._match_cache) == 0  # Cache cleared

    def test_load_file_deduplicates_rows(self, reference_service):
        """Test that duplicate rows are removed during loading."""
        data = {
            'Tekst': ['Same text', 'Same text', 'Different text'],
            'Frequentie': [5, 5, 3],
            'Advies': ['BEHOUDEN', 'BEHOUDEN', 'VERWIJDEREN'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        ref_data = reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")

        # Should have 2 clauses (duplicate removed)
        assert len(ref_data.clauses) == 2

    def test_load_file_skips_empty_rows(self, reference_service):
        """Test that empty rows are skipped."""
        data = {
            'Tekst': ['Valid text', 'nan', '', '   '],
            'Frequentie': [5, 1, 1, 1],
            'Advies': ['BEHOUDEN', 'SKIP', 'SKIP', 'SKIP'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        ref_data = reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")

        assert len(ref_data.clauses) == 1

    def test_load_file_missing_text_column(self, reference_service):
        """Test error handling for missing text column."""
        data = {
            'WrongColumn': ['text1'],
            'Frequentie': [5],
            'Advies': ['BEHOUDEN'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        with pytest.raises(ValueError, match="Geen 'Tekst' kolom"):
            reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")

    def test_load_file_missing_advice_column(self, reference_service):
        """Test error handling for missing advice column."""
        data = {
            'Tekst': ['text1'],
            'Frequentie': [5],
            'WrongColumn': ['BEHOUDEN'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        with pytest.raises(ValueError, match="Geen 'Advies' kolom"):
            reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")

    def test_load_file_parses_frequency(self, reference_service, sample_excel_bytes):
        """Test that frequency is parsed correctly."""
        ref_data = reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        clause = ref_data.clauses[0]
        assert clause.frequency == 5
        assert clause.advice_code == 'BEHOUDEN'

    def test_load_file_with_original_frequency(self, reference_service):
        """Test loading with original frequency column (for UNIEK clusters)."""
        data = {
            'Tekst': ['Text1', 'Text2'],
            'Frequentie': [625, 280],  # Cluster sizes
            'Orig. Frequentie': [1, 5],  # Original frequencies
            'Advies': ['BEHOUDEN', 'VERWIJDEREN'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        ref_data = reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")

        # Should use original frequency
        assert ref_data.clauses[0].frequency == 1
        assert ref_data.clauses[1].frequency == 5


class TestFindMatch:
    """Tests for finding reference matches."""

    def test_find_exact_match(self, reference_service, sample_excel_bytes):
        """Test finding exact text match."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        # Find exact match
        match = reference_service.find_match("Dekking voor schade aan het motorrijtuig is meeverzekerd")

        assert match is not None
        assert match.match_type == "exact"
        assert match.match_score == 1.0

    def test_find_match_caching(self, reference_service, sample_excel_bytes):
        """Test that find_match caches results."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        text = "Dekking voor schade aan het motorrijtuig is meeverzekerd"

        # First call
        match1 = reference_service.find_match(text)
        cache_size_1 = len(reference_service._match_cache)

        # Second call (should hit cache)
        match2 = reference_service.find_match(text)
        cache_size_2 = len(reference_service._match_cache)

        assert match1 == match2
        assert cache_size_1 == cache_size_2

    def test_find_match_no_data_loaded(self, reference_service):
        """Test find_match returns None if no data loaded."""
        match = reference_service.find_match("some text")
        assert match is None

    def test_find_fuzzy_match(self, reference_service, sample_excel_bytes):
        """Test fuzzy matching with similar but not identical text."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        # Similar but not identical
        similar_text = "Dekking schade motorrijtuig meeverzekerd"
        match = reference_service.find_match(similar_text, min_score=0.70)

        # Should find a fuzzy match
        assert match is not None
        assert match.match_type == "fuzzy"
        assert match.match_score >= 0.70

    def test_find_match_with_policy_number(self, reference_service, sample_excel_with_policy):
        """Test per-policy matching."""
        reference_service.load_reference_file(sample_excel_with_policy, "test.xlsx")

        # Exact policy match
        match = reference_service.find_match("policy a text", policy_number="POL-001")

        assert match is not None
        assert match.reference_clause.policy_number == "POL-001"

    def test_find_match_marks_matched(self, reference_service, sample_excel_bytes):
        """Test that matches mark the reference clause as matched."""
        ref_data = reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        # Initially none are marked as matched
        unmatched_before = reference_service.get_gone_texts()
        assert len(unmatched_before) == 3

        # Find a match
        reference_service.find_match("Dekking voor schade aan het motorrijtuig is meeverzekerd")

        # Now one should be marked
        unmatched_after = reference_service.get_gone_texts()
        assert len(unmatched_after) == 2

    def test_find_match_case_insensitive(self, reference_service, sample_excel_bytes):
        """Test that matching is case-insensitive."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        # Use uppercase
        text_upper = "DEKKING VOOR SCHADE AAN HET MOTORRIJTUIG IS MEEVERZEKERD"
        match = reference_service.find_match(text_upper)

        assert match is not None
        assert match.match_score == 1.0


class TestGetCombinedFrequency:
    """Tests for frequency combination logic."""

    def test_combined_frequency_no_reference(self, reference_service):
        """Test combined frequency when no reference match."""
        result = reference_service.get_combined_frequency(10, None)
        assert result == 10

    def test_combined_frequency_higher_reference(self, reference_service):
        """Test combined frequency when reference is higher."""
        ref_clause = ReferenceClause(
            text="test", simplified_text="test", frequency=20,
            advice_code="BEHOUDEN"
        )
        match = ReferenceMatch(ref_clause, "exact", 1.0)

        result = reference_service.get_combined_frequency(10, match)
        assert result == 20

    def test_combined_frequency_higher_current(self, reference_service):
        """Test combined frequency when current is higher."""
        ref_clause = ReferenceClause(
            text="test", simplified_text="test", frequency=5,
            advice_code="BEHOUDEN"
        )
        match = ReferenceMatch(ref_clause, "exact", 1.0)

        result = reference_service.get_combined_frequency(10, match)
        assert result == 10


class TestShouldStandardizeFromReference:
    """Tests for standardization threshold check."""

    def test_should_standardize_no_reference(self, reference_service):
        """Test standardization check when no reference."""
        result = reference_service.should_standardize_from_reference(None, 20)
        assert not result

    def test_should_standardize_above_threshold(self, reference_service):
        """Test standardization when reference frequency exceeds threshold."""
        ref_clause = ReferenceClause(
            text="test", simplified_text="test", frequency=25,
            advice_code="BEHOUDEN"
        )
        match = ReferenceMatch(ref_clause, "exact", 1.0)

        result = reference_service.should_standardize_from_reference(match, 20)
        assert result is True

    def test_should_standardize_below_threshold(self, reference_service):
        """Test standardization when reference frequency below threshold."""
        ref_clause = ReferenceClause(
            text="test", simplified_text="test", frequency=10,
            advice_code="BEHOUDEN"
        )
        match = ReferenceMatch(ref_clause, "exact", 1.0)

        result = reference_service.should_standardize_from_reference(match, 20)
        assert result is False


class TestGetComparisonStatus:
    """Tests for comparison status determination."""

    def test_comparison_status_new(self, reference_service):
        """Test NEW status when no reference match."""
        status = reference_service.get_comparison_status("BEHOUDEN", None)
        assert status == ComparisonStatus.NEW

    def test_comparison_status_consistent(self, reference_service):
        """Test CONSISTENT status when advice matches."""
        ref_clause = ReferenceClause(
            text="test", simplified_text="test", frequency=5,
            advice_code="BEHOUDEN"
        )
        match = ReferenceMatch(ref_clause, "exact", 1.0)

        status = reference_service.get_comparison_status("BEHOUDEN", match)
        assert status == ComparisonStatus.CONSISTENT

    def test_comparison_status_different(self, reference_service):
        """Test DIFFERENT status when advice differs."""
        ref_clause = ReferenceClause(
            text="test", simplified_text="test", frequency=5,
            advice_code="BEHOUDEN"
        )
        match = ReferenceMatch(ref_clause, "exact", 1.0)

        status = reference_service.get_comparison_status("VERWIJDEREN", match)
        assert status == ComparisonStatus.DIFFERENT


class TestGetGoneTexts:
    """Tests for retrieving unmatched reference clauses."""

    def test_get_gone_texts_no_data(self, reference_service):
        """Test get_gone_texts when no data loaded."""
        result = reference_service.get_gone_texts()
        assert result == []

    def test_get_gone_texts_no_matches(self, reference_service, sample_excel_bytes):
        """Test get_gone_texts when nothing matched."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        gone = reference_service.get_gone_texts()
        assert len(gone) == 3  # All clauses are unmatched

    def test_get_gone_texts_partial_match(self, reference_service, sample_excel_bytes):
        """Test get_gone_texts with partial matches."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        # Match one clause
        reference_service.find_match("Dekking voor schade aan het motorrijtuig is meeverzekerd")

        gone = reference_service.get_gone_texts()
        assert len(gone) == 2  # 2 clauses still unmatched


class TestGetStatistics:
    """Tests for statistics retrieval."""

    def test_get_statistics_no_data(self, reference_service):
        """Test statistics when no data loaded."""
        stats = reference_service.get_statistics()
        assert not stats.get("loaded")

    def test_get_statistics_with_data(self, reference_service, sample_excel_bytes):
        """Test statistics with loaded data."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        stats = reference_service.get_statistics()
        assert stats["loaded"] is True
        assert stats["source_file"] == "test.xlsx"
        assert stats["total"] == 3
        assert stats["matched"] == 0
        assert stats["cache_size"] == 0

    def test_get_statistics_with_matches(self, reference_service, sample_excel_bytes):
        """Test statistics with matches recorded."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        # Make a match
        reference_service.find_match("Dekking voor schade aan het motorrijtuig is meeverzekerd")

        stats = reference_service.get_statistics()
        assert stats["matched"] == 1
        assert stats["unmatched"] == 2
        assert stats["cache_size"] >= 1


class TestPrivateMethods:
    """Tests for private utility methods."""

    def test_find_column_exact_match(self, reference_service):
        """Test column finding with exact name match."""
        data = {'Tekst': [1], 'Frequentie': [1]}
        df = pd.DataFrame(data)

        col = reference_service._find_column(df, 'text')
        assert col == 'Tekst'

    def test_find_column_case_variations(self, reference_service):
        """Test column finding with case variations."""
        data = {'tekst': [1]}
        df = pd.DataFrame(data)

        col = reference_service._find_column(df, 'text')
        assert col == 'tekst'

    def test_find_column_not_found(self, reference_service):
        """Test column finding when column doesn't exist."""
        data = {'WrongColumn': [1]}
        df = pd.DataFrame(data)

        col = reference_service._find_column(df, 'text')
        assert col is None

    def test_simplify_text_basic(self, reference_service):
        """Test text simplification."""
        result = reference_service._simplify_text("  TEST TEXT  ")
        assert result == "test text"

    def test_simplify_text_empty(self, reference_service):
        """Test simplifying empty text."""
        result = reference_service._simplify_text("")
        assert result == ""

    def test_simplify_text_multiple_spaces(self, reference_service):
        """Test simplification normalizes multiple spaces."""
        result = reference_service._simplify_text("Test   multiple    spaces")
        assert result == "test multiple spaces"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_find_match_empty_text(self, reference_service, sample_excel_bytes):
        """Test find_match with empty text."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        match = reference_service.find_match("")
        # Should return None or fuzzy match depending on implementation
        assert match is None or match.match_score < 1.0

    def test_find_match_whitespace_only(self, reference_service, sample_excel_bytes):
        """Test find_match with whitespace-only text."""
        reference_service.load_reference_file(sample_excel_bytes, "test.xlsx")

        match = reference_service.find_match("   ")
        assert match is None or match.match_score < 1.0

    def test_load_file_with_special_characters(self, reference_service):
        """Test loading file with special characters."""
        data = {
            'Tekst': ['Text with éàü special chars', 'Text with "quotes"'],
            'Frequentie': [5, 3],
            'Advies': ['BEHOUDEN', 'VERWIJDEREN'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        ref_data = reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")
        assert len(ref_data.clauses) == 2
        assert "éàü" in ref_data.clauses[0].text

    def test_load_file_invalid_frequency(self, reference_service):
        """Test loading with invalid frequency values."""
        data = {
            'Tekst': ['Text1', 'Text2'],
            'Frequentie': ['invalid', 3.5],  # Invalid frequency
            'Advies': ['BEHOUDEN', 'VERWIJDEREN'],
        }
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, sheet_name='Sheet1')
        buffer.seek(0)

        # Should handle gracefully, default to 1
        ref_data = reference_service.load_reference_file(buffer.getvalue(), "test.xlsx")
        assert ref_data.clauses[0].frequency == 1
        assert ref_data.clauses[1].frequency == 3
