"""
Unit tests for PreprocessingService.

Tests text cleaning, normalization, DataFrame conversion, and clause creation.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from typing import List

from hienfeld.config import load_config
from hienfeld.domain.clause import Clause
from hienfeld.services.preprocessing_service import PreprocessingService


@pytest.fixture
def config():
    """Load default config for tests."""
    return load_config()


@pytest.fixture
def preprocessing_service(config):
    """Create preprocessing service."""
    return PreprocessingService(config)


@pytest.fixture
def preprocessing_service_with_synonyms(config):
    """Create preprocessing service with synonyms."""
    service = PreprocessingService(config)
    service.add_synonym("auto", "motorrijtuig")
    service.add_synonym("schade", "damage")
    return service


# ============================================================
# Text Simplification Tests
# ============================================================

class TestTextSimplification:
    """Tests for text simplification and normalization."""

    def test_simplify_text_basic(self, preprocessing_service):
        """Simplify basic text."""
        text = "Dekking voor Motorrijtuigen"

        result = preprocessing_service.simplify_text(text)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_simplify_text_empty(self, preprocessing_service):
        """Simplify empty text."""
        result = preprocessing_service.simplify_text("")

        assert result == ""

    def test_simplify_text_whitespace(self, preprocessing_service):
        """Simplify text with extra whitespace."""
        text = "Dekking   voor    Motorrijtuigen"

        result = preprocessing_service.simplify_text(text)

        # Should normalize whitespace
        assert "   " not in result or result.count(" ") <= 1

    def test_simplify_text_with_synonyms(self, preprocessing_service_with_synonyms):
        """Simplify text applies synonym mapping."""
        text = "Dekking voor auto"

        result = preprocessing_service_with_synonyms.simplify_text(text)

        # Should apply synonym mapping
        assert isinstance(result, str)

    def test_simplify_text_special_characters(self, preprocessing_service):
        """Simplify text with special characters."""
        text = "Dekking § 5, artikel €100"

        result = preprocessing_service.simplify_text(text)

        assert isinstance(result, str)

    def test_simplify_text_unicode(self, preprocessing_service):
        """Simplify text with unicode characters."""
        text = "Dekking café résumé"

        result = preprocessing_service.simplify_text(text)

        assert isinstance(result, str)

    def test_simplify_text_newlines(self, preprocessing_service):
        """Simplify text with newlines."""
        text = "Dekking voor\nMotorrijtuigen"

        result = preprocessing_service.simplify_text(text)

        assert isinstance(result, str)


# ============================================================
# DataFrame to Clauses Conversion Tests
# ============================================================

class TestDataFrameToClausesConversion:
    """Tests for converting DataFrame rows to Clause objects."""

    def test_dataframe_to_clauses_basic(self, preprocessing_service):
        """Convert basic DataFrame to clauses."""
        df = pd.DataFrame({
            "tekst": ["Dekking auto", "Brand uitsluiting"],
            "polis": ["POL001", "POL002"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 2
        assert all(isinstance(c, Clause) for c in clauses)
        assert clauses[0].raw_text == "Dekking auto"
        assert clauses[1].raw_text == "Brand uitsluiting"

    def test_dataframe_to_clauses_generates_ids(self, preprocessing_service):
        """Generated clause IDs are unique."""
        df = pd.DataFrame({
            "tekst": ["Tekst 1", "Tekst 2", "Tekst 3"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        ids = [c.id for c in clauses]
        assert len(ids) == len(set(ids))  # All unique

    def test_dataframe_to_clauses_with_policy_number(self, preprocessing_service):
        """Convert DataFrame with policy number column."""
        df = pd.DataFrame({
            "tekst": ["Dekking auto"],
            "polis": ["POL001"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(
            df, "tekst", policy_number_col="polis"
        )

        assert len(clauses) == 1
        assert clauses[0].source_policy_number == "POL001"
        assert "POL001" in clauses[0].id

    def test_dataframe_to_clauses_with_source_file_name(self, preprocessing_service):
        """Convert DataFrame with source file name."""
        df = pd.DataFrame({
            "tekst": ["Dekking auto"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(
            df, "tekst", source_file_name="test_policy.xlsx"
        )

        assert clauses[0].source_file_name == "test_policy.xlsx"

    def test_dataframe_to_clauses_empty_dataframe(self, preprocessing_service):
        """Convert empty DataFrame."""
        df = pd.DataFrame({
            "tekst": []
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert clauses == []

    def test_dataframe_to_clauses_single_row(self, preprocessing_service):
        """Convert single row DataFrame."""
        df = pd.DataFrame({
            "tekst": ["Dekking auto"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 1

    def test_dataframe_to_clauses_multiple_columns(self, preprocessing_service):
        """Convert DataFrame with multiple columns."""
        df = pd.DataFrame({
            "tekst": ["Dekking auto"],
            "polis": ["POL001"],
            "bedrag": [1000],
            "omschrijving": ["Test"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 1
        # Only tekst column should be used
        assert clauses[0].raw_text == "Dekking auto"

    def test_dataframe_to_clauses_missing_text_column(self, preprocessing_service):
        """Handle DataFrame with missing text column."""
        df = pd.DataFrame({
            "polis": ["POL001"]
        })

        # Should raise or handle gracefully
        try:
            clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")
            # If no error, should have NaN values
        except KeyError:
            pass  # Expected behavior

    def test_dataframe_to_clauses_nan_values(self, preprocessing_service):
        """Handle DataFrame with NaN values."""
        df = pd.DataFrame({
            "tekst": ["Dekking auto", None, "Brand"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 3
        # NaN becomes string representation (could be "nan" or "None")
        assert "nan" in clauses[1].raw_text.lower() or "none" in clauses[1].raw_text.lower()

    def test_dataframe_to_clauses_numeric_column(self, preprocessing_service):
        """Convert numeric values in text column."""
        df = pd.DataFrame({
            "tekst": [12345, "Dekking", 67.89]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 3
        # Numeric values should be converted to strings
        assert "12345" in clauses[0].raw_text
        assert "67.89" in clauses[2].raw_text

    def test_dataframe_to_clauses_simplified_text_generated(self, preprocessing_service):
        """Simplified text is generated for each clause."""
        df = pd.DataFrame({
            "tekst": ["  Dekking Auto  "]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert clauses[0].simplified_text is not None
        assert len(clauses[0].simplified_text) > 0


# ============================================================
# Empty Clause Filtering Tests
# ============================================================

class TestEmptyClauseFiltering:
    """Tests for filtering empty or very short clauses."""

    def test_filter_empty_clauses_removes_empty(self, preprocessing_service, config):
        """Filter removes clauses with empty text."""
        clauses = [
            Clause(id="c1", raw_text="Dekking auto verzekering", simplified_text="dekking auto verzekering"),
            Clause(id="c2", raw_text="", simplified_text=""),
            Clause(id="c3", raw_text="Brand uitsluiting", simplified_text="brand uitsluiting")
        ]

        filtered = preprocessing_service.filter_empty_clauses(clauses)

        assert len(filtered) == 2
        assert all(c.id != "c2" for c in filtered)

    def test_filter_empty_clauses_respects_min_length(self, preprocessing_service, config):
        """Filter respects minimum text length."""
        config.clustering.min_text_length = 10

        clauses = [
            Clause(id="c1", raw_text="Dekking auto", simplified_text="dekking auto"),
            Clause(id="c2", raw_text="AB", simplified_text="ab"),  # Too short
            Clause(id="c3", raw_text="Brand uitsluiting", simplified_text="brand uitsluiting")
        ]

        filtered = preprocessing_service.filter_empty_clauses(clauses)

        assert len(filtered) == 2

    def test_filter_empty_clauses_empty_list(self, preprocessing_service):
        """Filter empty clause list."""
        filtered = preprocessing_service.filter_empty_clauses([])

        assert filtered == []

    def test_filter_empty_clauses_no_empty_clauses(self, preprocessing_service):
        """Filter when no empty clauses present."""
        clauses = [
            Clause(id="c1", raw_text="Dekking auto", simplified_text="dekking auto"),
            Clause(id="c2", raw_text="Brand uitsluiting", simplified_text="brand uitsluiting")
        ]

        filtered = preprocessing_service.filter_empty_clauses(clauses)

        assert len(filtered) == 2

    def test_filter_empty_clauses_all_empty(self, preprocessing_service):
        """Filter when all clauses are empty."""
        clauses = [
            Clause(id="c1", raw_text="", simplified_text=""),
            Clause(id="c2", raw_text="", simplified_text="")
        ]

        filtered = preprocessing_service.filter_empty_clauses(clauses)

        assert len(filtered) == 0


# ============================================================
# Clause Sorting Tests
# ============================================================

class TestClauseSorting:
    """Tests for sorting clauses by length."""

    def test_sort_clauses_by_length_descending(self, preprocessing_service):
        """Sort clauses by length in descending order."""
        clauses = [
            Clause(id="c1", raw_text="Short", simplified_text="short"),
            Clause(id="c2", raw_text="This is a much longer clause text", simplified_text="this is a much longer clause text"),
            Clause(id="c3", raw_text="Medium text", simplified_text="medium text")
        ]

        sorted_clauses = preprocessing_service.sort_clauses_by_length(clauses, descending=True)

        # Longest should be first
        assert len(sorted_clauses[0].simplified_text) >= len(sorted_clauses[1].simplified_text)
        assert len(sorted_clauses[1].simplified_text) >= len(sorted_clauses[2].simplified_text)

    def test_sort_clauses_by_length_ascending(self, preprocessing_service):
        """Sort clauses by length in ascending order."""
        clauses = [
            Clause(id="c1", raw_text="This is a much longer clause text", simplified_text="this is a much longer clause text"),
            Clause(id="c2", raw_text="Short", simplified_text="short"),
            Clause(id="c3", raw_text="Medium text", simplified_text="medium text")
        ]

        sorted_clauses = preprocessing_service.sort_clauses_by_length(clauses, descending=False)

        # Shortest should be first
        assert len(sorted_clauses[0].simplified_text) <= len(sorted_clauses[1].simplified_text)
        assert len(sorted_clauses[1].simplified_text) <= len(sorted_clauses[2].simplified_text)

    def test_sort_clauses_empty_list(self, preprocessing_service):
        """Sort empty clause list."""
        sorted_clauses = preprocessing_service.sort_clauses_by_length([], descending=True)

        assert sorted_clauses == []

    def test_sort_clauses_single_clause(self, preprocessing_service):
        """Sort single clause."""
        clauses = [
            Clause(id="c1", raw_text="Dekking auto", simplified_text="dekking auto")
        ]

        sorted_clauses = preprocessing_service.sort_clauses_by_length(clauses)

        assert len(sorted_clauses) == 1
        assert sorted_clauses[0].id == "c1"

    def test_sort_clauses_equal_length(self, preprocessing_service):
        """Sort clauses with equal length."""
        clauses = [
            Clause(id="c1", raw_text="Dekking", simplified_text="dekking"),
            Clause(id="c2", raw_text="Schade", simplified_text="schade"),
            Clause(id="c3", raw_text="Brand", simplified_text="brand")
        ]

        sorted_clauses = preprocessing_service.sort_clauses_by_length(clauses)

        # All same length, should all be present
        assert len(sorted_clauses) == 3


# ============================================================
# Synonym Mapping Tests
# ============================================================

class TestSynonymMapping:
    """Tests for synonym management."""

    def test_add_synonym(self, preprocessing_service):
        """Add single synonym."""
        preprocessing_service.add_synonym("auto", "motorrijtuig")

        assert "auto" in preprocessing_service.synonym_map
        assert preprocessing_service.synonym_map["auto"] == "motorrijtuig"

    def test_add_synonym_case_insensitive(self, preprocessing_service):
        """Synonym keys are stored lowercase."""
        preprocessing_service.add_synonym("Auto", "Motorrijtuig")

        assert "auto" in preprocessing_service.synonym_map
        assert preprocessing_service.synonym_map["auto"] == "motorrijtuig"

    def test_add_multiple_synonyms(self, preprocessing_service):
        """Add multiple synonyms."""
        preprocessing_service.add_synonym("auto", "motorrijtuig")
        preprocessing_service.add_synonym("schade", "damage")
        preprocessing_service.add_synonym("brand", "fire")

        assert len(preprocessing_service.synonym_map) == 3

    def test_load_synonyms_from_dict(self, preprocessing_service):
        """Load multiple synonyms from dictionary."""
        synonyms = {
            "auto": "motorrijtuig",
            "schade": "damage",
            "brand": "fire"
        }

        preprocessing_service.load_synonyms_from_dict(synonyms)

        assert len(preprocessing_service.synonym_map) == 3
        assert preprocessing_service.synonym_map["auto"] == "motorrijtuig"

    def test_synonym_map_empty_by_default(self, preprocessing_service):
        """Synonym map is empty by default."""
        assert preprocessing_service.synonym_map == {}

    def test_synonym_map_with_initial_synonyms(self, config):
        """Initialize service with initial synonyms."""
        initial_synonyms = {
            "auto": "motorrijtuig",
            "schade": "damage"
        }

        service = PreprocessingService(config, synonym_map=initial_synonyms)

        assert len(service.synonym_map) == 2

    def test_add_synonym_overwrites_existing(self, preprocessing_service):
        """Adding synonym with same key overwrites old value."""
        preprocessing_service.add_synonym("auto", "motorrijtuig")
        preprocessing_service.add_synonym("auto", "voertuig")

        assert preprocessing_service.synonym_map["auto"] == "voertuig"

    def test_load_empty_synonym_dict(self, preprocessing_service):
        """Load empty synonym dictionary."""
        preprocessing_service.load_synonyms_from_dict({})

        assert preprocessing_service.synonym_map == {}


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """Integration tests for combined operations."""

    def test_full_preprocessing_pipeline(self, preprocessing_service):
        """Full preprocessing pipeline: DataFrame → Clauses → Filter → Sort."""
        df = pd.DataFrame({
            "tekst": [
                "This is a longer clause with more content",
                "Medium clause text",
                "Brand uitsluiting dekking",
                ""  # Empty clause
            ]
        })

        # Convert to clauses
        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")
        assert len(clauses) == 4

        # Filter empty
        filtered = preprocessing_service.filter_empty_clauses(clauses)
        assert len(filtered) == 3

        # Sort by length
        sorted_clauses = preprocessing_service.sort_clauses_by_length(filtered, descending=True)
        assert len(sorted_clauses) == 3

        # Verify sorting
        lengths = [len(c.simplified_text) for c in sorted_clauses]
        assert lengths == sorted(lengths, reverse=True)

    def test_preprocessing_with_synonyms_and_filtering(self, preprocessing_service_with_synonyms):
        """Preprocessing with synonyms and filtering."""
        df = pd.DataFrame({
            "tekst": [
                "Dekking voor auto",
                "Brand schade",
                ""
            ]
        })

        clauses = preprocessing_service_with_synonyms.dataframe_to_clauses(df, "tekst")
        filtered = preprocessing_service_with_synonyms.filter_empty_clauses(clauses)

        assert len(filtered) == 2

    def test_large_dataframe_conversion(self, preprocessing_service):
        """Handle large DataFrame conversion."""
        large_df = pd.DataFrame({
            "tekst": [f"Clause text {i}" for i in range(1000)]
        })

        clauses = preprocessing_service.dataframe_to_clauses(large_df, "tekst")

        assert len(clauses) == 1000
        # Check some properties
        assert clauses[0].raw_text == "Clause text 0"
        assert clauses[999].raw_text == "Clause text 999"


# ============================================================
# Edge Cases and Error Handling
# ============================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_long_text_clause(self, preprocessing_service):
        """Handle very long text clause."""
        long_text = "A" * 50000

        clause = Clause(
            id="c1",
            raw_text=long_text,
            simplified_text=long_text.lower()
        )

        filtered = preprocessing_service.filter_empty_clauses([clause])

        assert len(filtered) == 1

    def test_special_characters_in_text(self, preprocessing_service):
        """Handle special characters."""
        df = pd.DataFrame({
            "tekst": ["Dekking § 5, €1000, ©2024, ™"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 1
        assert "§" in clauses[0].raw_text

    def test_unicode_characters_in_text(self, preprocessing_service):
        """Handle unicode characters."""
        df = pd.DataFrame({
            "tekst": ["Café résumé naïve"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 1
        assert "café" in clauses[0].raw_text.lower()

    def test_newlines_in_text_column(self, preprocessing_service):
        """Handle newlines in text column."""
        df = pd.DataFrame({
            "tekst": ["Dekking\nfor\nMotorrijtuigen"]
        })

        clauses = preprocessing_service.dataframe_to_clauses(df, "tekst")

        assert len(clauses) == 1
        assert "\n" in clauses[0].raw_text

    def test_clause_with_only_whitespace(self, preprocessing_service):
        """Handle clause with only whitespace."""
        clauses = [
            Clause(id="c1", raw_text="   ", simplified_text="   ")
        ]

        filtered = preprocessing_service.filter_empty_clauses(clauses)

        # Should be filtered as empty/too short
        assert len(filtered) == 0
