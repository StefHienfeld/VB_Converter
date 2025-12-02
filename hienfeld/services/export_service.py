# hienfeld/services/export_service.py
"""
Service for exporting analysis results to various formats.
"""
from typing import Dict, List, Optional
from io import BytesIO
import pandas as pd

from ..config import AppConfig
from ..domain.clause import Clause
from ..domain.cluster import Cluster
from ..domain.analysis import AnalysisAdvice
from ..logging_config import get_logger

logger = get_logger('export_service')


class ExportService:
    """
    Handles export of analysis results to Excel and other formats.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the export service.
        
        Args:
            config: Application configuration
        """
        self.config = config
    
    def build_results_dataframe(
        self,
        clauses: List[Clause],
        clusters: List[Cluster],
        advice_map: Dict[str, AnalysisAdvice],
        include_original_columns: bool = True,
        original_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Build a DataFrame with analysis results.
        
        Args:
            clauses: List of analyzed Clause objects
            clusters: List of Cluster objects
            advice_map: Mapping of cluster_id -> AnalysisAdvice
            include_original_columns: Whether to include original data columns
            original_df: Original DataFrame (for preserving columns)
            
        Returns:
            DataFrame with analysis results
        """
        logger.info(f"Building results DataFrame from {len(clauses)} clauses")
        
        # Create cluster lookup for efficiency
        cluster_lookup = {c.id: c for c in clusters}
        
        # Build rows
        rows = []
        for clause in clauses:
            cluster_id = clause.cluster_id or "NVT"
            
            # Get cluster info
            cluster = cluster_lookup.get(cluster_id)
            advice = advice_map.get(cluster_id)
            
            row = {
                'Clause_ID': clause.id,
                'Cluster_ID': cluster_id,
                'Cluster_Naam': cluster.name if cluster else '',
                'Frequentie': cluster.frequency if cluster else 0,
                'Advies': advice.advice_code if advice else '',
                'Vertrouwen': advice.confidence if advice else '',
                'Reden': advice.reason if advice else '',
                'Artikel': advice.reference_article if advice else '',
                'Tekst': clause.raw_text,
                'Is_Multi_Clause': clause.is_multi_clause
            }
            
            # Add policy number if available
            if clause.source_policy_number:
                row['Polisnummer'] = clause.source_policy_number
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Sort by cluster ID for readability
        df = df.sort_values(by='Cluster_ID')
        
        logger.info(f"Created DataFrame with {len(df)} rows, {len(df.columns)} columns")
        return df
    
    def build_cluster_summary(
        self,
        clusters: List[Cluster],
        advice_map: Dict[str, AnalysisAdvice]
    ) -> pd.DataFrame:
        """
        Build a summary DataFrame with one row per cluster.
        
        Args:
            clusters: List of Cluster objects
            advice_map: Mapping of cluster_id -> AnalysisAdvice
            
        Returns:
            Summary DataFrame
        """
        rows = []
        
        for cluster in clusters:
            advice = advice_map.get(cluster.id)
            
            row = {
                'Cluster_ID': cluster.id,
                'Cluster_Naam': cluster.name,
                'Frequentie': cluster.frequency,
                'Advies': advice.advice_code if advice else '',
                'Vertrouwen': advice.confidence if advice else '',
                'Reden': advice.reason if advice else '',
                'Artikel': advice.reference_article if advice else '',
                'Voorbeeld_Tekst': cluster.original_text[:200] + '...' if len(cluster.original_text) > 200 else cluster.original_text
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df = df.sort_values(by='Cluster_ID')
        
        return df
    
    def to_excel_bytes(
        self, 
        df: pd.DataFrame,
        include_summary: bool = False,
        clusters: Optional[List[Cluster]] = None,
        advice_map: Optional[Dict[str, AnalysisAdvice]] = None
    ) -> bytes:
        """
        Export DataFrame to Excel bytes.
        
        Args:
            df: Main results DataFrame
            include_summary: Whether to include a summary sheet
            clusters: Clusters for summary (required if include_summary=True)
            advice_map: Advice map for summary (required if include_summary=True)
            
        Returns:
            Excel file as bytes
        """
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Main data sheet
            df.to_excel(
                writer, 
                sheet_name=self.config.export.excel_sheet_name,
                index=False
            )
            
            # Optional summary sheet
            if include_summary and clusters and advice_map:
                summary_df = self.build_cluster_summary(clusters, advice_map)
                summary_df.to_excel(
                    writer,
                    sheet_name='Cluster Samenvatting',
                    index=False
                )
        
        logger.info("Generated Excel file")
        return output.getvalue()
    
    def to_csv_bytes(self, df: pd.DataFrame, delimiter: str = ';') -> bytes:
        """
        Export DataFrame to CSV bytes.
        
        Args:
            df: DataFrame to export
            delimiter: CSV delimiter (default: ';' for Dutch Excel)
            
        Returns:
            CSV file as bytes
        """
        output = BytesIO()
        df.to_csv(output, sep=delimiter, index=False, encoding='utf-8-sig')
        return output.getvalue()
    
    def get_statistics_summary(
        self,
        clauses: List[Clause],
        clusters: List[Cluster],
        advice_map: Dict[str, AnalysisAdvice]
    ) -> dict:
        """
        Generate statistics summary for display.
        
        Args:
            clauses: All clauses
            clusters: All clusters
            advice_map: All advice
            
        Returns:
            Dictionary with statistics
        """
        total_rows = len(clauses)
        unique_clusters = len(clusters)
        
        # Count by advice type
        advice_counts = {}
        category_counts = {}
        found_in_conditions = 0
        
        for advice in advice_map.values():
            code = advice.advice_code
            advice_counts[code] = advice_counts.get(code, 0) + 1
            
            # Track categories
            cat = advice.category or "UNKNOWN"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
            # Track items found in conditions (KRITIEKE METRIC!)
            if cat and 'VOORWAARDEN' in cat:
                found_in_conditions += 1
        
        # Reduction percentage
        reduction = int((1 - unique_clusters / total_rows) * 100) if total_rows > 0 else 0
        
        # Multi-clause count
        multi_clause_count = sum(1 for c in clauses if c.is_multi_clause)
        
        return {
            'total_rows': total_rows,
            'unique_clusters': unique_clusters,
            'reduction_percentage': reduction,
            'multi_clause_count': multi_clause_count,
            'advice_distribution': advice_counts,
            'category_distribution': category_counts,
            'found_in_conditions': found_in_conditions,
            'avg_cluster_size': total_rows / unique_clusters if unique_clusters > 0 else 0
        }
    
    def format_column_selection(
        self,
        df: pd.DataFrame,
        text_col: str
    ) -> pd.DataFrame:
        """
        Select and order columns for final output.
        
        Args:
            df: Full DataFrame
            text_col: Name of the original text column
            
        Returns:
            DataFrame with selected columns in order
        """
        # Define desired column order
        priority_cols = [
            'Cluster_ID', 'Cluster_Naam', 'Frequentie',
            'Advies', 'Vertrouwen', 'Reden', 'Artikel'
        ]
        
        # Add text column
        if 'Tekst' in df.columns:
            priority_cols.append('Tekst')
        elif text_col in df.columns:
            priority_cols.append(text_col)
        
        # Filter to existing columns
        existing_cols = [c for c in priority_cols if c in df.columns]
        
        # Add any remaining columns
        other_cols = [c for c in df.columns if c not in existing_cols]
        
        return df[existing_cols + other_cols]

