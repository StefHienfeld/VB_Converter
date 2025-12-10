# hienfeld/utils/text_normalization.py
"""
Text normalization utilities for consistent text comparison.
"""
import re
import unicodedata
from typing import Optional, Dict


def normalize_whitespace(text: str) -> str:
    """
    Normalize all whitespace to single spaces.
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    return " ".join(text.split())


def remove_punctuation(text: str, keep_chars: str = "") -> str:
    """
    Remove punctuation from text, optionally keeping specific characters.
    
    Args:
        text: Input text
        keep_chars: Characters to preserve
        
    Returns:
        Text without punctuation
    """
    if not text:
        return ""
    pattern = f'[^\\w\\s{re.escape(keep_chars)}]'
    return re.sub(pattern, '', text)


def normalize_unicode(text: str) -> str:
    """
    Normalize unicode characters to their canonical form.
    
    Args:
        text: Input text
        
    Returns:
        Unicode-normalized text
    """
    if not text:
        return ""
    # NFKC normalization: compatibility decomposition followed by canonical composition
    return unicodedata.normalize('NFKC', text)


def simplify_text(text: str, synonym_map: Optional[Dict[str, str]] = None) -> str:
    """
    Simplify text for comparison by normalizing case, whitespace, and punctuation.
    
    This is the main text normalization function used throughout the application.
    
    Args:
        text: Input text to simplify
        synonym_map: Optional dictionary mapping terms to their canonical form
                    (e.g., {'franchise': 'eigen risico'})
        
    Returns:
        Simplified, normalized text suitable for comparison
    """
    if not text:
        return ""
    
    # Step 1: Unicode normalization
    text = normalize_unicode(text)
    
    # Step 2: Lowercase
    text = text.lower()
    
    # Step 3: Remove punctuation (keep alphanumeric and whitespace)
    text = remove_punctuation(text)
    
    # Step 4: Normalize whitespace
    text = normalize_whitespace(text)
    
    # Step 5: Apply synonym mapping (optional)
    if synonym_map:
        for term, canonical in synonym_map.items():
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(term)}\b'
            text = re.sub(pattern, canonical, text)
    
    return text


def extract_clause_codes(text: str, pattern: str = r'\b[0-9][A-Z]{2}[0-9]\b') -> list:
    """
    Extract clause codes from text (e.g., 9NX3, 9NY3).
    
    Args:
        text: Input text to search
        pattern: Regex pattern for clause codes
        
    Returns:
        List of unique clause codes found
    """
    if not text:
        return []
    matches = re.findall(pattern, text)
    return list(set(matches))


def extract_article_references(text: str) -> list:
    """
    Extract article references from text (e.g., Art 2.14, Artikel 9.1).
    
    Args:
        text: Input text to search
        
    Returns:
        List of article references found
    """
    if not text:
        return []
    # Match patterns like "Art 2.14", "Artikel 9.1", "art. 2.8"
    pattern = r'\b[Aa]rt(?:ikel)?\.?\s*(\d+(?:\.\d+)?)\b'
    matches = re.findall(pattern, text)
    return [f"Art {m}" for m in matches]


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.
    
    Args:
        text: Input text
        max_length: Maximum length before truncation
        suffix: String to append when truncated
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length - len(suffix)] + suffix


def normalize_for_clustering(text: str) -> str:
    """
    Aggressively normalize text for clustering by replacing variable parts.
    
    This function replaces addresses, monetary amounts, dates, policy numbers,
    and other variable content with placeholders so that similar clauses
    can be clustered together even when they differ in these details.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text with placeholders for variable parts
    """
    if not text:
        return ""
    
    # Start with basic simplification
    normalized = simplify_text(text)
    
    # Replace monetary amounts (€ 50.000, EUR 100.000,00, etc.)
    normalized = re.sub(
        r'(?:€|eur|euro)\s*[\d.,]+(?:\s*(?:miljoen|duizend))?',
        '[BEDRAG]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace standalone currency amounts
    normalized = re.sub(
        r'\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:euro|€)',
        '[BEDRAG]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace percentage values
    normalized = re.sub(
        r'\b\d+(?:[.,]\d+)?\s*%',
        '[PERCENTAGE]',
        normalized
    )
    
    # Replace dates (various formats)
    # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
    normalized = re.sub(
        r'\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b',
        '[DATUM]',
        normalized
    )
    # "1 januari 2020" format
    maanden = 'januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december'
    normalized = re.sub(
        rf'\b\d{{1,2}}\s+(?:{maanden})\s+\d{{2,4}}\b',
        '[DATUM]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace postal codes (Dutch: 1234 AB)
    normalized = re.sub(
        r'\b\d{4}\s*[a-z]{2}\b',
        '[POSTCODE]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace house numbers with potential additions
    normalized = re.sub(
        r'\b\d+(?:\s*[-/]\s*\d+)?(?:\s*[a-z])?\b(?=\s+te\s|\s+[a-z]+$)',
        '[HUISNR]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace policy numbers (common patterns)
    normalized = re.sub(
        r'\b(?:dl|ren|pol|polis)\d{5,10}[a-z]?\b',
        '[POLISNR]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace phone numbers
    normalized = re.sub(
        r'\b(?:\+31|0)\s*(?:\d[\s-]*){9,10}\b',
        '[TELEFOON]',
        normalized
    )
    
    # Replace email addresses
    normalized = re.sub(
        r'\b[\w.-]+@[\w.-]+\.\w+\b',
        '[EMAIL]',
        normalized
    )
    
    # Replace specific article/item numbers in lists (nr. 1, item 42, etc.)
    normalized = re.sub(
        r'\b(?:nr|item|nummer|pos)\.?\s*\d+\b',
        '[ITEMNR]',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Replace standalone numbers that are likely reference numbers (5+ digits)
    normalized = re.sub(
        r'\b\d{5,}\b',
        '[REFNR]',
        normalized
    )
    
    # Normalize multiple consecutive placeholders
    normalized = re.sub(r'\[BEDRAG\](?:\s*\[BEDRAG\])+', '[BEDRAG]', normalized)
    normalized = re.sub(r'\[DATUM\](?:\s*\[DATUM\])+', '[DATUM]', normalized)
    
    # Final whitespace normalization
    normalized = normalize_whitespace(normalized)
    
    return normalized
