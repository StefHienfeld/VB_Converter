# hienfeld/services/policy_parser_service.py
"""
Service for parsing policy condition documents (PDF/DOCX/TXT).
"""
from typing import List, Optional
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
    
    def __init__(self, config: AppConfig):
        """
        Initialize the policy parser service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Article heading patterns (Dutch)
        self.article_patterns = [
            r'^\s*Artikel\s+(\d+(?:\.\d+)?)\s*[:\.\-]?\s*(.*)$',
            r'^\s*Art\.?\s+(\d+(?:\.\d+)?)\s*[:\.\-]?\s*(.*)$',
            r'^(\d+(?:\.\d+)?)\s*[:\.\-]\s+(.+)$'
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
        
        Args:
            text: Full text content
            filename: Source filename
            
        Returns:
            List of sections
        """
        sections = []
        current_section = None
        current_text = []
        
        for line in text.split('\n'):
            # Check if line is an article heading
            article_match = None
            for pattern in self.article_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    article_match = match
                    break
            
            if article_match:
                # Save previous section
                if current_section:
                    section_text = '\n'.join(current_text).strip()
                    current_section.raw_text = section_text
                    current_section.simplified_text = simplify_text(section_text)
                    if not current_section.is_empty:
                        sections.append(current_section)
                
                # Start new section
                article_num = article_match.group(1)
                title = article_match.group(2).strip() if article_match.lastindex >= 2 else ""
                
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
        
        # If no sections found, create single section from all text
        if not sections:
            sections.append(PolicyDocumentSection(
                id="DOC-1",
                title="Voorwaarden",
                raw_text=text,
                simplified_text=simplify_text(text),
                document_id=filename
            ))
        
        logger.info(f"Extracted {len(sections)} sections from {filename}")
        return sections
    
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

