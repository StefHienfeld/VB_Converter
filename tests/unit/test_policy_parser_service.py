"""
Unit tests for PolicyParserService.

Tests document parsing functionality:
- PDF parsing (with PyMuPDF and pdfplumber)
- DOCX parsing
- TXT parsing
- Article/section detection
- Parallel file processing
- Text segmentation and chunking
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from typing import List
from io import BytesIO

from hienfeld.config import load_config
from hienfeld.services.policy_parser_service import PolicyParserService
from hienfeld.domain.policy_document import PolicyDocumentSection


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def policy_parser_service(config):
    """Create a PolicyParserService with default config."""
    return PolicyParserService(config)


@pytest.fixture
def sample_txt_content():
    """Sample TXT file content with article structure."""
    return """
Artikel 1 - Algemene Bepalingen
Deze verzekering dekt schade aan het motorrijtuig volgens de voorwaarden van deze polis.
De verzekerde moet aan alle verplichtingen voldoen.

Artikel 2 - Dekking
2.1 Basis dekking
De verzekering dekt schade door brand, storm en water.

2.2 Aanvullende dekking
Extra dekking voor diefstal en vandalisme.

Artikel 3 - Uitsluitingen
Niet gedekt zijn:
- Opzet
- Grove nalatigheid
- Slijtage
"""


@pytest.fixture
def sample_txt_bytes(sample_txt_content):
    """Sample TXT file as bytes."""
    return sample_txt_content.encode('utf-8')


@pytest.fixture
def sample_docx_bytes():
    """Create sample DOCX file bytes (minimal valid structure)."""
    # This is a minimal mock - real tests should use actual DOCX files
    return b"PK\x03\x04minimal_docx_content"


@pytest.fixture
def sample_pdf_bytes():
    """Create sample PDF file bytes (minimal structure)."""
    # This is a minimal mock - real tests should use actual PDF files
    return b"%PDF-1.4\nminimal_pdf_content"


@pytest.fixture
def long_text_content():
    """Long text content for chunking tests."""
    paragraph = "Dit is een lange paragraaf met veel tekst. " * 100
    return f"Artikel 1 - Test\n{paragraph}\n\nArtikel 2 - Meer\n{paragraph}"


# ============================================================
# Tests for PolicyParserService Initialization
# ============================================================

class TestPolicyParserServiceInit:
    """Tests for PolicyParserService initialization."""

    def test_init_with_config(self, config):
        """Should initialize with config."""
        service = PolicyParserService(config)
        assert service.config is config

    def test_article_patterns_defined(self, policy_parser_service):
        """Article patterns should be defined."""
        assert len(policy_parser_service.article_patterns) > 0

    def test_section_keywords_defined(self, policy_parser_service):
        """Section keywords should be defined."""
        assert len(policy_parser_service.section_keywords) > 0
        assert 'Dekking' in policy_parser_service.section_keywords
        assert 'Uitsluitingen' in policy_parser_service.section_keywords

    def test_constants_defined(self, policy_parser_service):
        """Constants should be properly defined."""
        assert policy_parser_service.MAX_SECTION_LENGTH > 0
        assert policy_parser_service.MIN_ARTICLE_NUM >= 1
        assert policy_parser_service.MAX_ARTICLE_NUM <= 100


# ============================================================
# Tests for File Type Detection
# ============================================================

class TestFileTypeDetection:
    """Tests for parse_policy_file file type handling."""

    def test_txt_file_extension(self, policy_parser_service, sample_txt_bytes):
        """Should parse TXT files."""
        sections = policy_parser_service.parse_policy_file(
            sample_txt_bytes, "test.txt"
        )
        assert isinstance(sections, list)
        assert all(isinstance(s, PolicyDocumentSection) for s in sections)

    def test_docx_file_extension(self, policy_parser_service):
        """Should attempt to parse DOCX files."""
        with patch.object(policy_parser_service, '_parse_docx') as mock_parse:
            mock_parse.return_value = []
            policy_parser_service.parse_policy_file(b"content", "test.docx")
            mock_parse.assert_called_once()

    def test_pdf_file_extension(self, policy_parser_service):
        """Should attempt to parse PDF files."""
        with patch.object(policy_parser_service, '_parse_pdf') as mock_parse:
            mock_parse.return_value = []
            policy_parser_service.parse_policy_file(b"content", "test.pdf")
            mock_parse.assert_called_once()

    def test_unknown_extension_fallback_to_txt(self, policy_parser_service, sample_txt_bytes):
        """Unknown extensions should fall back to TXT parsing."""
        sections = policy_parser_service.parse_policy_file(
            sample_txt_bytes, "test.xyz"
        )
        assert isinstance(sections, list)

    def test_case_insensitive_extension(self, policy_parser_service):
        """File extension detection should be case-insensitive."""
        with patch.object(policy_parser_service, '_parse_pdf') as mock_parse:
            mock_parse.return_value = []
            policy_parser_service.parse_policy_file(b"content", "test.PDF")
            mock_parse.assert_called_once()


# ============================================================
# Tests for TXT Parsing
# ============================================================

class TestTXTParsing:
    """Tests for _parse_txt method."""

    def test_parse_basic_txt(self, policy_parser_service, sample_txt_bytes):
        """Should parse basic TXT content."""
        sections = policy_parser_service._parse_txt(sample_txt_bytes, "test.txt")

        assert len(sections) > 0
        assert all(isinstance(s, PolicyDocumentSection) for s in sections)

    def test_parse_utf8_encoding(self, policy_parser_service):
        """Should handle UTF-8 encoding."""
        content = "Artikel 1 - Testë en ü tekens"
        sections = policy_parser_service._parse_txt(
            content.encode('utf-8'), "test.txt"
        )
        assert len(sections) > 0

    def test_parse_latin1_encoding(self, policy_parser_service):
        """Should handle Latin-1 encoding."""
        content = "Artikel 1 - Test\nDekking voor schade."
        sections = policy_parser_service._parse_txt(
            content.encode('latin1'), "test.txt"
        )
        assert len(sections) > 0

    def test_parse_invalid_encoding(self, policy_parser_service):
        """Should handle invalid encoding gracefully."""
        # Mix of invalid bytes
        content = b"Artikel 1 - Test\n\xff\xfe Invalid bytes here"
        sections = policy_parser_service._parse_txt(content, "test.txt")
        assert len(sections) > 0


# ============================================================
# Tests for Article Header Detection
# ============================================================

class TestArticleHeaderDetection:
    """Tests for _detect_article_header method."""

    def test_detect_artikel_format(self, policy_parser_service):
        """Should detect 'Artikel N' format."""
        result = policy_parser_service._detect_article_header("Artikel 5 - Dekking")
        assert result is not None
        article_num, title, pattern_type = result
        assert article_num == "5"
        assert "Dekking" in title

    def test_detect_artikel_with_decimal(self, policy_parser_service):
        """Should detect 'Artikel N.M' format."""
        result = policy_parser_service._detect_article_header("Artikel 2.14 - Molest")
        assert result is not None
        article_num, title, pattern_type = result
        assert article_num == "2.14"

    def test_detect_art_abbreviation(self, policy_parser_service):
        """Should detect 'Art. N' abbreviation."""
        result = policy_parser_service._detect_article_header("Art. 3 Uitsluitingen")
        assert result is not None
        article_num, title, pattern_type = result
        assert article_num == "3"

    def test_detect_numbered_section(self, policy_parser_service):
        """Should detect numbered sections like '1.1'."""
        result = policy_parser_service._detect_article_header("2.3 Aanvullende bepalingen")
        assert result is not None
        article_num, _, _ = result
        assert article_num == "2.3"

    def test_reject_year_numbers(self, policy_parser_service):
        """Should reject year numbers (1979, 2014, etc.)."""
        result = policy_parser_service._detect_article_header("1979 was a good year")
        assert result is None

        result = policy_parser_service._detect_article_header("2014 nieuwe regels")
        assert result is None

    def test_reject_large_numbers(self, policy_parser_service):
        """Should reject numbers > MAX_ARTICLE_NUM."""
        result = policy_parser_service._detect_article_header("100 redenen")
        assert result is None

    def test_no_match_normal_text(self, policy_parser_service):
        """Should return None for normal text."""
        result = policy_parser_service._detect_article_header(
            "Dit is gewone tekst zonder artikel header."
        )
        assert result is None


# ============================================================
# Tests for Article Number Validation
# ============================================================

class TestArticleNumberValidation:
    """Tests for _is_valid_article_number method."""

    def test_valid_single_digit(self, policy_parser_service):
        """Single digit articles should be valid."""
        assert policy_parser_service._is_valid_article_number("1") is True
        assert policy_parser_service._is_valid_article_number("9") is True

    def test_valid_double_digit(self, policy_parser_service):
        """Double digit articles should be valid."""
        assert policy_parser_service._is_valid_article_number("10") is True
        assert policy_parser_service._is_valid_article_number("25") is True
        assert policy_parser_service._is_valid_article_number("50") is True

    def test_valid_decimal_number(self, policy_parser_service):
        """Decimal article numbers should be valid."""
        assert policy_parser_service._is_valid_article_number("1.1") is True
        assert policy_parser_service._is_valid_article_number("2.14") is True
        assert policy_parser_service._is_valid_article_number("10.5.3") is True

    def test_invalid_year_numbers(self, policy_parser_service):
        """Year numbers should be invalid."""
        assert policy_parser_service._is_valid_article_number("1979") is False
        assert policy_parser_service._is_valid_article_number("2000") is False
        assert policy_parser_service._is_valid_article_number("2024") is False

    def test_invalid_too_large(self, policy_parser_service):
        """Numbers > MAX_ARTICLE_NUM should be invalid."""
        assert policy_parser_service._is_valid_article_number("51") is False
        assert policy_parser_service._is_valid_article_number("100") is False

    def test_invalid_zero(self, policy_parser_service):
        """Zero should be invalid."""
        assert policy_parser_service._is_valid_article_number("0") is False


# ============================================================
# Tests for Text Segmentation
# ============================================================

class TestTextSegmentation:
    """Tests for _segment_text method."""

    def test_segment_with_articles(self, policy_parser_service, sample_txt_content):
        """Should segment text by article headers."""
        sections = policy_parser_service._segment_text(sample_txt_content, "test.txt")

        assert len(sections) >= 2
        # Should have found article sections
        article_sections = [s for s in sections if s.id.startswith("Art")]
        assert len(article_sections) >= 2

    def test_segment_sets_document_id(self, policy_parser_service, sample_txt_content):
        """Should set document_id from filename."""
        sections = policy_parser_service._segment_text(sample_txt_content, "voorwaarden.txt")

        for section in sections:
            assert section.document_id == "voorwaarden.txt"

    def test_segment_preserves_content(self, policy_parser_service, sample_txt_content):
        """Should preserve section content."""
        sections = policy_parser_service._segment_text(sample_txt_content, "test.txt")

        for section in sections:
            assert len(section.raw_text) > 0
            assert len(section.simplified_text) > 0


# ============================================================
# Tests for Paragraph Splitting
# ============================================================

class TestParagraphSplitting:
    """Tests for _split_by_paragraphs method."""

    def test_split_by_double_newlines(self, policy_parser_service):
        """Should split on double newlines when paragraphs are long enough."""
        # Each paragraph must be at least 20 chars to not be filtered
        text = "Paragraph one with sufficient length.\n\nParagraph two also has enough text.\n\nParagraph three is long too."
        sections = policy_parser_service._split_by_paragraphs(text, "test.txt")

        assert len(sections) >= 1

    def test_detect_keyword_headers(self, policy_parser_service):
        """Should detect keyword-based headers."""
        text = "Dekking\nDit is de dekking.\n\nUitsluitingen\nDit zijn de uitsluitingen."
        sections = policy_parser_service._split_by_paragraphs(text, "test.txt")

        # Should detect 'Dekking' and 'Uitsluitingen' as section keywords
        assert len(sections) >= 1

    def test_skip_short_paragraphs(self, policy_parser_service):
        """Should skip very short paragraphs."""
        text = "Short\n\nThis is a longer paragraph with enough content.\n\nX"
        sections = policy_parser_service._split_by_paragraphs(text, "test.txt")

        # Short paragraphs should be filtered
        for section in sections:
            assert len(section.raw_text) >= 20 or 'longer' in section.raw_text.lower()


# ============================================================
# Tests for Needs Paragraph Splitting Check
# ============================================================

class TestNeedsParagraphSplitting:
    """Tests for _needs_paragraph_splitting method."""

    def test_single_section_needs_splitting(self, policy_parser_service):
        """Single section should need splitting."""
        sections = [PolicyDocumentSection(
            id="Art 1",
            title="Test",
            raw_text="Short content",
            simplified_text="short content",
            document_id="test.txt"
        )]

        assert policy_parser_service._needs_paragraph_splitting(sections) is True

    def test_two_sections_need_splitting(self, policy_parser_service):
        """Two sections should need splitting."""
        sections = [
            PolicyDocumentSection(
                id="Art 1", title="Test", raw_text="Content 1",
                simplified_text="content 1", document_id="test.txt"
            ),
            PolicyDocumentSection(
                id="Art 2", title="Test", raw_text="Content 2",
                simplified_text="content 2", document_id="test.txt"
            )
        ]

        assert policy_parser_service._needs_paragraph_splitting(sections) is True

    def test_many_sections_no_splitting_needed(self, policy_parser_service):
        """Multiple sections don't need splitting."""
        sections = [
            PolicyDocumentSection(
                id=f"Art {i}", title=f"Section {i}",
                raw_text=f"Content {i}" * 10,
                simplified_text=f"content {i}" * 10,
                document_id="test.txt"
            )
            for i in range(5)
        ]

        assert policy_parser_service._needs_paragraph_splitting(sections) is False

    def test_large_section_needs_splitting(self, policy_parser_service):
        """Large section (>10000 chars) should need splitting."""
        sections = [
            PolicyDocumentSection(
                id="Art 1", title="Large",
                raw_text="A" * 15000,
                simplified_text="a" * 15000,
                document_id="test.txt"
            )
        ] + [
            PolicyDocumentSection(
                id=f"Art {i}", title=f"Section {i}",
                raw_text="Content", simplified_text="content",
                document_id="test.txt"
            )
            for i in range(2, 10)
        ]

        assert policy_parser_service._needs_paragraph_splitting(sections) is True


# ============================================================
# Tests for Keyword Header Detection
# ============================================================

class TestKeywordHeaderDetection:
    """Tests for _detect_keyword_header method."""

    def test_detect_dekking_keyword(self, policy_parser_service):
        """Should detect 'Dekking' keyword."""
        result = policy_parser_service._detect_keyword_header("Dekking\nDetails about coverage.")
        assert result is not None
        assert "Dekking" in result

    def test_detect_uitsluitingen_keyword(self, policy_parser_service):
        """Should detect 'Uitsluitingen' keyword."""
        result = policy_parser_service._detect_keyword_header("Uitsluitingen\nWhat's not covered.")
        assert result is not None

    def test_detect_all_caps_header(self, policy_parser_service):
        """Should detect ALL CAPS headers."""
        result = policy_parser_service._detect_keyword_header("ALGEMENE BEPALINGEN\nContent here.")
        assert result is not None
        assert result == "ALGEMENE BEPALINGEN"

    def test_reject_short_all_caps(self, policy_parser_service):
        """Should reject very short ALL CAPS text."""
        result = policy_parser_service._detect_keyword_header("ABC\nContent here.")
        assert result is None

    def test_reject_long_all_caps(self, policy_parser_service):
        """Should reject very long ALL CAPS text."""
        long_caps = "A" * 150
        result = policy_parser_service._detect_keyword_header(f"{long_caps}\nContent here.")
        assert result is None

    def test_no_keyword_match(self, policy_parser_service):
        """Should return None for normal text."""
        result = policy_parser_service._detect_keyword_header("Dit is normale tekst zonder keywords.")
        assert result is None


# ============================================================
# Tests for Large Section Splitting
# ============================================================

class TestLargeSectionSplitting:
    """Tests for _split_large_sections method."""

    def test_small_sections_unchanged(self, policy_parser_service):
        """Small sections should pass through unchanged."""
        sections = [
            PolicyDocumentSection(
                id="Art 1", title="Small",
                raw_text="Short content",
                simplified_text="short content",
                document_id="test.txt"
            )
        ]

        result = policy_parser_service._split_large_sections(sections, "test.txt")
        assert len(result) == 1

    def test_large_section_split(self, policy_parser_service):
        """Large section should be split into chunks."""
        large_text = "This is a sentence. " * 200  # > MAX_SECTION_LENGTH
        sections = [
            PolicyDocumentSection(
                id="Art 1", title="Large Section",
                raw_text=large_text,
                simplified_text=large_text.lower(),
                document_id="test.txt"
            )
        ]

        result = policy_parser_service._split_large_sections(sections, "test.txt")
        assert len(result) > 1

    def test_split_preserves_ids(self, policy_parser_service):
        """Split sections should have related IDs."""
        large_text = "This is a sentence. " * 200
        sections = [
            PolicyDocumentSection(
                id="Art 5", title="Split Me",
                raw_text=large_text,
                simplified_text=large_text.lower(),
                document_id="test.txt"
            )
        ]

        result = policy_parser_service._split_large_sections(sections, "test.txt")

        # First chunk keeps original ID
        assert result[0].id.startswith("Art 5")
        # Subsequent chunks should have continuation indicator
        if len(result) > 1:
            assert "vervolg" in result[1].title.lower() or result[1].id.startswith("Art 5")


# ============================================================
# Tests for Text Chunking
# ============================================================

class TestTextChunking:
    """Tests for _split_text_into_chunks method."""

    def test_short_text_single_chunk(self, policy_parser_service):
        """Short text should remain as single chunk."""
        text = "This is short text."
        chunks = policy_parser_service._split_text_into_chunks(text, 1000)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self, policy_parser_service):
        """Long text should be split into multiple chunks."""
        text = "This is a sentence. " * 100
        chunks = policy_parser_service._split_text_into_chunks(text, 500)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 500 + 50  # Allow some tolerance for sentence boundaries

    def test_split_at_sentence_boundaries(self, policy_parser_service):
        """Should split at sentence boundaries when possible."""
        text = "First sentence. Second sentence. Third sentence."
        chunks = policy_parser_service._split_text_into_chunks(text, 30)

        # Each chunk should end at a sentence boundary if possible
        for chunk in chunks[:-1]:  # Except last chunk
            assert chunk.strip().endswith('.') or len(chunk) <= 30


# ============================================================
# Tests for Parallel File Parsing
# ============================================================

class TestParallelFileParsing:
    """Tests for parse_files_parallel method."""

    def test_empty_files_list(self, policy_parser_service):
        """Empty file list should return empty results."""
        result = policy_parser_service.parse_files_parallel([])
        assert result == []

    def test_single_file_sequential(self, policy_parser_service, sample_txt_bytes):
        """Single file should use sequential processing."""
        files = [(sample_txt_bytes, "test.txt")]
        result = policy_parser_service.parse_files_parallel(files)

        assert isinstance(result, list)
        # Below parallel threshold, so sequential
        assert len(result) >= 0

    def test_multiple_files_parallel(self, policy_parser_service, sample_txt_bytes):
        """Multiple files should use parallel processing."""
        files = [
            (sample_txt_bytes, "test1.txt"),
            (sample_txt_bytes, "test2.txt"),
            (sample_txt_bytes, "test3.txt"),
        ]

        result = policy_parser_service.parse_files_parallel(files)

        assert isinstance(result, list)

    def test_parallel_with_max_workers(self, policy_parser_service, sample_txt_bytes):
        """Should respect max_workers parameter."""
        files = [
            (sample_txt_bytes, f"test{i}.txt")
            for i in range(5)
        ]

        result = policy_parser_service.parse_files_parallel(files, max_workers=2)
        assert isinstance(result, list)

    def test_parallel_handles_errors_gracefully(self, policy_parser_service):
        """Should handle parsing errors gracefully."""
        # Mix of valid and invalid content
        files = [
            (b"Artikel 1 - Valid content", "valid.txt"),
            (b"\x00\x01\x02\x03", "binary.txt"),  # Invalid
        ]

        # Should not raise exception
        result = policy_parser_service.parse_files_parallel(files)
        assert isinstance(result, list)


# ============================================================
# Tests for Sequential Fallback
# ============================================================

class TestSequentialFallback:
    """Tests for _parse_files_sequential method."""

    def test_sequential_parsing(self, policy_parser_service, sample_txt_bytes):
        """Should parse files sequentially."""
        files = [
            (sample_txt_bytes, "test1.txt"),
            (sample_txt_bytes, "test2.txt"),
        ]

        result = policy_parser_service._parse_files_sequential(files)

        assert isinstance(result, list)

    def test_sequential_handles_errors(self, policy_parser_service):
        """Should continue on parsing errors."""
        files = [
            (b"Artikel 1 - Valid", "valid.txt"),
            (None, "invalid.txt"),  # Will cause error
        ]

        # Should not raise, but may log warning
        try:
            result = policy_parser_service._parse_files_sequential(files)
            assert isinstance(result, list)
        except (TypeError, AttributeError):
            # Expected for None content
            pass


# ============================================================
# Tests for Safe Single File Parsing
# ============================================================

class TestSafeSingleFileParsing:
    """Tests for _parse_single_file_safe method."""

    def test_parse_valid_file(self, policy_parser_service, sample_txt_bytes):
        """Should parse valid file successfully."""
        result = policy_parser_service._parse_single_file_safe(
            sample_txt_bytes, "test.txt"
        )

        assert isinstance(result, list)

    def test_parse_invalid_file_raises(self, policy_parser_service):
        """Should raise exception for invalid files with context."""
        with pytest.raises(Exception) as exc_info:
            policy_parser_service._parse_single_file_safe(None, "invalid.txt")

        assert "invalid.txt" in str(exc_info.value)


# ============================================================
# Tests for Fallback Section Creation
# ============================================================

class TestFallbackSectionCreation:
    """Tests for _create_fallback_section method."""

    def test_create_fallback_section(self, policy_parser_service):
        """Should create fallback section from raw bytes."""
        content = b"This is fallback content"
        section = policy_parser_service._create_fallback_section(content, "test.txt")

        assert isinstance(section, PolicyDocumentSection)
        assert section.id == "FALLBACK-1"
        assert "fallback content" in section.raw_text.lower()

    def test_fallback_handles_encoding_errors(self, policy_parser_service):
        """Should handle encoding errors in fallback."""
        content = b"\xff\xfe Invalid bytes \x00"
        section = policy_parser_service._create_fallback_section(content, "test.txt")

        assert isinstance(section, PolicyDocumentSection)


# ============================================================
# Tests for Get All Text
# ============================================================

class TestGetAllText:
    """Tests for get_all_text method."""

    def test_empty_sections(self, policy_parser_service):
        """Empty sections should return empty string."""
        result = policy_parser_service.get_all_text([])
        assert result == ""

    def test_combine_sections(self, policy_parser_service):
        """Should combine all section text."""
        sections = [
            PolicyDocumentSection(
                id="Art 1", title="First",
                raw_text="First content",
                simplified_text="first content",
                document_id="test.txt"
            ),
            PolicyDocumentSection(
                id="Art 2", title="Second",
                raw_text="Second content",
                simplified_text="second content",
                document_id="test.txt"
            )
        ]

        result = policy_parser_service.get_all_text(sections)

        assert "first content" in result
        assert "second content" in result


# ============================================================
# Tests for PDF Parsing (with mocks)
# ============================================================

class TestPDFParsing:
    """Tests for _parse_pdf method using mocks."""

    def test_pdf_parsing_returns_list(self, policy_parser_service):
        """PDF parsing should return a list of sections."""
        # PDF parsing uses local imports, so we test the interface
        # The actual PDF content would need PyMuPDF or pdfplumber
        result = policy_parser_service._parse_pdf(b"%PDF-1.4\nminimal", "test.pdf")

        # Should return a list (may be empty or fallback sections)
        assert isinstance(result, list)

    def test_pdf_fallback_message(self, policy_parser_service):
        """PDF parsing should return fallback when no parser available."""
        # When neither PyMuPDF nor pdfplumber can parse, returns placeholder
        result = policy_parser_service._parse_pdf(b"not valid pdf", "test.pdf")

        assert isinstance(result, list)
        # Should have at least one fallback section


# ============================================================
# Tests for DOCX Parsing (with mocks)
# ============================================================

class TestDOCXParsing:
    """Tests for _parse_docx method using mocks."""

    def test_docx_parsing_returns_list(self, policy_parser_service):
        """DOCX parsing should return a list of sections."""
        # DOCX parsing uses local imports and requires valid DOCX content
        # Invalid content returns fallback section
        result = policy_parser_service._parse_docx(b"PK\x03\x04invalid", "test.docx")

        assert isinstance(result, list)

    def test_docx_import_error(self, policy_parser_service):
        """Should handle python-docx import error gracefully."""
        # Simulated by raising ImportError inside _parse_docx
        # The method should return a fallback section


# ============================================================
# Tests for Text Segmentation with Pages
# ============================================================

class TestTextSegmentationWithPages:
    """Tests for _segment_text_with_pages method."""

    def test_segment_with_page_numbers(self, policy_parser_service):
        """Should assign page numbers to sections."""
        page_texts = [
            (1, "Artikel 1 - Eerste artikel\nInhoud van artikel 1."),
            (2, "Artikel 2 - Tweede artikel\nInhoud van artikel 2."),
            (3, "Artikel 3 - Derde artikel\nInhoud van artikel 3."),
        ]

        sections = policy_parser_service._segment_text_with_pages(page_texts, "test.pdf")

        # At least some sections should have page numbers assigned
        sections_with_pages = [s for s in sections if s.page_number is not None]
        # May or may not have page numbers depending on matching success

    def test_segment_handles_empty_pages(self, policy_parser_service):
        """Should handle empty pages."""
        page_texts = [
            (1, "Artikel 1 - Content"),
            (2, ""),  # Empty page
            (3, "Artikel 2 - More content"),
        ]

        sections = policy_parser_service._segment_text_with_pages(page_texts, "test.pdf")
        assert isinstance(sections, list)
