# hienfeld/services/clause_library_service.py
"""
Service for managing and searching the standard clause library.

The clause library contains pre-approved standard clauses that can be used
to replace similar free text clauses, enabling policy standardization.
"""
import os
import re
from io import BytesIO
from typing import List, Optional, Tuple

import pandas as pd

from ..config import AppConfig
from ..domain.standard_clause import StandardClause, ClauseLibraryMatch
from ..utils.text_normalization import simplify_text
from ..services.similarity_service import SimilarityService, RapidFuzzSimilarityService
from ..logging_config import get_logger

logger = get_logger('clause_library_service')


class ClauseLibraryService:
    """
    Manages the standard clause library for sanering (standardization).
    
    Responsibilities:
    - Load clause library from CSV/Excel or multiple DOCX/PDF/DOC files
    - Index clauses for fast similarity search
    - Find matching standard clauses for free text
    """
    
    # Similarity thresholds for matching
    EXACT_MATCH_THRESHOLD = 0.95      # Almost identical -> REPLACE
    HIGH_SIMILARITY_THRESHOLD = 0.85   # Very similar -> REVIEW
    MEDIUM_SIMILARITY_THRESHOLD = 0.75 # Similar -> POSSIBLE MATCH
    
    def __init__(
        self, 
        config: AppConfig,
        similarity_service: Optional[SimilarityService] = None
    ):
        """
        Initialize the clause library service.
        
        Args:
            config: Application configuration
            similarity_service: Service for computing text similarity
        """
        self.config = config
        
        # Use provided similarity service or create default
        if similarity_service is None:
            self.similarity_service = RapidFuzzSimilarityService(
                threshold=self.HIGH_SIMILARITY_THRESHOLD
            )
        else:
            self.similarity_service = similarity_service
        
        # Clause storage
        self._clauses: List[StandardClause] = []
        self._is_loaded = False
        
        # Lazy load win32com application
        self._word_app = None
    
    def load_from_files(self, files: List[Tuple[bytes, str]]) -> int:
        """
        Load clause library from multiple files (batch processing).
        
        Supports:
        - CSV/Excel (treated as bulk imports)
        - PDF/DOCX/DOC (treated as individual clauses or multi-clause docs)
        
        Args:
            files: List of (file_bytes, filename) tuples
            
        Returns:
            Total number of clauses loaded
        """
        logger.info(f"Batch loading {len(files)} files into clause library")
        
        # Initialize Word App if needed (only on Windows and if .doc files present)
        has_doc_files = any(f[1].lower().endswith('.doc') for f in files)
        if has_doc_files:
            self._init_word_app()
        
        count_before = len(self._clauses)
        
        for file_bytes, filename in files:
            try:
                self.load_from_file(file_bytes, filename)
            except Exception as e:
                logger.warning(f"Failed to load clause file {filename}: {e}")
                continue
                
        # Clean up Word App
        self._quit_word_app()
        
        total_loaded = len(self._clauses) - count_before
        self._is_loaded = len(self._clauses) > 0
        logger.info(f"Batch load complete. Added {total_loaded} clauses. Total: {len(self._clauses)}")
        
        return total_loaded

    def load_from_file(self, file_bytes: bytes, filename: str) -> int:
        """
        Load clause library from CSV, Excel, PDF, DOC, or DOCX file.
        
        For CSV/Excel:
        - Expected columns (case-insensitive): Code, Tekst/Text, Categorie/Category (optional)
        
        For PDF/DOCX/DOC:
        - Tries to extract clause code/title from the file content (first line).
        - Falls back to using the filename as the clause code.
        
        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename (for format detection)
            
        Returns:
            Number of clauses loaded from this file
            
        Raises:
            ValueError: If file format is not supported
        """
        # Don't log every single file in batch mode to avoid spam, but keep for single calls
        # logger.debug(f"Loading clause file: {filename}")
        
        filename_lower = filename.lower()
        new_clauses = []
        
        # Load data based on file type
        if filename_lower.endswith('.csv'):
            file_obj = BytesIO(file_bytes)
            df = self._load_csv(file_obj, file_bytes)
            new_clauses = self._parse_dataframe(df)
        elif filename_lower.endswith(('.xlsx', '.xls')):
            file_obj = BytesIO(file_bytes)
            df = pd.read_excel(file_obj)
            new_clauses = self._parse_dataframe(df)
        elif filename_lower.endswith('.pdf'):
            text = self._extract_text_pdf(file_bytes)
            new_clauses = self._parse_single_clause_file(text, filename)
        elif filename_lower.endswith('.docx'):
            text = self._extract_text_docx(file_bytes)
            new_clauses = self._parse_single_clause_file(text, filename)
        elif filename_lower.endswith('.doc'):
            text = self._extract_text_doc_legacy(file_bytes, filename)
            new_clauses = self._parse_single_clause_file(text, filename)
        else:
            logger.warning(f"Unsupported file format: {filename}")
            return 0
        
        self._clauses.extend(new_clauses)
        
        # Only set is_loaded to True if we are not in a batch (handled by caller) or if this is a single call
        if not self._is_loaded and new_clauses:
            self._is_loaded = True
            
        return len(new_clauses)

    def _parse_single_clause_file(self, text: str, filename: str) -> List[StandardClause]:
        """
        Parse a single file content as a clause.
        
        Strategy:
        1. Clean up text.
        2. Detect Clause Code/Title from the first line of content.
        3. If ambiguous, fallback to Filename (minus extension).
        
        Returns:
            List with a single StandardClause object (or multiple if patterns found? 
            For now, assume 1 file = 1 clause unless explicit patterns found).
        """
        if not text or not text.strip():
            return []
            
        text = self._clean_text(text)
        
        # Attempt to find code in text (legacy support for multi-clause files)
        # If the file contains explicit codes like "9NX3 ... VB12 ...", parse it as multi-clause
        try:
            return self._extract_clauses_from_text(text, filename)
        except ValueError:
            # No explicit multiple codes found -> Treat entire file as ONE clause
            pass
            
        # Strategy: File = 1 Clause
        # Determine Code/Title
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return []
            
        first_line = lines[0]
        filename_base = os.path.splitext(filename)[0]
        
        # Heuristic: If first line is short (< 100 chars) and looks like a header, use it.
        # Otherwise use filename.
        code = filename_base
        
        if len(first_line) < 100:
            # Valid header candidate
            code = first_line
            # Remove the header from the text body to avoid duplication? 
            # User requirement says: "If match, that is the clause number. If not, text matches."
            # Actually, usually the title is part of the text. Let's keep it in 'text' but use it as 'code'.
        
        # Category detection
        category = self._detect_category(code, text)
        
        clause = StandardClause(
            code=code,
            text=text,
            simplified_text=simplify_text(text),
            category=category,
            description=None
        )
        
        return [clause] if clause.is_valid else []

    def _clean_text(self, text: str) -> str:
        """Remove unprintable characters."""
        if not text:
            return ""
        # Remove control characters except newline and tab
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text).strip()

    def _init_word_app(self):
        """Initialize Word Application for legacy .doc parsing."""
        if os.name != 'nt':
            return
        try:
            import win32com.client as win32
            # pythoncom.CoInitialize() might be needed in threads
            import pythoncom
            pythoncom.CoInitialize()
            
            self._word_app = win32.Dispatch("Word.Application")
            self._word_app.Visible = False
            self._word_app.DisplayAlerts = False
        except Exception as e:
            logger.warning(f"Could not initialize Word for .doc parsing: {e}")

    def _quit_word_app(self):
        """Quit Word Application."""
        if self._word_app:
            try:
                self._word_app.Quit()
            except:
                pass
            self._word_app = None

    def _extract_text_doc_legacy(self, file_bytes: bytes, filename: str) -> str:
        """Extract text from .doc using win32com (Windows only)."""
        if not self._word_app:
            return ""
            
        import tempfile
        import os
        
        # Save bytes to temp file because Word needs a path
        fd, path = tempfile.mkstemp(suffix='.doc')
        try:
            with os.fdopen(fd, 'wb') as tmp:
                tmp.write(file_bytes)
            
            doc = self._word_app.Documents.Open(path, ReadOnly=True, Visible=False)
            text = doc.Range().Text
            doc.Close(False)
            return text
        except Exception as e:
            logger.error(f"Error parsing .doc {filename}: {e}")
            return ""
        finally:
            # Cleanup temp file
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

    def _extract_text_docx(self, file_bytes: bytes) -> str:
        """Extract text from .docx using python-docx."""
        try:
            from docx import Document
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            logger.error(f"Error parsing .docx: {e}")
            return ""

    def _extract_text_pdf(self, file_bytes: bytes) -> str:
        """Extract text from .pdf using PyMuPDF."""
        text = ""
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
        return text

    def _parse_dataframe(self, df: pd.DataFrame) -> List[StandardClause]:
        """
        Parse a DataFrame into StandardClause objects.
        
        Args:
            df: DataFrame with clause data
            
        Returns:
            List of StandardClause objects
        """
        # Normalize column names
        df.columns = [col.strip().lower() for col in df.columns]
        
        # Find required columns
        code_col = self._find_column(df, ['code', 'clausulecode', 'clause_code'])
        text_col = self._find_column(df, ['tekst', 'text', 'clausule', 'clause', 'inhoud', 'content'])
        
        if code_col is None:
            raise ValueError("Missing required column: 'Code'. Please add a column with clause codes.")
        if text_col is None:
            raise ValueError("Missing required column: 'Tekst'. Please add a column with clause text.")
        
        # Find optional columns
        category_col = self._find_column(df, ['categorie', 'category', 'type'])
        description_col = self._find_column(df, ['beschrijving', 'description', 'omschrijving'])
        
        # Convert to StandardClause objects
        clauses = []
        for _, row in df.iterrows():
            code = str(row[code_col]).strip()
            text = str(row[text_col]).strip()
            
            # Skip empty rows
            if not code or not text or code == 'nan' or text == 'nan':
                continue
            
            category = str(row[category_col]).strip() if category_col and pd.notna(row.get(category_col)) else "Algemeen"
            description = str(row[description_col]).strip() if description_col and pd.notna(row.get(description_col)) else None
            
            if category == 'nan':
                category = "Algemeen"
            if description == 'nan':
                description = None
            
            clause = StandardClause(
                code=code,
                text=text,
                simplified_text=simplify_text(text),
                category=category,
                description=description
            )
            
            if clause.is_valid:
                clauses.append(clause)
        
        return clauses
    
    def _load_csv(self, file_obj: BytesIO, file_bytes: bytes) -> pd.DataFrame:
        """Load CSV with encoding and delimiter detection."""
        # Try different encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        delimiters = [';', ',', '\t']
        
        for encoding in encodings:
            for delimiter in delimiters:
                try:
                    file_obj.seek(0)
                    df = pd.read_csv(file_obj, delimiter=delimiter, encoding=encoding)
                    if len(df.columns) > 1:  # Success if we got multiple columns
                        return df
                except Exception:
                    continue
        
        # Fallback
        file_obj.seek(0)
        return pd.read_csv(file_obj)
    
    def _find_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """Find a column matching any of the candidate names."""
        for col in df.columns:
            if col in candidates:
                return col
        return None
    
    # Re-implementing _extract_clauses_from_text for legacy multi-clause support
    def _extract_clauses_from_text(self, text: str, source_filename: str) -> List[StandardClause]:
        """
        Extract clauses from unstructured text by finding clause codes.
        
        Pattern: Looks for codes like "9NX3", "VB12" (format: \d[A-Z]{2}\d)
        Extracts text following each code until next code or section break.
        """
        # Clause code pattern: digit + 2 uppercase letters + digit (e.g., 9NX3, VB12)
        clause_code_pattern = r'\b(\d[A-Z]{2}\d)\b'
        
        # Find all clause codes with their positions
        matches = list(re.finditer(clause_code_pattern, text, re.IGNORECASE))
        
        if not matches:
            raise ValueError(
                f"Geen clausulecodes gevonden in {source_filename}. "
                f"Verwacht patroon: cijfer + 2 letters + cijfer (bijv. 9NX3, VB12)"
            )
        
        clauses = []
        current_category = "Algemeen"
        
        for i, match in enumerate(matches):
            code = match.group(1).upper()
            
            # Find start position (after the code)
            start_pos = match.end()
            
            # Find end position (next code or end of text)
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(text)
            
            # Extract clause text
            clause_text = text[start_pos:end_pos].strip()
            
            # Clean up: remove leading/trailing whitespace, newlines, punctuation
            clause_text = re.sub(r'^[:\-\.\s]+', '', clause_text)  # Remove leading punctuation
            clause_text = re.sub(r'\s+', ' ', clause_text)  # Normalize whitespace
            clause_text = clause_text.strip()
            
            # Skip if text is too short or empty
            if len(clause_text) < 10:
                logger.warning(f"Clausule {code} heeft te weinig tekst, overgeslagen")
                continue
            
            # Try to detect category from nearby headers (look for common patterns)
            # Check if there's a header before this clause
            before_text = text[max(0, match.start() - 200):match.start()]
            category = self._detect_category(before_text, clause_text)
            
            clause = StandardClause(
                code=code,
                text=clause_text,
                simplified_text=simplify_text(clause_text),
                category=category,
                description=None
            )
            
            if clause.is_valid:
                clauses.append(clause)
        
        logger.info(f"Geëxtraheerd {len(clauses)} clausules uit {source_filename}")
        
        return clauses
    
    def _detect_category(self, before_text: str, clause_text: str) -> str:
        """
        Try to detect category from context or clause content.
        """
        # Common category keywords
        category_keywords = {
            'terrorisme': 'Terrorisme',
            'brand': 'Brand',
            'diefstal': 'Diefstal',
            'inbraak': 'Diefstal',
            'molest': 'Molest',
            'eigen risico': 'Eigen Risico',
            'uitsluiting': 'Uitsluitingen',
            'dekking': 'Dekking',
            'premie': 'Premie',
            'buitenland': 'Buitenland',
            'sanctie': 'Sancties',
            'fraude': 'Fraude'
        }
        
        # Check before text for headers
        before_lower = before_text.lower()
        for keyword, category in category_keywords.items():
            if keyword in before_lower:
                return category
        
        # Check clause text itself
        clause_lower = clause_text.lower()
        for keyword, category in category_keywords.items():
            if keyword in clause_lower:
                return category
        
        return "Algemeen"
    
    def find_match(self, text: str) -> Optional[ClauseLibraryMatch]:
        """
        Find the best matching standard clause for the given text.
        
        Args:
            text: Free text to match against the library
            
        Returns:
            ClauseLibraryMatch if a match is found above medium threshold, None otherwise
        """
        if not self._clauses or not text:
            return None
        
        simplified = simplify_text(text)
        if len(simplified) < 10:
            return None
        
        best_score = 0.0
        best_clause = None
        
        for clause in self._clauses:
            score = self.similarity_service.similarity(simplified, clause.simplified_text)
            
            if score > best_score:
                best_score = score
                best_clause = clause
        
        # Only return matches above medium threshold
        if best_clause and best_score >= self.MEDIUM_SIMILARITY_THRESHOLD:
            return ClauseLibraryMatch.from_score(best_clause, best_score)
        
        return None
    
    def find_matches(
        self, 
        text: str, 
        top_k: int = 3, 
        min_score: float = 0.75
    ) -> List[ClauseLibraryMatch]:
        """
        Find multiple matching standard clauses for the given text.
        
        Args:
            text: Free text to match
            top_k: Maximum number of matches to return
            min_score: Minimum similarity score
            
        Returns:
            List of ClauseLibraryMatch objects, sorted by score descending
        """
        if not self._clauses or not text:
            return []
        
        simplified = simplify_text(text)
        if len(simplified) < 10:
            return []
        
        # Score all clauses
        scored = []
        for clause in self._clauses:
            score = self.similarity_service.similarity(simplified, clause.simplified_text)
            if score >= min_score:
                scored.append((clause, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Convert to matches
        return [
            ClauseLibraryMatch.from_score(clause, score)
            for clause, score in scored[:top_k]
        ]
    
    def get_all_clauses(self) -> List[StandardClause]:
        """Get all loaded standard clauses."""
        return self._clauses.copy()
    
    def get_clause_by_code(self, code: str) -> Optional[StandardClause]:
        """
        Get a specific clause by its code.
        
        Args:
            code: Clause code to find
            
        Returns:
            StandardClause if found, None otherwise
        """
        code_upper = code.upper().strip()
        for clause in self._clauses:
            if clause.code.upper() == code_upper:
                return clause
        return None
    
    def get_categories(self) -> List[str]:
        """Get list of unique categories in the library."""
        categories = set(clause.category for clause in self._clauses)
        return sorted(categories)
    
    def get_statistics(self) -> dict:
        """Get statistics about the loaded clause library."""
        if not self._clauses:
            return {
                'total_clauses': 0,
                'categories': [],
                'is_loaded': False
            }
        
        categories = {}
        for clause in self._clauses:
            cat = clause.category
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            'total_clauses': len(self._clauses),
            'categories': categories,
            'is_loaded': self._is_loaded
        }
    
    @property
    def is_loaded(self) -> bool:
        """Check if a clause library has been loaded."""
        return self._is_loaded and len(self._clauses) > 0
    
    @property
    def clause_count(self) -> int:
        """Get the number of loaded clauses."""
        return len(self._clauses)
    
    def clear(self) -> None:
        """Clear the loaded clause library."""
        self._clauses = []
        self._is_loaded = False
        logger.info("Clause library cleared")
