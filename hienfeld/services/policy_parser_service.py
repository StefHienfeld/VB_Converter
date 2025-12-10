# hienfeld/services/policy_parser_service.py
"""
Service for parsing policy condition documents (PDF/DOCX/TXT).

IMPROVED v2.1: Better article detection with:
- Support for numbered headers (1.1, 2.3, etc.)
- Paragraph-based splitting for better granularity
- Filtering of false positive year matches (1979, 2014)
- Maximum section size enforcement
"""
from typing import List, Optional, Tuple
import re
from io import BytesIO

from ..config import AppConfig
from ..domain.policy_document import PolicyDocumentSection
from ..utils.text_normalization import simplify_text
from ..logging_config import get_logger

logger = get_logger('policy_parser_service')


class PolicyParserService:
    """
    Handles parsing of policy condition documents.
    
    Responsibilities:
    - Parse PDF, DOCX, and TXT files
    - Extract article/section structure
    - Create PolicyDocumentSection objects
    """
    
    # Maximum characters per section (for better matching)
    MAX_SECTION_LENGTH = 2000
    
    # Valid article number range (to filter out years like 1979)
    MIN_ARTICLE_NUM = 1
    MAX_ARTICLE_NUM = 50
    
    def __init__(self, config: AppConfig):
        """
        Initialize the policy parser service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Article heading patterns (Dutch) - IMPROVED
        # Order matters: most specific patterns first
        self.article_patterns = [
            # "Artikel 1.2" or "Artikel 1" with optional title
            (r'^\s*Artikel\s+(\d+(?:\.\d+)?)\s*[:\.\-]?\s*(.*)$', 'artikel'),
            # "Art. 1.2" or "Art 1"
            (r'^\s*Art\.?\s+(\d+(?:\.\d+)?)\s*[:\.\-]?\s*(.*)$', 'art'),
            # Numbered sections like "1.1 Title" or "2.3.4 Title" (at start of line)
            (r'^(\d+(?:\.\d+)+)\s+([A-Z][a-zA-Z\s]+.*)$', 'numbered'),
            # Single number with title "1 Algemeen" (but NOT years like "1979")
            (r'^(\d{1,2})\s+([A-Z][a-zA-Z\s]{3,}.*)$', 'single_num'),
        ]
        
        # Keywords that indicate section headers
        self.section_keywords = [
            'Dekking', 'Uitsluitingen', 'Verplichtingen', 'Premie', 'Schade',
            'Begripsomschrijvingen', 'Algemeen', 'Gebouwverzekering', 
            'Inboedelverzekering', 'Kostbaarheden', 'Aansprakelijkheid',
            'Wijzigingen', 'Begin en einde', 'Overige bepalingen'
        ]
    
    def parse_policy_file(self, file_bytes: bytes, filename: str) -> List[PolicyDocumentSection]:
        """
        Parse a policy conditions file and extract sections.
        
        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename
            
        Returns:
            List of PolicyDocumentSection objects
        """
        filename_lower = filename.lower()
        
        logger.info(f"Parsing policy file: {filename}")
        
        if filename_lower.endswith('.docx'):
            return self._parse_docx(file_bytes, filename)
        elif filename_lower.endswith('.pdf'):
            return self._parse_pdf(file_bytes, filename)
        elif filename_lower.endswith('.txt'):
            return self._parse_txt(file_bytes, filename)
        else:
            logger.warning(f"Unknown file type: {filename}, treating as TXT")
            return self._parse_txt(file_bytes, filename)
    
    def _parse_docx(self, file_bytes: bytes, filename: str) -> List[PolicyDocumentSection]:
        """
        Parse a DOCX file.
        
        Args:
            file_bytes: Raw bytes of DOCX file
            filename: Source filename
            
        Returns:
            List of sections
        """
        try:
            from docx import Document
            
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            
            full_text = "\n".join(paragraphs)
            return self._segment_text(full_text, filename)
            
        except ImportError:
            logger.error("python-docx not installed, cannot parse DOCX")
            return [self._create_fallback_section(file_bytes, filename)]
        except Exception as e:
            logger.error(f"Error parsing DOCX: {e}")
            return [self._create_fallback_section(file_bytes, filename)]
    
    def _parse_pdf(self, file_bytes: bytes, filename: str) -> List[PolicyDocumentSection]:
        """
        Parse a PDF file.
        
        Tries multiple PDF libraries for best results.
        
        Args:
            file_bytes: Raw bytes of PDF file
            filename: Source filename
            
        Returns:
            List of sections
        """
        text = ""
        page_texts = []
        
        # Try PyMuPDF (fitz) first - best quality
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                page_texts.append((page_num + 1, page_text))
                text += page_text + "\n"
            doc.close()
            
            logger.info(f"Parsed PDF with PyMuPDF: {len(page_texts)} pages")
            return self._segment_text_with_pages(page_texts, filename)
            
        except ImportError:
            logger.debug("PyMuPDF not available, trying pdfplumber")
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}, trying pdfplumber")
        
        # Try pdfplumber as fallback
        try:
            import pdfplumber
            
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    page_texts.append((page_num + 1, page_text))
                    text += page_text + "\n"
            
            logger.info(f"Parsed PDF with pdfplumber: {len(page_texts)} pages")
            return self._segment_text_with_pages(page_texts, filename)
            
        except ImportError:
            logger.warning("Neither PyMuPDF nor pdfplumber installed")
        except Exception as e:
            logger.error(f"pdfplumber failed: {e}")
        
        # Final fallback
        logger.warning("PDF parsing not available - returning placeholder")
        return [PolicyDocumentSection(
            id="PDF-1",
            title="PDF Document",
            raw_text="[PDF parsing requires PyMuPDF or pdfplumber]",
            simplified_text="pdf parsing requires pymupdf or pdfplumber",
            document_id=filename
        )]
    
    def _parse_txt(self, file_bytes: bytes, filename: str) -> List[PolicyDocumentSection]:
        """
        Parse a TXT file.
        
        Args:
            file_bytes: Raw bytes of TXT file
            filename: Source filename
            
        Returns:
            List of sections
        """
        # Try different encodings
        for encoding in ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = file_bytes.decode('utf-8', errors='ignore')
        
        return self._segment_text(text, filename)
    
    def _segment_text(self, text: str, filename: str) -> List[PolicyDocumentSection]:
        """
        Segment text into article/section structure.
        
        IMPROVED v2.1:
        - Better article number validation (filters years like 1979)
        - Paragraph-based splitting for large sections
        - Keyword-based section detection
        
        Args:
            text: Full text content
            filename: Source filename
            
        Returns:
            List of sections
        """
        sections = []
        current_section = None
        current_text = []
        
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines):
            # Check if line is an article heading
            article_info = self._detect_article_header(line)
            
            if article_info:
                article_num, title, pattern_type = article_info
                
                # Save previous section
                if current_section:
                    section_text = '\n'.join(current_text).strip()
                    current_section.raw_text = section_text
                    current_section.simplified_text = simplify_text(section_text)
                    if not current_section.is_empty:
                        sections.append(current_section)
                
                # Start new section
                current_section = PolicyDocumentSection(
                    id=f"Art {article_num}",
                    title=title,
                    raw_text="",
                    simplified_text="",
                    document_id=filename
                )
                current_text = []
            else:
                current_text.append(line)
        
        # Don't forget last section
        if current_section:
            section_text = '\n'.join(current_text).strip()
            current_section.raw_text = section_text
            current_section.simplified_text = simplify_text(section_text)
            if not current_section.is_empty:
                sections.append(current_section)
        
        # If no sections found or sections are too large, use paragraph splitting
        if not sections or self._needs_paragraph_splitting(sections):
            logger.info(f"Using paragraph-based splitting for {filename}")
            sections = self._split_by_paragraphs(text, filename)
        
        # Split any remaining large sections
        sections = self._split_large_sections(sections, filename)
        
        logger.info(f"Extracted {len(sections)} sections from {filename}")
        return sections
    
    def _detect_article_header(self, line: str) -> Optional[Tuple[str, str, str]]:
        """
        Detect if a line is an article header.
        
        Returns:
            Tuple of (article_num, title, pattern_type) if header found, None otherwise
        """
        line_stripped = line.strip()
        
        for pattern, pattern_type in self.article_patterns:
            match = re.match(pattern, line_stripped, re.IGNORECASE)
            if match:
                article_num = match.group(1)
                title = match.group(2).strip() if match.lastindex >= 2 else ""
                
                # Validate article number (filter years like 1979, 2014)
                if not self._is_valid_article_number(article_num):
                    continue
                
                return (article_num, title, pattern_type)
        
        return None
    
    def _is_valid_article_number(self, article_num: str) -> bool:
        """
        Check if an article number is valid (not a year or other false positive).
        
        Args:
            article_num: The article number string (e.g., "1.2", "21", "1979")
            
        Returns:
            True if valid article number, False otherwise
        """
        # Extract the main number (before any decimal)
        main_num_str = article_num.split('.')[0]
        
        try:
            main_num = int(main_num_str)
        except ValueError:
            return False
        
        # Filter out years (1900-2100) and other clearly invalid numbers
        if main_num >= 1900 and main_num <= 2100:
            return False
        
        # Valid article numbers are typically 1-50
        if main_num < self.MIN_ARTICLE_NUM or main_num > self.MAX_ARTICLE_NUM:
            return False
        
        return True
    
    def _needs_paragraph_splitting(self, sections: List[PolicyDocumentSection]) -> bool:
        """
        Check if sections need additional paragraph-based splitting.
        
        Returns True if:
        - Only 1-2 sections (document wasn't properly split)
        - Any section is very large (>10000 chars)
        """
        if len(sections) <= 2:
            return True
        
        for section in sections:
            if len(section.raw_text) > 10000:
                return True
        
        return False
    
    def _split_by_paragraphs(self, text: str, filename: str) -> List[PolicyDocumentSection]:
        """
        Split text by paragraphs (double newlines) and keywords.
        
        Creates more granular sections for better matching.
        """
        sections = []
        
        # Split on double newlines (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_section_text = []
        current_section_id = 1
        current_title = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < 20:
                continue
            
            # Check if paragraph starts with a section keyword
            new_title = self._detect_keyword_header(para)
            
            if new_title and current_section_text:
                # Save current section
                section_text = '\n\n'.join(current_section_text)
                sections.append(PolicyDocumentSection(
                    id=f"Sec {current_section_id}",
                    title=current_title or f"Sectie {current_section_id}",
                    raw_text=section_text,
                    simplified_text=simplify_text(section_text),
                    document_id=filename
                ))
                current_section_id += 1
                current_section_text = []
                current_title = new_title
            elif new_title:
                current_title = new_title
            
            current_section_text.append(para)
            
            # Force split if section gets too long
            combined = '\n\n'.join(current_section_text)
            if len(combined) > self.MAX_SECTION_LENGTH:
                sections.append(PolicyDocumentSection(
                    id=f"Sec {current_section_id}",
                    title=current_title or f"Sectie {current_section_id}",
                    raw_text=combined,
                    simplified_text=simplify_text(combined),
                    document_id=filename
                ))
                current_section_id += 1
                current_section_text = []
                current_title = ""
        
        # Don't forget last section
        if current_section_text:
            section_text = '\n\n'.join(current_section_text)
            sections.append(PolicyDocumentSection(
                id=f"Sec {current_section_id}",
                title=current_title or f"Sectie {current_section_id}",
                raw_text=section_text,
                simplified_text=simplify_text(section_text),
                document_id=filename
            ))
        
        return sections
    
    def _detect_keyword_header(self, para: str) -> Optional[str]:
        """
        Detect if a paragraph starts with a section keyword.
        
        Returns the keyword/title if found, None otherwise.
        """
        first_line = para.split('\n')[0].strip()
        
        for keyword in self.section_keywords:
            if first_line.lower().startswith(keyword.lower()):
                return first_line[:80]  # Truncate long titles
        
        # Also detect ALL CAPS headers
        if first_line.isupper() and len(first_line) > 5 and len(first_line) < 100:
            return first_line
        
        return None
    
    def _split_large_sections(
        self, 
        sections: List[PolicyDocumentSection], 
        filename: str
    ) -> List[PolicyDocumentSection]:
        """
        Split any remaining large sections into smaller chunks.
        """
        result = []
        
        for section in sections:
            if len(section.raw_text) <= self.MAX_SECTION_LENGTH:
                result.append(section)
            else:
                # Split into chunks
                chunks = self._split_text_into_chunks(
                    section.raw_text, 
                    self.MAX_SECTION_LENGTH
                )
                
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{section.id}.{i+1}" if len(chunks) > 1 else section.id
                    result.append(PolicyDocumentSection(
                        id=chunk_id,
                        title=section.title if i == 0 else f"{section.title} (vervolg)",
                        raw_text=chunk,
                        simplified_text=simplify_text(chunk),
                        document_id=filename,
                        page_number=section.page_number
                    ))
        
        return result
    
    def _split_text_into_chunks(self, text: str, max_length: int) -> List[str]:
        """
        Split text into chunks of maximum length, trying to break at sentence boundaries.
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Split by sentences (roughly)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                current_chunk = current_chunk + " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _segment_text_with_pages(
        self, 
        page_texts: List[tuple], 
        filename: str
    ) -> List[PolicyDocumentSection]:
        """
        Segment text while preserving page numbers.
        
        Args:
            page_texts: List of (page_num, text) tuples
            filename: Source filename
            
        Returns:
            List of sections with page numbers
        """
        # Combine all text first
        full_text = "\n".join([text for _, text in page_texts])
        sections = self._segment_text(full_text, filename)
        
        # Try to assign page numbers (simplified approach)
        # In a production system, this would track positions more carefully
        for section in sections:
            for page_num, page_text in page_texts:
                if section.title and section.title in page_text:
                    section.page_number = page_num
                    break
        
        return sections
    
    def _create_fallback_section(self, file_bytes: bytes, filename: str) -> PolicyDocumentSection:
        """
        Create a fallback section when parsing fails.
        
        Args:
            file_bytes: Raw bytes
            filename: Source filename
            
        Returns:
            Single section with available content
        """
        try:
            text = file_bytes.decode('utf-8', errors='ignore')
        except:
            text = "[Could not decode file content]"
        
        return PolicyDocumentSection(
            id="FALLBACK-1",
            title="Document",
            raw_text=text,
            simplified_text=simplify_text(text),
            document_id=filename
        )
    
    def get_all_text(self, sections: List[PolicyDocumentSection]) -> str:
        """
        Combine all sections into single text.
        
        Args:
            sections: List of PolicyDocumentSection objects
            
        Returns:
            Combined simplified text
        """
        return " ".join(s.simplified_text for s in sections if s.simplified_text)

