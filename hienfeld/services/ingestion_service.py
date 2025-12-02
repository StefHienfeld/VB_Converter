# hienfeld/services/ingestion_service.py
"""
Service for ingesting policy data files (CSV/Excel).
"""
from typing import List, Optional
from io import BytesIO
import pandas as pd

from ..config import AppConfig
from ..logging_config import get_logger
from ..utils.csv_utils import detect_encoding, detect_delimiter

logger = get_logger('ingestion_service')


class IngestionService:
    """
    Handles loading and initial processing of policy data files.
    
    Responsibilities:
    - Load CSV and Excel files
    - Detect encoding and delimiters
    - Identify text columns
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the ingestion service.
        
        Args:
            config: Application configuration
        """
        self.config = config
    
    def load_policy_file(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        """
        Load a policy file (CSV or Excel) into a DataFrame.
        
        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename (used for format detection)
            
        Returns:
            DataFrame containing the policy data
            
        Raises:
            ValueError: If file format is not supported
        """
        logger.info(f"Loading policy file: {filename}")
        
        file_obj = BytesIO(file_bytes)
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.csv'):
            return self._load_csv(file_obj, file_bytes)
        elif filename_lower.endswith(('.xlsx', '.xls')):
            return self._load_excel(file_obj)
        else:
            raise ValueError(f"Unsupported file format: {filename}")
    
    def _load_csv(self, file_obj: BytesIO, file_bytes: bytes) -> pd.DataFrame:
        """
        Load CSV file with encoding and delimiter detection.
        
        Args:
            file_obj: BytesIO object for reading
            file_bytes: Raw bytes for encoding detection
            
        Returns:
            DataFrame with CSV data
        """
        # Detect encoding
        encoding = detect_encoding(
            file_bytes, 
            fallback=self.config.ingestion.fallback_encoding
        )
        logger.debug(f"Detected encoding: {encoding}")
        
        # Detect delimiter from first 4KB
        sample = file_bytes[:4096].decode(encoding, errors='ignore')
        delimiter = detect_delimiter(sample, self.config.ingestion.csv_delimiters)
        logger.debug(f"Detected delimiter: {repr(delimiter)}")
        
        # Try loading with detected settings
        try:
            file_obj.seek(0)
            df = pd.read_csv(
                file_obj,
                delimiter=delimiter,
                encoding=encoding,
                on_bad_lines='skip'
            )
            logger.info(f"Loaded CSV with {len(df)} rows, {len(df.columns)} columns")
            return df
        except Exception as e:
            logger.warning(f"Failed with detected settings, trying fallback: {e}")
            
            # Fallback: try different encoding
            file_obj.seek(0)
            return pd.read_csv(
                file_obj,
                delimiter=delimiter,
                encoding=self.config.ingestion.fallback_encoding,
                on_bad_lines='skip'
            )
    
    def _load_excel(self, file_obj: BytesIO) -> pd.DataFrame:
        """
        Load Excel file.
        
        Args:
            file_obj: BytesIO object for reading
            
        Returns:
            DataFrame with Excel data
        """
        df = pd.read_excel(file_obj)
        logger.info(f"Loaded Excel with {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def detect_text_column(self, df: pd.DataFrame) -> str:
        """
        Identify the column containing free text clauses.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Name of the text column
        """
        # Check preferred column names from config
        for col_name in self.config.ingestion.preferred_text_columns:
            if col_name in df.columns:
                logger.info(f"Found text column: {col_name}")
                return col_name
        
        # Check case-insensitive
        col_lower_map = {col.lower(): col for col in df.columns}
        for preferred in self.config.ingestion.preferred_text_columns:
            if preferred.lower() in col_lower_map:
                found = col_lower_map[preferred.lower()]
                logger.info(f"Found text column (case-insensitive): {found}")
                return found
        
        # Fallback: last column (often contains free text)
        fallback = df.columns[-1]
        logger.warning(f"No preferred column found, using fallback: {fallback}")
        return fallback
    
    def detect_policy_number_column(self, df: pd.DataFrame) -> Optional[str]:
        """
        Try to identify a policy number column.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Name of policy number column or None
        """
        policy_indicators = ['polisnummer', 'polis', 'policy', 'nummer', 'number', 'id']
        
        for col in df.columns:
            col_lower = col.lower()
            if any(ind in col_lower for ind in policy_indicators):
                logger.info(f"Found policy number column: {col}")
                return col
        
        return None
    
    def get_column_info(self, df: pd.DataFrame) -> dict:
        """
        Get information about DataFrame columns.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Dictionary with column information
        """
        return {
            'columns': list(df.columns),
            'row_count': len(df),
            'text_column': self.detect_text_column(df),
            'policy_column': self.detect_policy_number_column(df),
            'dtypes': df.dtypes.to_dict()
        }

