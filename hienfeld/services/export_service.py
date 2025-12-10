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
        original_df: Optional[pd.DataFrame] = None,
        hierarchical_results: Optional[List[Dict]] = None
    ) -> pd.DataFrame:
        """
        Build a DataFrame with analysis results, supporting hierarchical parent/child structure.
        
        Args:
            clauses: List of analyzed Clause objects (legacy, may be empty if using hierarchical_results)
            clusters: List of Cluster objects
            advice_map: Mapping of cluster_id -> AnalysisAdvice
            include_original_columns: Whether to include original data columns
            original_df: Original DataFrame (for preserving columns)
            hierarchical_results: Optional list of hierarchical result dicts with 'type' ('PARENT', 'CHILD', 'SINGLE')
            
        Returns:
            DataFrame with analysis results
        """
        # Use hierarchical results if available, otherwise fall back to legacy method
        if hierarchical_results:
            return self._build_hierarchical_dataframe(
                hierarchical_results,
                clusters,
                original_df
            )
        
        # Legacy method (backward compatibility)
        logger.info(f"Building results DataFrame from {len(clauses)} clauses (legacy mode)")
        
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
    
    def _build_hierarchical_dataframe(
        self,
        hierarchical_results: List[Dict],
        clusters: List[Cluster],
        original_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Build DataFrame from hierarchical results structure.
        
        Args:
            hierarchical_results: List of result dicts with 'type', 'id', 'cluster', 'advice', etc.
            clusters: List of Cluster objects (for lookup)
            original_df: Original DataFrame (for preserving columns)
            
        Returns:
            DataFrame with hierarchical structure
        """
        logger.info(f"Building hierarchical DataFrame from {len(hierarchical_results)} results")
        
        # Create cluster lookup
        cluster_lookup = {c.id: c for c in clusters}
        
        # Identify source columns (all except text column)
        source_cols = []
        if original_df is not None:
            # Find text column name (common names)
            text_cols = ['Tekst', 'Vrije Tekst', 'Clausule', 'Text', 'Description']
            text_col = None
            for col in text_cols:
                if col in original_df.columns:
                    text_col = col
                    break
            
            # All other columns are source columns
            source_cols = [c for c in original_df.columns if c != text_col]
        
        export_rows = []
        
        for item in hierarchical_results:
            item_type = item.get('type', 'SINGLE')
            item_id = item.get('id', 'UNKNOWN')
            cluster = item.get('cluster')
            advice = item.get('advice')
            
            # Base row data
            row = {
                'Type': item_type,  # Add Type column for filtering
                'Cluster_ID': item_id,
                'Advies': advice.advice_code if advice else '',
                'Vertrouwen': advice.confidence if advice else '',
                'Reden': advice.reason if advice else '',
                'Artikel': advice.reference_article if advice else '',
            }
            
            if item_type in ['PARENT', 'SINGLE']:
                # Parent/Single rows: include full cluster info and original data
                if cluster:
                    row['Cluster_Naam'] = cluster.name
                    row['Frequentie'] = cluster.frequency
                    row['Tekst'] = cluster.original_text
                    
                    # Get original row data from DataFrame
                    if original_df is not None:
                        # Find original row by extracting index from clause ID
                        # Clause IDs are formatted as "row_{idx}" or "{policy_number}_{idx}"
                        leader_clause = cluster.leader_clause
                        orig_idx = None
                        
                        # Extract index from clause ID
                        clause_id = leader_clause.id
                        if clause_id.startswith('row_'):
                            try:
                                orig_idx = int(clause_id.split('_')[1])
                            except (ValueError, IndexError):
                                pass
                        elif '_' in clause_id:
                            # Format: {policy_number}_{idx}
                            try:
                                parts = clause_id.rsplit('_', 1)
                                if len(parts) == 2:
                                    orig_idx = int(parts[1])
                            except (ValueError, IndexError):
                                pass
                        
                        # Fallback: try to find by matching text
                        if orig_idx is None:
                            # Find text column
                            text_cols = ['Tekst', 'Vrije Tekst', 'Clausule', 'Text', 'Description']
                            text_col = None
                            for col in text_cols:
                                if col in original_df.columns:
                                    text_col = col
                                    break
                            
                            if text_col:
                                for idx, orig_text in original_df[text_col].items():
                                    if str(orig_text).strip() == cluster.original_text.strip():
                                        orig_idx = idx
                                        break
                        
                        # Get original row data
                        if orig_idx is not None:
                            try:
                                # Use loc to get row by index (works with both numeric and named indices)
                                if orig_idx in original_df.index:
                                    original_row = original_df.loc[orig_idx]
                                    # Add ALL source columns
                                    for col in source_cols:
                                        row[col] = original_row[col]
                                else:
                                    # Index not found, fill with empty
                                    for col in source_cols:
                                        row[col] = ""
                            except (KeyError, IndexError):
                                # Index error, fill with empty
                                for col in source_cols:
                                    row[col] = ""
                        else:
                            # Could not find index, fill with empty
                            for col in source_cols:
                                row[col] = ""
                    else:
                        # No original_df, fill source columns with empty
                        for col in source_cols:
                            row[col] = ""
                    
                    # Add clean text proposal
                    clean_text = item.get('clean_text_proposal', '')
                    row['Nieuwe_Systeem_Tekst'] = clean_text
                    
                    # PARENT rows: show summary of child advices
                    if item_type == 'PARENT':
                        children = item.get('children', [])
                        if children:
                            # Summarize child advice codes
                            child_advice_counts = {}
                            for child in children:
                                child_adv = child.get('advice')
                                if child_adv:
                                    code = child_adv.advice_code
                                    child_advice_counts[code] = child_advice_counts.get(code, 0) + 1
                            
                            # Build summary string
                            summary_parts = [f"{count}x {code}" for code, count in child_advice_counts.items()]
                            summary_str = ", ".join(summary_parts) if summary_parts else "geen onderdelen"
                            
                            row['Advies'] = '⚠️ GESPLITST'
                            row['Reden'] = f"Gesplitst in {len(children)} onderdelen: {summary_str}"
                        else:
                            row['Advies'] = '⚠️ ZIE ONDERSTAANDE DELEN'
                            row['Reden'] = "Bevat meerdere onderdelen. Zie details hieronder."
                else:
                    # Fallback if no cluster
                    row['Cluster_Naam'] = ''
                    row['Frequentie'] = 0
                    row['Tekst'] = ''
                    row['Nieuwe_Systeem_Tekst'] = ''
                    for col in source_cols:
                        row[col] = ""
                
            elif item_type == 'CHILD':
                # Child rows: indent text, no source data
                row['Cluster_Naam'] = ''
                row['Frequentie'] = 0
                row['Tekst'] = f"    ↳ {item.get('text', '')}"  # Indentatie
                row['Nieuwe_Systeem_Tekst'] = ''  # Empty for children
                
                # Fill source columns with empty
                for col in source_cols:
                    row[col] = ""
            
            export_rows.append(row)
        
        df = pd.DataFrame(export_rows)
        
        # Sort by Cluster_ID (will group parent and children together)
        df = df.sort_values(by='Cluster_ID')
        
        logger.info(f"Created hierarchical DataFrame with {len(df)} rows, {len(df.columns)} columns")
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
            # Check if DataFrame has 'Type' column (hierarchical results)
            has_type_column = 'Type' in df.columns
            
            if has_type_column:
                # V2.2 DUAL-SHEET ARCHITECTURE
                # Sheet 1: Analyseresultaten (Clean flow)
                # - SINGLE types without SPLITSEN in Advies
                clean_mask = (df['Type'] == 'SINGLE') & (~df['Advies'].str.contains('SPLITSEN', na=False))
                clean_df = df[clean_mask].copy()
                if 'Type' in clean_df.columns:
                    clean_df = clean_df.drop(columns=['Type'])
                clean_df.to_excel(writer, sheet_name='Analyseresultaten', index=False)
                
                # Sheet 2: Te Splitsen & Complex
                # - PARENT and CHILD types
                # - SINGLE types WITH SPLITSEN in Advies
                complex_mask = (df['Type'].isin(['PARENT', 'CHILD'])) | ((df['Type'] == 'SINGLE') & (df['Advies'].str.contains('SPLITSEN', na=False)))
                complex_df = df[complex_mask].copy()
                if 'Type' in complex_df.columns:
                    complex_df = complex_df.drop(columns=['Type'])
                complex_df.to_excel(writer, sheet_name='Te Splitsen & Complex', index=False)
                
                logger.info(f"Dual-sheet Excel: {len(clean_df)} clean, {len(complex_df)} complex")
            else:
                # Legacy mode: Single sheet
                df.to_excel(writer, sheet_name=self.config.export.excel_sheet_name, index=False)
            
            # Optional summary sheet
            if include_summary and clusters and advice_map:
                summary_df = self.build_cluster_summary(clusters, advice_map)
                summary_df.to_excel(writer, sheet_name='Cluster Samenvatting', index=False)
        
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

