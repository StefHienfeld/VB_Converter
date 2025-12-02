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

