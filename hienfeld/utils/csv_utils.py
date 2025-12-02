# hienfeld/utils/csv_utils.py
"""
CSV and file reading utilities.
"""
import csv
import sys
from typing import Optional, Tuple
from io import StringIO, BytesIO

# Increase CSV field size limit for large text fields
csv.field_size_limit(sys.maxsize)


def detect_encoding(file_bytes: bytes, fallback: str = 'utf-8') -> str:
    """
    Detect the encoding of a byte string.
    
    Args:
        file_bytes: Raw bytes to analyze
        fallback: Fallback encoding if detection fails
        
    Returns:
        Detected or fallback encoding string
    """
    # Try common encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            file_bytes.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    
    # Try chardet if available
    try:
        import chardet
        result = chardet.detect(file_bytes)
        if result and result.get('encoding'):
            return result['encoding']
    except ImportError:
        pass
    
    return fallback


def detect_delimiter(text_sample: str, candidates: list = None) -> str:
    """
    Detect the CSV delimiter from a text sample.
    
    Args:
        text_sample: Sample of CSV text (first few KB)
        candidates: List of candidate delimiters to try
        
    Returns:
        Detected delimiter character
    """
    if candidates is None:
        candidates = [';', ',', '\t', '|']
    
    try:
        # Use csv.Sniffer for intelligent detection
        dialect = csv.Sniffer().sniff(text_sample, delimiters=''.join(candidates))
        return dialect.delimiter
    except csv.Error:
        pass
    
    # Fallback: count occurrences of each candidate
    best_delimiter = ';'  # Default for Dutch CSV files
    max_count = 0
    
    for delim in candidates:
        count = text_sample.count(delim)
        if count > max_count:
            max_count = count
            best_delimiter = delim
    
    return best_delimiter


def clean_csv_headers(headers: list) -> list:
    """
    Clean CSV headers by removing BOM and whitespace.
    
    Args:
        headers: List of header strings
        
    Returns:
        Cleaned header list
    """
    if not headers:
        return []
    
    cleaned = []
    for h in headers:
        if h:
            # Remove BOM character and strip whitespace
            clean = h.strip().replace('\ufeff', '')
            cleaned.append(clean)
        else:
            cleaned.append('')
    
    return cleaned


def read_csv_robust(
    file_bytes: bytes,
    delimiter: Optional[str] = None,
    encoding: Optional[str] = None
) -> Tuple[list, list]:
    """
    Read CSV file with robust encoding and delimiter detection.
    
    Args:
        file_bytes: Raw bytes of CSV file
        delimiter: Optional forced delimiter
        encoding: Optional forced encoding
        
    Returns:
        Tuple of (headers, rows) where rows is list of dicts
    """
    # Detect encoding if not specified
    if encoding is None:
        encoding = detect_encoding(file_bytes)
    
    # Decode bytes to string
    text = file_bytes.decode(encoding, errors='ignore')
    
    # Detect delimiter if not specified
    if delimiter is None:
        sample = text[:4096]  # First 4KB for detection
        delimiter = detect_delimiter(sample)
    
    # Parse CSV
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    
    # Clean headers
    headers = clean_csv_headers(reader.fieldnames or [])
    reader.fieldnames = headers
    
    # Read all rows
    rows = []
    for row in reader:
        rows.append(row)
    
    return headers, rows

