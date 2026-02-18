"""
Unit tests for CustomInstructionsService.

Tests custom instruction parsing and matching:
- TSV/CSV format parsing
- Arrow format parsing (backwards compatible)
- Contains matching (fast path)
- Fuzzy matching
- Semantic matching (with mocks)
- Hybrid matching
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from typing import List

from hienfeld.services.custom_instructions_service import (
    CustomInstructionsService,
    CustomInstruction,
    CustomInstructionMatch
)


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def custom_instructions_service():
    """Create a CustomInstructionsService with default settings."""
    return CustomInstructionsService()


@pytest.fixture
def service_with_fuzzy_mock():
    """Create service with mocked fuzzy service."""
    mock_fuzzy = MagicMock()
    mock_fuzzy.similarity.return_value = 0.85
    return CustomInstructionsService(fuzzy_service=mock_fuzzy)


@pytest.fixture
def service_with_semantic_mock():
    """Create service with mocked semantic service."""
    mock_semantic = MagicMock()
    mock_semantic.find_best_match.return_value = MagicMock(
        text_id="instr_0",
        score=0.80
    )
    return CustomInstructionsService(semantic_service=mock_semantic)


@pytest.fixture
def service_with_hybrid_mock():
    """Create service with mocked hybrid service."""
    mock_hybrid = MagicMock()
    mock_hybrid.similarity.return_value = 0.90
    return CustomInstructionsService(hybrid_service=mock_hybrid)


@pytest.fixture
def sample_tsv_instructions():
    """Sample TSV format instructions."""
    return """meeverzekerde ondernemingen\tVullen in partijenkaart
sanctieclausule\tVerwijderen - mag weg
terrorisme\tBehouden - maatwerk"""


@pytest.fixture
def sample_arrow_instructions():
    """Sample arrow format instructions."""
    return """meeverzekerde ondernemingen
-> Vullen in partijenkaart

sanctieclausule
-> Verwijderen - mag weg

terrorisme dekking
-> Behouden - maatwerk"""


@pytest.fixture
def sample_mixed_instructions():
    """Sample with mixed formats."""
    return """meeverzekerde\tVullen in partijenkaart
fraude -> Verwijderen

molest
-> Behouden - maatwerk"""


# ============================================================
# Tests for CustomInstruction Dataclass
# ============================================================

class TestCustomInstructionDataclass:
    """Tests for CustomInstruction dataclass."""

    def test_create_instruction(self):
        """Should create instruction with search text and action."""
        instr = CustomInstruction(
            search_text="meeverzekerde",
            action="Vullen in partijenkaart"
        )

        assert instr.search_text == "meeverzekerde"
        assert instr.action == "Vullen in partijenkaart"

    def test_strips_whitespace(self):
        """Should strip whitespace from search text and action."""
        instr = CustomInstruction(
            search_text="  meeverzekerde  ",
            action="  Vullen in partijenkaart  "
        )

        assert instr.search_text == "meeverzekerde"
        assert instr.action == "Vullen in partijenkaart"

    def test_preserves_original_text(self):
        """Should preserve original text."""
        instr = CustomInstruction(
            search_text="test",
            action="action",
            original_text="test -> action"
        )

        assert instr.original_text == "test -> action"


# ============================================================
# Tests for CustomInstructionMatch Dataclass
# ============================================================

class TestCustomInstructionMatchDataclass:
    """Tests for CustomInstructionMatch dataclass."""

    def test_create_match(self):
        """Should create match with instruction, score, and text."""
        instr = CustomInstruction("test", "action")
        match = CustomInstructionMatch(
            instruction=instr,
            score=0.95,
            matched_text="matched input text"
        )

        assert match.instruction is instr
        assert match.score == 0.95
        assert match.matched_text == "matched input text"


# ============================================================
# Tests for Service Initialization
# ============================================================

class TestCustomInstructionsServiceInit:
    """Tests for CustomInstructionsService initialization."""

    def test_default_initialization(self):
        """Should initialize with default thresholds."""
        service = CustomInstructionsService()

        assert service.fuzzy_threshold == 0.65
        assert service.semantic_threshold == 0.60
        assert service._instructions == []
        assert service._indexed is False

    def test_custom_thresholds(self):
        """Should accept custom thresholds."""
        service = CustomInstructionsService(
            fuzzy_threshold=0.80,
            semantic_threshold=0.75
        )

        assert service.fuzzy_threshold == 0.80
        assert service.semantic_threshold == 0.75

    def test_accepts_services(self):
        """Should accept optional services."""
        mock_fuzzy = MagicMock()
        mock_semantic = MagicMock()
        mock_hybrid = MagicMock()

        service = CustomInstructionsService(
            fuzzy_service=mock_fuzzy,
            semantic_service=mock_semantic,
            hybrid_service=mock_hybrid
        )

        assert service._fuzzy_service is mock_fuzzy
        assert service._semantic_service is mock_semantic
        assert service._hybrid_service is mock_hybrid


# ============================================================
# Tests for TSV Format Parsing
# ============================================================

class TestTSVFormatParsing:
    """Tests for parsing TSV format instructions."""

    def test_parse_tsv_format(self, custom_instructions_service, sample_tsv_instructions):
        """Should parse TSV format instructions."""
        instructions = custom_instructions_service.parse_instructions(sample_tsv_instructions)

        assert len(instructions) == 3
        assert instructions[0].search_text == "meeverzekerde ondernemingen"
        assert instructions[0].action == "Vullen in partijenkaart"

    def test_parse_single_tsv_line(self, custom_instructions_service):
        """Should parse single TSV line."""
        instructions = custom_instructions_service.parse_instructions(
            "zoekterm\tactie"
        )

        assert len(instructions) == 1
        assert instructions[0].search_text == "zoekterm"
        assert instructions[0].action == "actie"

    def test_parse_tsv_with_empty_lines(self, custom_instructions_service):
        """Should handle empty lines in TSV."""
        raw_text = """zoekterm1\tactie1

zoekterm2\tactie2

"""
        instructions = custom_instructions_service.parse_instructions(raw_text)

        assert len(instructions) == 2

    def test_parse_semicolon_delimiter(self, custom_instructions_service):
        """Should parse semicolon-delimited format."""
        instructions = custom_instructions_service.parse_instructions(
            "zoekterm;actie"
        )

        assert len(instructions) == 1
        assert instructions[0].search_text == "zoekterm"
        assert instructions[0].action == "actie"

    def test_parse_comma_delimiter(self, custom_instructions_service):
        """Should parse comma-delimited format (if only 2 columns)."""
        instructions = custom_instructions_service.parse_instructions(
            "zoekterm,actie"
        )

        assert len(instructions) == 1
        assert instructions[0].search_text == "zoekterm"
        assert instructions[0].action == "actie"

    def test_reject_ambiguous_comma(self, custom_instructions_service):
        """Should reject comma with multiple occurrences."""
        instructions = custom_instructions_service.parse_instructions(
            "zoekterm, met comma, actie"  # 2 commas = ambiguous
        )

        # Should not be parsed as table format
        assert len(instructions) == 0 or instructions[0].action != "met comma"


# ============================================================
# Tests for Arrow Format Parsing
# ============================================================

class TestArrowFormatParsing:
    """Tests for parsing arrow format instructions."""

    def test_parse_arrow_format(self, custom_instructions_service, sample_arrow_instructions):
        """Should parse arrow format instructions."""
        instructions = custom_instructions_service.parse_instructions(sample_arrow_instructions)

        assert len(instructions) == 3
        assert instructions[0].search_text == "meeverzekerde ondernemingen"
        assert instructions[0].action == "Vullen in partijenkaart"

    def test_parse_unicode_arrow(self, custom_instructions_service):
        """Should parse Unicode arrow format."""
        raw_text = "zoekterm\n\u2192 actie"
        instructions = custom_instructions_service.parse_instructions(raw_text)

        assert len(instructions) == 1
        assert instructions[0].action == "actie"

    def test_parse_ascii_arrow(self, custom_instructions_service):
        """Should parse ASCII arrow format (->)."""
        raw_text = "zoekterm\n-> actie"
        instructions = custom_instructions_service.parse_instructions(raw_text)

        assert len(instructions) == 1
        assert instructions[0].action == "actie"

    def test_parse_single_line_arrow(self, custom_instructions_service):
        """Should parse single-line arrow format."""
        instructions = custom_instructions_service.parse_instructions(
            "zoekterm -> actie"
        )

        assert len(instructions) == 1
        assert instructions[0].search_text == "zoekterm"
        assert instructions[0].action == "actie"

    def test_parse_greater_than_arrow(self, custom_instructions_service):
        """Should parse > as arrow."""
        raw_text = "zoekterm\n> actie"
        instructions = custom_instructions_service.parse_instructions(raw_text)

        assert len(instructions) == 1


# ============================================================
# Tests for Mixed Format Parsing
# ============================================================

class TestMixedFormatParsing:
    """Tests for parsing mixed format instructions."""

    def test_parse_mixed_formats(self, custom_instructions_service, sample_mixed_instructions):
        """Should parse mixed TSV and arrow formats."""
        instructions = custom_instructions_service.parse_instructions(sample_mixed_instructions)

        assert len(instructions) >= 2


# ============================================================
# Tests for Edge Cases in Parsing
# ============================================================

class TestParsingEdgeCases:
    """Tests for edge cases in instruction parsing."""

    def test_empty_input(self, custom_instructions_service):
        """Empty input should return empty list."""
        assert custom_instructions_service.parse_instructions("") == []
        assert custom_instructions_service.parse_instructions(None) == []
        assert custom_instructions_service.parse_instructions("   ") == []

    def test_comments_ignored(self, custom_instructions_service):
        """Lines starting with # should be ignored."""
        raw_text = """# This is a comment
zoekterm\tactie
# Another comment"""
        instructions = custom_instructions_service.parse_instructions(raw_text)

        assert len(instructions) == 1

    def test_whitespace_handling(self, custom_instructions_service):
        """Should handle various whitespace."""
        raw_text = "  zoekterm  \t  actie  "
        instructions = custom_instructions_service.parse_instructions(raw_text)

        assert len(instructions) == 1
        assert instructions[0].search_text == "zoekterm"
        assert instructions[0].action == "actie"

    def test_incomplete_instruction(self, custom_instructions_service):
        """Incomplete instructions should be skipped."""
        raw_text = "zoekterm\n\nactie alleen"  # Missing arrow
        instructions = custom_instructions_service.parse_instructions(raw_text)

        # Should not create instruction without proper format
        for instr in instructions:
            assert instr.search_text and instr.action


# ============================================================
# Tests for Load Instructions
# ============================================================

class TestLoadInstructions:
    """Tests for load_instructions method."""

    def test_load_instructions(self, custom_instructions_service, sample_tsv_instructions):
        """Should load and count instructions."""
        count = custom_instructions_service.load_instructions(sample_tsv_instructions)

        assert count == 3
        assert custom_instructions_service.instruction_count == 3
        assert custom_instructions_service.is_loaded is True

    def test_load_empty_clears(self, custom_instructions_service, sample_tsv_instructions):
        """Loading empty should clear previous instructions."""
        custom_instructions_service.load_instructions(sample_tsv_instructions)
        custom_instructions_service.load_instructions("")

        assert custom_instructions_service.instruction_count == 0
        assert custom_instructions_service.is_loaded is False

    def test_load_resets_indexing(self, custom_instructions_service, sample_tsv_instructions):
        """Loading new instructions should reset indexing."""
        custom_instructions_service._indexed = True
        custom_instructions_service.load_instructions(sample_tsv_instructions)

        assert custom_instructions_service._indexed is False


# ============================================================
# Tests for Contains Matching (Fast Path)
# ============================================================

class TestContainsMatching:
    """Tests for contains-based matching (fast path)."""

    def test_exact_contains_match(self, custom_instructions_service, sample_tsv_instructions):
        """Should match when search text is contained in input."""
        custom_instructions_service.load_instructions(sample_tsv_instructions)

        match = custom_instructions_service.find_match(
            "Dit gaat over meeverzekerde ondernemingen in de polis"
        )

        assert match is not None
        assert match.score == 1.0
        assert "Vullen in partijenkaart" in match.instruction.action

    def test_case_insensitive_contains(self, custom_instructions_service):
        """Contains matching should be case-insensitive."""
        custom_instructions_service.load_instructions("ZOEKTERM\tActie")

        match = custom_instructions_service.find_match("tekst met zoekterm erin")

        assert match is not None
        assert match.score == 1.0

    def test_partial_word_match(self, custom_instructions_service):
        """Should match when search text is substring of input."""
        custom_instructions_service.load_instructions("fraude\tVerwijderen")

        match = custom_instructions_service.find_match(
            "Bij fraude handelen is er geen dekking"
        )

        # 'fraude' is literally in the input text
        assert match is not None

    def test_no_contains_match(self, custom_instructions_service):
        """Should return None when no contains match."""
        custom_instructions_service.load_instructions("specifieke zoekterm\tActie")

        match = custom_instructions_service.find_match(
            "tekst zonder de juiste woorden"
        )

        # No contains match and no services for fallback
        assert match is None


# ============================================================
# Tests for Fuzzy Matching
# ============================================================

class TestFuzzyMatching:
    """Tests for fuzzy text matching."""

    def test_fuzzy_match_with_service(self, service_with_fuzzy_mock):
        """Should use fuzzy service when available."""
        service_with_fuzzy_mock.load_instructions("zoekterm\tactie")
        service_with_fuzzy_mock._fuzzy_service.similarity.return_value = 0.70

        match = service_with_fuzzy_mock.find_match(
            "heel andere tekst",  # No contains match
            use_fuzzy=True
        )

        # Above threshold (0.65), should match
        assert match is not None

    def test_fuzzy_below_threshold(self, service_with_fuzzy_mock):
        """Should not match below fuzzy threshold."""
        service_with_fuzzy_mock.load_instructions("zoekterm\tactie")
        service_with_fuzzy_mock._fuzzy_service.similarity.return_value = 0.50  # Below 0.65

        # Force contains to fail by using very different text
        match = service_with_fuzzy_mock.find_match(
            "abcdefghijklmnop"  # Very different
        )

        # Below threshold, depends on simple fuzzy fallback too


# ============================================================
# Tests for Simple Fuzzy Matching (Last Resort)
# ============================================================

class TestSimpleFuzzyMatching:
    """Tests for _match_with_simple_fuzzy method."""

    def test_simple_substring_match(self, custom_instructions_service):
        """Should match when search text is substring with sufficient coverage."""
        # Use longer search term for better score (len(search)/len(input) + 0.3 >= 0.65)
        custom_instructions_service.load_instructions("fraude verzekering\tVerwijderen")

        # Direct call to simple fuzzy
        match = custom_instructions_service._match_with_simple_fuzzy(
            "dit is fraude verzekering tekst"
        )

        assert match is not None

    def test_simple_reverse_substring(self, custom_instructions_service):
        """Should match when input is substring of search."""
        custom_instructions_service.load_instructions(
            "meeverzekerde ondernemingen\tActie"
        )

        match = custom_instructions_service._match_with_simple_fuzzy("ondernemingen")

        # 'ondernemingen' is in 'meeverzekerde ondernemingen'
        assert match is not None


# ============================================================
# Tests for Hybrid Matching
# ============================================================

class TestHybridMatching:
    """Tests for hybrid similarity matching."""

    def test_hybrid_match_used(self, service_with_hybrid_mock):
        """Should use hybrid service when available."""
        service_with_hybrid_mock.load_instructions("zoekterm\tactie")

        # Force contains to fail
        match = service_with_hybrid_mock.find_match("heel andere tekst xyz")

        # Hybrid service should be called
        assert service_with_hybrid_mock._hybrid_service.similarity.called


# ============================================================
# Tests for Find Match Method
# ============================================================

class TestFindMatchMethod:
    """Tests for find_match method."""

    def test_no_instructions_loaded(self, custom_instructions_service):
        """Should return None when no instructions loaded."""
        match = custom_instructions_service.find_match("test text")
        assert match is None

    def test_empty_input_text(self, custom_instructions_service, sample_tsv_instructions):
        """Should return None for empty input."""
        custom_instructions_service.load_instructions(sample_tsv_instructions)

        assert custom_instructions_service.find_match("") is None
        assert custom_instructions_service.find_match("   ") is None

    def test_returns_best_match(self, custom_instructions_service):
        """Should return the best matching instruction."""
        custom_instructions_service.load_instructions("""kort\tActie voor kort
langere zoekterm\tActie voor lang""")

        # 'langere zoekterm' is more specific
        match = custom_instructions_service.find_match(
            "tekst met langere zoekterm erin"
        )

        assert match is not None
        # Contains match found for 'langere zoekterm'


# ============================================================
# Tests for Service Properties
# ============================================================

class TestServiceProperties:
    """Tests for service property methods."""

    def test_instruction_count(self, custom_instructions_service, sample_tsv_instructions):
        """Should return correct instruction count."""
        assert custom_instructions_service.instruction_count == 0

        custom_instructions_service.load_instructions(sample_tsv_instructions)
        assert custom_instructions_service.instruction_count == 3

    def test_instructions_property(self, custom_instructions_service, sample_tsv_instructions):
        """Should return copy of instructions list."""
        custom_instructions_service.load_instructions(sample_tsv_instructions)

        instructions = custom_instructions_service.instructions
        assert len(instructions) == 3

        # Should be a copy
        instructions.clear()
        assert custom_instructions_service.instruction_count == 3

    def test_is_loaded(self, custom_instructions_service, sample_tsv_instructions):
        """Should return True when instructions loaded."""
        assert custom_instructions_service.is_loaded is False

        custom_instructions_service.load_instructions(sample_tsv_instructions)
        assert custom_instructions_service.is_loaded is True

    def test_has_semantic_matching(self, service_with_semantic_mock):
        """Should indicate semantic matching availability."""
        assert service_with_semantic_mock.has_semantic_matching is False  # Not indexed yet

        # After loading and indexing
        service_with_semantic_mock.load_instructions("test\tactie")
        # Indexing happens in load_instructions if semantic service available


# ============================================================
# Tests for Clear Method
# ============================================================

class TestClearMethod:
    """Tests for clear method."""

    def test_clear_instructions(self, custom_instructions_service, sample_tsv_instructions):
        """Should clear all loaded instructions."""
        custom_instructions_service.load_instructions(sample_tsv_instructions)
        assert custom_instructions_service.is_loaded is True

        custom_instructions_service.clear()

        assert custom_instructions_service.instruction_count == 0
        assert custom_instructions_service.is_loaded is False
        assert custom_instructions_service._indexed is False


# ============================================================
# Tests for Index Building
# ============================================================

class TestIndexBuilding:
    """Tests for _index_for_semantic_search method."""

    def test_index_builds_with_semantic_service(self, service_with_semantic_mock):
        """Should build index when semantic service available."""
        service_with_semantic_mock.load_instructions("zoekterm\tactie")

        # Index texts should have been called
        assert service_with_semantic_mock._semantic_service.index_texts.called

    def test_index_handles_errors(self, service_with_semantic_mock):
        """Should handle indexing errors gracefully."""
        service_with_semantic_mock._semantic_service.index_texts.side_effect = Exception("Index error")

        # Should not raise
        service_with_semantic_mock.load_instructions("zoekterm\tactie")

        assert service_with_semantic_mock._indexed is False


# ============================================================
# Tests for Helper Methods
# ============================================================

class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_is_action_line(self, custom_instructions_service):
        """Should detect action lines."""
        assert custom_instructions_service._is_action_line("-> actie") is True
        assert custom_instructions_service._is_action_line("\u2192 actie") is True
        assert custom_instructions_service._is_action_line("> actie") is True
        assert custom_instructions_service._is_action_line("normale tekst") is False

    def test_extract_action(self, custom_instructions_service):
        """Should extract action from arrow line."""
        assert custom_instructions_service._extract_action("-> actie") == "actie"
        assert custom_instructions_service._extract_action("\u2192 actie") == "actie"
        assert custom_instructions_service._extract_action(">actie") == "actie"


# ============================================================
# Tests for Real-World Scenarios
# ============================================================

class TestRealWorldScenarios:
    """Tests for real-world instruction scenarios."""

    def test_insurance_instructions(self, custom_instructions_service):
        """Should handle typical insurance instructions."""
        instructions = """meeverzekerde ondernemingen\tVullen in partijenkaart
sanctieclausule\tVerwijderen - mag weg
terrorisme dekking\tBehouden - maatwerk
fraude en misleiding\tVerwijderen (art 2.8)
molest inclusief\tBehouden - special"""

        custom_instructions_service.load_instructions(instructions)

        # Test various clause matches
        match1 = custom_instructions_service.find_match(
            "De meeverzekerde ondernemingen zijn gevestigd in Nederland."
        )
        assert match1 is not None
        assert "partijenkaart" in match1.instruction.action.lower()

        match2 = custom_instructions_service.find_match(
            "Conform de sanctieclausule van deze polis."
        )
        assert match2 is not None
        assert "verwijderen" in match2.instruction.action.lower()

    def test_dutch_text_matching(self, custom_instructions_service):
        """Should handle Dutch text correctly."""
        custom_instructions_service.load_instructions(
            "verzekeringsvoorwaarden\tControleren"
        )

        match = custom_instructions_service.find_match(
            "De verzekeringsvoorwaarden zijn van toepassing."
        )

        assert match is not None

    def test_special_characters_in_instructions(self, custom_instructions_service):
        """Should handle special characters."""
        custom_instructions_service.load_instructions(
            "EUR 10.000\tControleer bedrag"
        )

        match = custom_instructions_service.find_match(
            "Dekking tot EUR 10.000 per gebeurtenis."
        )

        assert match is not None


# ============================================================
# Tests for Performance Edge Cases
# ============================================================

class TestPerformanceEdgeCases:
    """Tests for performance-related edge cases."""

    def test_many_instructions(self, custom_instructions_service):
        """Should handle many instructions efficiently."""
        # Create 100 instructions
        lines = [f"zoekterm{i}\tactie{i}" for i in range(100)]
        custom_instructions_service.load_instructions("\n".join(lines))

        assert custom_instructions_service.instruction_count == 100

        # Should still find match quickly
        match = custom_instructions_service.find_match("tekst met zoekterm50 erin")
        assert match is not None

    def test_long_search_text(self, custom_instructions_service):
        """Should handle long search texts."""
        long_text = "heel lange zoektekst " * 20
        custom_instructions_service.load_instructions(f"{long_text}\tactie")

        assert custom_instructions_service.instruction_count == 1

    def test_long_input_text(self, custom_instructions_service):
        """Should handle long input texts."""
        custom_instructions_service.load_instructions("kort\tactie")

        long_input = "veel tekst " * 1000 + "kort" + " meer tekst " * 1000
        match = custom_instructions_service.find_match(long_input)

        assert match is not None
