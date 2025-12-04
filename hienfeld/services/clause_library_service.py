# hienfeld/services/clause_library_service.py
"""
Service for managing and searching the standard clause library.

The clause library contains pre-approved standard clauses that can be used
to replace similar free text clauses, enabling policy standardization.
"""
from typing import List, Optional, Tuple
from io import BytesIO
import pandas as pd
import re

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
    - Load clause library from CSV/Excel
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
    
    def load_from_file(self, file_bytes: bytes, filename: str) -> int:
        """
        Load clause library from CSV, Excel, PDF, or Word file.
        
        For CSV/Excel:
        - Expected columns (case-insensitive): Code, Tekst/Text, Categorie/Category (optional)
        
        For PDF/Word:
        - Automatically extracts clauses by finding clause codes (pattern: \d[A-Z]{2}\d)
        - Extracts text following each code until next code or section break
        
        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename (for format detection)
            
        Returns:
            Number of clauses loaded
            
        Raises:
            ValueError: If file format is not supported
        """
        logger.info(f"Loading clause library from: {filename}")
        
        filename_lower = filename.lower()
        
        # Load data based on file type
        if filename_lower.endswith('.csv'):
            file_obj = BytesIO(file_bytes)
            df = self._load_csv(file_obj, file_bytes)
            self._clauses = self._parse_dataframe(df)
        elif filename_lower.endswith(('.xlsx', '.xls')):
            file_obj = BytesIO(file_bytes)
            df = pd.read_excel(file_obj)
            self._clauses = self._parse_dataframe(df)
        elif filename_lower.endswith('.pdf'):
            self._clauses = self._parse_pdf(file_bytes, filename)
        elif filename_lower.endswith('.docx'):
            self._clauses = self._parse_docx(file_bytes, filename)
        else:
            raise ValueError(
                f"Unsupported file format: {filename}. "
                f"Supported formats: CSV, Excel (.xlsx, .xls), PDF, Word (.docx)"
            )
        
        self._is_loaded = True
        logger.info(f"Loaded {len(self._clauses)} standard clauses from {filename}")
        
        return len(self._clauses)
    
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
    
    def _parse_pdf(self, file_bytes: bytes, filename: str) -> List[StandardClause]:
        """
        Parse PDF file and extract clauses.
        
        Looks for clause codes (pattern: \d[A-Z]{2}\d) and extracts text following each code.
        
        Args:
            file_bytes: Raw bytes of PDF file
            filename: Source filename
            
        Returns:
            List of StandardClause objects
        """
        text = ""
        
        # Try PyMuPDF (fitz) first
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            logger.info(f"Parsed PDF with PyMuPDF")
        except ImportError:
            logger.debug("PyMuPDF not available, trying pdfplumber")
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}, trying pdfplumber")
        
        # Try pdfplumber as fallback
        if not text:
            try:
                import pdfplumber
                with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        text += page_text + "\n"
                logger.info(f"Parsed PDF with pdfplumber")
            except ImportError:
                raise ValueError("PDF parsing requires PyMuPDF or pdfplumber. Install with: pip install PyMuPDF pdfplumber")
            except Exception as e:
                raise ValueError(f"Failed to parse PDF: {e}")
        
        if not text.strip():
            raise ValueError("Could not extract text from PDF. File may be empty or corrupted.")
        
        return self._extract_clauses_from_text(text, filename)
    
    def _parse_docx(self, file_bytes: bytes, filename: str) -> List[StandardClause]:
        """
        Parse Word DOCX file and extract clauses.
        
        Looks for clause codes (pattern: \d[A-Z]{2}\d) and extracts text following each code.
        
        Args:
            file_bytes: Raw bytes of DOCX file
            filename: Source filename
            
        Returns:
            List of StandardClause objects
        """
        try:
            from docx import Document
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            text = "\n".join(paragraphs)
            
            if not text.strip():
                raise ValueError("Could not extract text from Word document. File may be empty.")
            
            return self._extract_clauses_from_text(text, filename)
        except ImportError:
            raise ValueError("Word parsing requires python-docx. Install with: pip install python-docx")
        except Exception as e:
            raise ValueError(f"Failed to parse Word document: {e}")
    
    def _extract_clauses_from_text(self, text: str, source_filename: str) -> List[StandardClause]:
        """
        Extract clauses from unstructured text by finding clause codes.
        
        Pattern: Looks for codes like "9NX3", "VB12" (format: \d[A-Z]{2}\d)
        Extracts text following each code until next code or section break.
        
        Args:
            text: Full text content
            source_filename: Source filename for logging
            
        Returns:
            List of StandardClause objects
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
                current_category = category  # Use for next clause if no header found
        
        logger.info(f"Geëxtraheerd {len(clauses)} clausules uit {source_filename}")
        
        return clauses
    
    def _detect_category(self, before_text: str, clause_text: str) -> str:
        """
        Try to detect category from context or clause content.
        
        Args:
            before_text: Text before the clause code
            clause_text: The clause text itself
            
        Returns:
            Detected category or "Algemeen"
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

