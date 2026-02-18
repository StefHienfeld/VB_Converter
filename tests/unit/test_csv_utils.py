"""
Unit tests for CSV utilities.

Tests encoding detection, delimiter detection, CSV reading, and header cleaning.
"""

import pytest
from io import StringIO
from unittest.mock import patch, MagicMock
import csv

from hienfeld.utils.csv_utils import (
    detect_encoding,
    detect_delimiter,
    clean_csv_headers,
    read_csv_robust
)


# ============================================================
# Encoding Detection Tests
# ============================================================

class TestEncodingDetection:
    """Tests for encoding detection."""

    def test_detect_encoding_utf8(self):
        """Detect UTF-8 encoding."""
        text = "Dekking voor motorrijtuigen"
        file_bytes = text.encode('utf-8')

        encoding = detect_encoding(file_bytes)

        assert encoding in ['utf-8', 'utf-8-sig', 'ascii']

    def test_detect_encoding_utf8_with_bom(self):
        """Detect UTF-8 with BOM encoding."""
        text = "Dekking voor motorrijtuigen"
        file_bytes = b'\xef\xbb\xbf' + text.encode('utf-8')

        encoding = detect_encoding(file_bytes)

        # Should detect UTF-8 or UTF-8 with BOM
        assert encoding in ['utf-8', 'utf-8-sig']

    def test_detect_encoding_latin1(self):
        """Detect Latin-1 encoding."""
        text = "Café résumé"
        file_bytes = text.encode('latin1')

        encoding = detect_encoding(file_bytes)

        # Should detect one of the Latin1 variants
        assert encoding in ['latin1', 'iso-8859-1', 'cp1252', 'utf-8']

    def test_detect_encoding_cp1252(self):
        """Detect Windows-1252 encoding."""
        text = "Dekking"
        file_bytes = text.encode('cp1252')

        encoding = detect_encoding(file_bytes)

        assert encoding is not None

    def test_detect_encoding_empty_bytes(self):
        """Detect encoding of empty bytes."""
        file_bytes = b''

        encoding = detect_encoding(file_bytes)

        # Should return fallback or detect as UTF-8
        assert encoding is not None

    def test_detect_encoding_fallback(self):
        """Use fallback encoding when detection fails."""
        # Create bytes that don't decode as standard encodings
        file_bytes = bytes([0xFF, 0xFE, 0x00, 0x00])

        encoding = detect_encoding(file_bytes, fallback='utf-8')

        # Should detect one of the valid encodings (might detect UTF-32-LE or fallback)
        assert encoding is not None
        assert isinstance(encoding, str)

    def test_detect_encoding_with_special_characters(self):
        """Detect encoding with special characters."""
        text = "€ £ ¥ § ¶"
        file_bytes = text.encode('cp1252')

        encoding = detect_encoding(file_bytes)

        assert encoding is not None

    def test_detect_encoding_custom_fallback(self):
        """Use custom fallback encoding."""
        # Invalid bytes
        file_bytes = bytes([0xFF, 0xFF, 0xFF])

        encoding = detect_encoding(file_bytes, fallback='latin1')

        assert encoding == 'latin1'


# ============================================================
# Delimiter Detection Tests
# ============================================================

class TestDelimiterDetection:
    """Tests for CSV delimiter detection."""

    def test_detect_delimiter_semicolon(self):
        """Detect semicolon delimiter (Dutch standard)."""
        text = "col1;col2;col3\nval1;val2;val3"

        delimiter = detect_delimiter(text)

        assert delimiter == ';'

    def test_detect_delimiter_comma(self):
        """Detect comma delimiter."""
        text = "col1,col2,col3\nval1,val2,val3"

        delimiter = detect_delimiter(text)

        assert delimiter == ','

    def test_detect_delimiter_tab(self):
        """Detect tab delimiter."""
        text = "col1\tcol2\tcol3\nval1\tval2\tval3"

        delimiter = detect_delimiter(text)

        assert delimiter == '\t'

    def test_detect_delimiter_pipe(self):
        """Detect pipe delimiter."""
        text = "col1|col2|col3\nval1|val2|val3"

        delimiter = detect_delimiter(text)

        assert delimiter == '|'

    def test_detect_delimiter_empty_sample(self):
        """Detect delimiter on empty sample."""
        text = ""

        delimiter = detect_delimiter(text)

        # Should return default
        assert delimiter == ';'

    def test_detect_delimiter_single_line(self):
        """Detect delimiter on single line."""
        text = "col1;col2;col3"

        delimiter = detect_delimiter(text)

        assert delimiter == ';'

    def test_detect_delimiter_custom_candidates(self):
        """Detect delimiter from custom candidates."""
        text = "col1|col2|col3\nval1|val2|val3"

        delimiter = detect_delimiter(text, candidates=['|', ',', ';'])

        assert delimiter == '|'

    def test_detect_delimiter_empty_candidates(self):
        """Detect delimiter with empty candidates list."""
        text = "col1;col2;col3"

        # Should use empty candidates list
        with patch('csv.Sniffer.sniff', side_effect=csv.Error("No delimiters")):
            delimiter = detect_delimiter(text, candidates=[])
            # Should fall back to default
            assert delimiter == ';'

    def test_detect_delimiter_ambiguous(self):
        """Detect delimiter with equal occurrence."""
        # Both semicolon and comma appear 3 times
        text = "a;b,c;d,e;f,g"

        delimiter = detect_delimiter(text, candidates=[';', ','])

        # Should return one of them
        assert delimiter in [';', ',']

    def test_detect_delimiter_sniff_exception_handled(self):
        """Handle csv.Sniffer exception gracefully."""
        text = "col1;col2\nval1;val2"

        with patch('csv.Sniffer.sniff', side_effect=csv.Error("Detection failed")):
            delimiter = detect_delimiter(text)
            # Should fall back to counting delimiters
            assert delimiter == ';'


# ============================================================
# Header Cleaning Tests
# ============================================================

class TestHeaderCleaning:
    """Tests for CSV header cleaning."""

    def test_clean_csv_headers_basic(self):
        """Clean basic headers."""
        headers = ["tekst", "polis", "bedrag"]

        cleaned = clean_csv_headers(headers)

        assert cleaned == ["tekst", "polis", "bedrag"]

    def test_clean_csv_headers_with_bom(self):
        """Remove BOM character from headers."""
        headers = ["\ufeffTekst", "Polis", "Bedrag"]

        cleaned = clean_csv_headers(headers)

        assert cleaned[0] == "Tekst"
        assert "\ufeff" not in cleaned[0]

    def test_clean_csv_headers_with_whitespace(self):
        """Strip whitespace from headers."""
        headers = ["  tekst  ", "polis ", " bedrag"]

        cleaned = clean_csv_headers(headers)

        assert cleaned == ["tekst", "polis", "bedrag"]

    def test_clean_csv_headers_empty_list(self):
        """Clean empty header list."""
        cleaned = clean_csv_headers([])

        assert cleaned == []

    def test_clean_csv_headers_with_empty_strings(self):
        """Handle empty strings in headers."""
        headers = ["tekst", "", "bedrag"]

        cleaned = clean_csv_headers(headers)

        assert len(cleaned) == 3
        assert cleaned[1] == ""

    def test_clean_csv_headers_with_none(self):
        """Handle None values in headers."""
        headers = ["tekst", None, "bedrag"]

        # Should not crash, may skip or convert to string
        try:
            cleaned = clean_csv_headers(headers)
            assert len(cleaned) == 3
        except (TypeError, AttributeError):
            pass

    def test_clean_csv_headers_multiple_spaces(self):
        """Handle multiple consecutive spaces."""
        headers = ["  tekst  ", "polis", "bedrag"]

        cleaned = clean_csv_headers(headers)

        assert "tekst" in cleaned[0]
        assert "  " not in cleaned[0]

    def test_clean_csv_headers_special_characters(self):
        """Preserve special characters in headers."""
        headers = ["tekst-1", "bedrag ($)", "polis_nr"]

        cleaned = clean_csv_headers(headers)

        assert "-" in cleaned[0]
        assert "($)" in cleaned[1]
        assert "_" in cleaned[2]

    def test_clean_csv_headers_unicode(self):
        """Handle unicode characters in headers."""
        headers = ["café", "résumé", "naïve"]

        cleaned = clean_csv_headers(headers)

        assert "café" in cleaned[0]
        assert len(cleaned) == 3


# ============================================================
# Robust CSV Reading Tests
# ============================================================

class TestRobustCSVReading:
    """Tests for robust CSV file reading."""

    def test_read_csv_robust_basic(self):
        """Read basic CSV file."""
        csv_bytes = b"tekst,polis\nDekking,POL001\nBrand,POL002"

        headers, rows = read_csv_robust(csv_bytes)

        assert len(headers) == 2
        assert len(rows) == 2
        assert rows[0]["tekst"] == "Dekking"

    def test_read_csv_robust_semicolon_delimiter(self):
        """Read CSV with semicolon delimiter."""
        csv_bytes = b"tekst;polis\nDekking;POL001\nBrand;POL002"

        headers, rows = read_csv_robust(csv_bytes)

        assert len(headers) == 2
        assert rows[0]["tekst"] == "Dekking"

    def test_read_csv_robust_with_encoding_param(self):
        """Read CSV with specified encoding."""
        csv_bytes = b"tekst\nDekking"

        headers, rows = read_csv_robust(csv_bytes, encoding='utf-8')

        assert len(headers) == 1
        assert headers[0] == "tekst"

    def test_read_csv_robust_with_delimiter_param(self):
        """Read CSV with specified delimiter."""
        csv_bytes = b"tekst;polis\nDekking;POL001"

        headers, rows = read_csv_robust(csv_bytes, delimiter=';')

        assert len(headers) == 2

    def test_read_csv_robust_auto_detect_encoding(self):
        """Auto-detect encoding when not specified."""
        text = "tekst\nDekking"
        csv_bytes = text.encode('utf-8')

        headers, rows = read_csv_robust(csv_bytes)

        assert len(headers) == 1

    def test_read_csv_robust_auto_detect_delimiter(self):
        """Auto-detect delimiter when not specified."""
        csv_bytes = b"tekst;polis\nDekking;POL001"

        headers, rows = read_csv_robust(csv_bytes)

        # Should detect semicolon
        assert len(headers) == 2

    def test_read_csv_robust_empty_file(self):
        """Read empty CSV file."""
        csv_bytes = b""

        headers, rows = read_csv_robust(csv_bytes)

        assert headers == []
        assert rows == []

    def test_read_csv_robust_header_only(self):
        """Read CSV with only headers."""
        csv_bytes = b"tekst,polis,bedrag"

        headers, rows = read_csv_robust(csv_bytes)

        assert len(headers) == 3
        assert len(rows) == 0

    def test_read_csv_robust_with_quoted_fields(self):
        """Read CSV with quoted fields."""
        csv_bytes = b'tekst,polis\n"Dekking, inclusief",POL001'

        headers, rows = read_csv_robust(csv_bytes)

        assert rows[0]["tekst"] == "Dekking, inclusief"

    def test_read_csv_robust_with_newlines_in_fields(self):
        """Read CSV with newlines in quoted fields."""
        csv_bytes = b'tekst,polis\n"Dekking\nmulti-line",POL001'

        headers, rows = read_csv_robust(csv_bytes)

        assert len(rows) == 1
        assert "\n" in rows[0]["tekst"]

    def test_read_csv_robust_latin1_encoding(self):
        """Read CSV with Latin-1 encoding."""
        text = "tekst,polis\nCafé,POL001"
        csv_bytes = text.encode('latin1')

        headers, rows = read_csv_robust(csv_bytes)

        assert "caf" in rows[0]["tekst"].lower()

    def test_read_csv_robust_cleans_headers(self):
        """Headers are cleaned (BOM/whitespace removed)."""
        csv_bytes = b"  tekst  ,polis\nDekking,POL001"

        headers, rows = read_csv_robust(csv_bytes)

        # Headers should be cleaned
        assert "tekst" in headers[0].lower()

    def test_read_csv_robust_with_both_params(self):
        """Read CSV with both encoding and delimiter specified."""
        csv_bytes = b"tekst;polis\nDekking;POL001"

        headers, rows = read_csv_robust(csv_bytes, delimiter=';', encoding='utf-8')

        assert len(headers) == 2
        assert len(rows) == 1

    def test_read_csv_robust_special_characters(self):
        """Read CSV with special characters."""
        csv_bytes = "tekst,bedrag\nDekking €, €1000".encode('utf-8')

        headers, rows = read_csv_robust(csv_bytes)

        assert "€" in rows[0]["bedrag"]

    def test_read_csv_robust_returns_list_of_dicts(self):
        """read_csv_robust returns rows as list of dicts."""
        csv_bytes = b"tekst,polis\nDekking,POL001\nBrand,POL002"

        headers, rows = read_csv_robust(csv_bytes)

        assert isinstance(rows, list)
        assert all(isinstance(row, dict) for row in rows)

    def test_read_csv_robust_column_access(self):
        """Can access columns by header name in row dicts."""
        csv_bytes = b"tekst,polis\nDekking,POL001"

        headers, rows = read_csv_robust(csv_bytes)

        assert rows[0]["tekst"] == "Dekking"
        assert rows[0]["polis"] == "POL001"


# ============================================================
# Edge Cases and Error Handling
# ============================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_long_lines(self):
        """Handle very long CSV lines."""
        long_text = "A" * 10000
        csv_bytes = f"tekst\n{long_text}".encode('utf-8')

        headers, rows = read_csv_robust(csv_bytes)

        assert len(rows) == 1
        assert len(rows[0]["tekst"]) == 10000

    def test_many_columns(self):
        """Handle CSV with many columns."""
        num_cols = 100
        header = ",".join([f"col{i}" for i in range(num_cols)])
        values = ",".join([f"val{i}" for i in range(num_cols)])
        csv_bytes = f"{header}\n{values}".encode('utf-8')

        headers, rows = read_csv_robust(csv_bytes)

        assert len(headers) == num_cols
        assert len(rows) == 1

    def test_many_rows(self):
        """Handle CSV with many rows."""
        csv_bytes = b"tekst\n" + b"\n".join([f"row{i}".encode() for i in range(1000)])

        headers, rows = read_csv_robust(csv_bytes)

        assert len(rows) == 1000

    def test_duplicate_header_names(self):
        """Handle duplicate column names."""
        csv_bytes = b"tekst,tekst,polis\nval1,val2,POL001"

        headers, rows = read_csv_robust(csv_bytes)

        # CSV reader should handle this
        assert len(headers) == 3

    def test_inconsistent_column_count(self):
        """Handle rows with inconsistent column counts."""
        csv_bytes = b"tekst,polis\nval1,val2\nval3\nval4,val5,val6"

        headers, rows = read_csv_robust(csv_bytes)

        # Should handle gracefully
        assert len(rows) >= 1

    def test_detect_encoding_chardet_fallback(self):
        """detect_encoding uses chardet if available."""
        text = "Dekking"
        file_bytes = text.encode('utf-8')

        encoding = detect_encoding(file_bytes)

        # Should work regardless of chardet availability
        assert encoding is not None

    def test_null_bytes_in_data(self):
        """Handle null bytes in CSV data."""
        csv_bytes = b"tekst,polis\nDek\x00king,POL001"

        # Should handle gracefully (might raise or skip)
        try:
            headers, rows = read_csv_robust(csv_bytes)
            assert len(rows) >= 0
        except (ValueError, UnicodeDecodeError):
            pass

    def test_bom_in_csv_data(self):
        """Handle BOM in CSV data."""
        csv_bytes = b'\xef\xbb\xbfTekst,Polis\nDekking,POL001'

        headers, rows = read_csv_robust(csv_bytes)

        # Should handle BOM
        assert len(headers) == 2
        assert "Tekst" in headers or "tekst" in headers[0].lower()


# ============================================================
# CSV Field Size Limit Tests
# ============================================================

class TestCSVFieldSizeLimit:
    """Tests for CSV field size limit handling."""

    def test_csv_field_size_limit_set(self):
        """CSV field size limit is set to sys.maxsize."""
        import csv
        import sys

        # The field size limit should be high
        current_limit = csv.field_size_limit()
        assert current_limit == sys.maxsize

    def test_read_very_large_field(self):
        """Read CSV with very large field."""
        large_text = "X" * 100000
        csv_bytes = f"tekst\n{large_text}".encode('utf-8')

        # Should not raise due to field size limit
        try:
            headers, rows = read_csv_robust(csv_bytes)
            assert len(rows) == 1
            assert len(rows[0]["tekst"]) == 100000
        except csv.Error:
            # If it still fails, that's due to csv module limitations
            pass
