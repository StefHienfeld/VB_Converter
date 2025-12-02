# hienfeld/services/preprocessing_service.py
"""
Service for preprocessing and normalizing text data.
"""
from typing import List, Optional, Dict
import pandas as pd

from ..config import AppConfig
from ..domain.clause import Clause
from ..utils.text_normalization import simplify_text
from ..logging_config import get_logger

logger = get_logger('preprocessing_service')


class PreprocessingService:
    """
    Handles text preprocessing and conversion to domain objects.
    
    Responsibilities:
    - Normalize text using configurable rules
    - Convert DataFrame rows to Clause objects
    - Apply synonym mapping
    """
    
    def __init__(self, config: AppConfig, synonym_map: Optional[Dict[str, str]] = None):
        """
        Initialize the preprocessing service.
        
        Args:
            config: Application configuration
            synonym_map: Optional dictionary mapping terms to canonical forms
        """
        self.config = config
        self.synonym_map = synonym_map or {}
    
    def simplify_text(self, text: str) -> str:
        """
        Simplify text for comparison.
        
        Uses the utility function with optional synonym mapping.
        
        Args:
            text: Raw text to simplify
            
        Returns:
            Normalized, simplified text
        """
        return simplify_text(text, self.synonym_map)
    
    def dataframe_to_clauses(
        self,
        df: pd.DataFrame,
        text_col: str,
        policy_number_col: Optional[str] = None,
        source_file_name: Optional[str] = None
    ) -> List[Clause]:
        """
        Convert DataFrame rows to Clause domain objects.
        
        Args:
            df: DataFrame containing policy data
            text_col: Name of the column with free text
            policy_number_col: Optional column with policy numbers
            source_file_name: Name of the source file
            
        Returns:
            List of Clause objects
        """
        logger.info(f"Converting DataFrame to Clauses (text_col={text_col})")
        
        clauses = []
        
        for idx, row in df.iterrows():
            raw_text = str(row.get(text_col, ''))
            
            # Get policy number if available
            policy_number = None
            if policy_number_col and policy_number_col in row:
                policy_number = str(row[policy_number_col])
            
            # Generate ID
            if policy_number:
                clause_id = f"{policy_number}_{idx}"
            else:
                clause_id = f"row_{idx}"
            
            # Create Clause object
            clause = Clause(
                id=clause_id,
                raw_text=raw_text,
                simplified_text=self.simplify_text(raw_text),
                source_policy_number=policy_number,
                source_file_name=source_file_name
            )
            
            clauses.append(clause)
        
        logger.info(f"Created {len(clauses)} Clause objects")
        return clauses
    
    def filter_empty_clauses(self, clauses: List[Clause]) -> List[Clause]:
        """
        Remove clauses with empty or very short text.
        
        Args:
            clauses: List of Clause objects
            
        Returns:
            Filtered list without empty clauses
        """
        min_length = self.config.clustering.min_text_length
        filtered = [c for c in clauses if not c.is_empty and len(c.simplified_text) >= min_length]
        
        removed = len(clauses) - len(filtered)
        if removed > 0:
            logger.info(f"Filtered out {removed} empty/short clauses")
        
        return filtered
    
    def sort_clauses_by_length(self, clauses: List[Clause], descending: bool = True) -> List[Clause]:
        """
        Sort clauses by text length.
        
        Sorting by length (descending) helps the Leader algorithm
        by ensuring longer, more specific texts become leaders first.
        
        Args:
            clauses: List of Clause objects
            descending: Sort longest first (default True)
            
        Returns:
            Sorted list of clauses
        """
        return sorted(
            clauses,
            key=lambda c: len(c.simplified_text),
            reverse=descending
        )
    
    def add_synonym(self, term: str, canonical: str) -> None:
        """
        Add a synonym mapping.
        
        Args:
            term: Term to replace
            canonical: Canonical form to use
        """
        self.synonym_map[term.lower()] = canonical.lower()
    
    def load_synonyms_from_dict(self, synonyms: Dict[str, str]) -> None:
        """
        Load multiple synonyms from a dictionary.
        
        Args:
            synonyms: Dictionary of term -> canonical mappings
        """
        for term, canonical in synonyms.items():
            self.add_synonym(term, canonical)

