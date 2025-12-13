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

        # Identify source columns (all except the text column)
        source_cols: List[str] = []
        if include_original_columns and original_df is not None:
            text_col = self._detect_text_column(original_df)
            source_cols = [c for c in original_df.columns if c != text_col]
        
        # Build rows
        rows = []
        for clause in clauses:
            cluster_id = clause.cluster_id or "NVT"
            
            # Get cluster info
            cluster = cluster_lookup.get(cluster_id)
            advice = advice_map.get(cluster_id)
            
            row = {
                # NEW: Status kolom (leeg) voor collega's tracking
                'Status': '',
                'Cluster_ID': cluster_id,
                'Cluster_Naam': cluster.name if cluster else '',
                'Vertrouwen': advice.confidence if advice else '',
                'Advies': advice.advice_code if advice else '',
                'Reden': advice.reason if advice else '',
                'Artikel': advice.reference_article if advice else '',
                'Frequentie': cluster.frequency if cluster else 0,
                'Tekst': clause.raw_text,
            }
            
            # Add policy number if available
            if clause.source_policy_number:
                row['Polisnummer'] = clause.source_policy_number

            # Add original source columns per policy row (e.g., vervaldatum, product, etc.)
            if include_original_columns and original_df is not None and source_cols:
                orig_idx = self._extract_original_index(clause.id)
                if orig_idx is not None and orig_idx in original_df.index:
                    original_row = original_df.loc[orig_idx]
                    for col in source_cols:
                        try:
                            row[col] = original_row[col]
                        except Exception:
                            row[col] = ""
                else:
                    for col in source_cols:
                        row[col] = ""
            
            rows.append(row)
        
        df = pd.DataFrame(rows)

        # POST-PROCESSING: Group singleton clusters (freq=1) into "Uniek" meta-clusters
        df = self._group_unique_texts(df)

        # Sort by cluster ID for readability
        df = df.sort_values(by='Cluster_ID')

        logger.info(f"Created DataFrame with {len(df)} rows, {len(df.columns)} columns")
        return df

    def _extract_original_index(self, clause_id: str) -> Optional[int]:
        """
        Extract original DataFrame index from Clause ID.

        Supported formats:
        - "row_{idx}"
        - "{policy_number}_{idx}" (policy number may contain underscores; idx is last part)
        """
        if not clause_id:
            return None

        clause_id = str(clause_id)
        if clause_id.startswith('row_'):
            try:
                return int(clause_id.split('_')[1])
            except (ValueError, IndexError):
                return None

        if '_' in clause_id:
            try:
                parts = clause_id.rsplit('_', 1)
                if len(parts) == 2:
                    return int(parts[1])
            except (ValueError, IndexError):
                return None

        return None

    def _group_unique_texts(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Group singleton clusters (Frequentie=1) into "Uniek" meta-clusters.

        Strategy:
        - Clusters with freq >= 2: Keep as-is (real duplicates)
        - Clusters with freq == 1: Group by Advies + Vertrouwen

        Result:
        - Normal clusters: CL-0001, CL-0002, etc.
        - Unique clusters: UNIEK-VERWIJDEREN-Hoog, UNIEK-HANDMATIG CHECKEN-Midden, etc.

        Args:
            df: DataFrame with analysis results

        Returns:
            DataFrame with regrouped unique texts
        """
        if df.empty or 'Frequentie' not in df.columns:
            return df

        # Separate real clusters (freq >= 2) from singletons (freq == 1)
        real_clusters = df[df['Frequentie'] >= 2].copy()
        singletons = df[df['Frequentie'] == 1].copy()

        if singletons.empty:
            logger.info("No singleton clusters to regroup")
            return df

        logger.info(f"Regrouping {len(singletons)} singleton clusters into 'Uniek' meta-clusters")

        # Create unique cluster IDs based on Advies + Vertrouwen
        def create_unique_cluster_id(row):
            advies = row.get('Advies', 'ONBEKEND')
            vertrouwen = row.get('Vertrouwen', 'Onbekend')
            # Clean up advies for ID (remove emojis, special chars)
            advies_clean = advies.replace('✓', '').replace('⚠️', '').replace('🔍', '').strip()
            return f"UNIEK-{advies_clean}-{vertrouwen}"

        def create_unique_cluster_name(row):
            advies = row.get('Advies', 'Onbekend')
            vertrouwen = row.get('Vertrouwen', 'Onbekend')
            return f"Unieke teksten - {advies} ({vertrouwen})"

        # Apply grouping
        singletons['Cluster_ID'] = singletons.apply(create_unique_cluster_id, axis=1)
        singletons['Cluster_Naam'] = singletons.apply(create_unique_cluster_name, axis=1)

        # Update Frequentie to reflect group size (per unique cluster)
        unique_cluster_sizes = singletons['Cluster_ID'].value_counts().to_dict()
        singletons['Frequentie'] = singletons['Cluster_ID'].map(unique_cluster_sizes)

        # Combine back together
        result = pd.concat([real_clusters, singletons], ignore_index=True)

        # Log statistics
        unique_groups = singletons['Cluster_ID'].nunique()
        logger.info(f"Created {unique_groups} unique meta-clusters from {len(singletons)} singleton texts")
        logger.info(f"Final: {len(real_clusters)} real clusters + {unique_groups} unique groups = {len(real_clusters) + unique_groups} total cluster groups")

        return result

    def _detect_text_column(self, df: pd.DataFrame) -> Optional[str]:
        """
        Best-effort detection of the free-text column in the original DataFrame.

        1) Try common names (Tekst/Vrije Tekst/etc.)
        2) Fallback: pick the column with the highest median string length in a small sample.
        """
        if df is None or df.empty:
            return None

        # Common names (keep in sync with ingestion/preprocessing expectations)
        text_cols = ['Tekst', 'Vrije Tekst', 'Clausule', 'Text', 'Description']
        for col in text_cols:
            if col in df.columns:
                return col

        # Case-insensitive match
        lower_map = {c.lower(): c for c in df.columns}
        for col in text_cols:
            if col.lower() in lower_map:
                return lower_map[col.lower()]

        # Heuristic fallback (sample for performance)
        sample = df.head(200)
        best_col = None
        best_score = -1.0
        for col in df.columns:
            try:
                series = sample[col]
                # Prefer object-like columns; numeric columns won't win on length anyway
                med = series.astype(str).str.len().median()
                if pd.notna(med) and float(med) > best_score:
                    best_score = float(med)
                    best_col = col
            except Exception:
                continue

        return best_col
    
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
            # Split long texts (>800 characters) into separate sheet
            max_text_length = self.config.analysis_rules.max_text_length  # Default: 800

            # Identify long text rows (check if Reden mentions "te lang" or actual text length)
            long_text_mask = df['Tekst'].str.len() > max_text_length

            # Split into two DataFrames
            long_texts_df = df[long_text_mask].copy()
            normal_df = df[~long_text_mask].copy()

            # Write normal results to main sheet
            normal_df.to_excel(writer, sheet_name='Analyseresultaten', index=False)
            logger.info(f"Analyseresultaten sheet: {len(normal_df)} rows")

            # Write long texts to separate sheet (if any)
            if not long_texts_df.empty:
                long_texts_df.to_excel(writer, sheet_name='Lange teksten', index=False)
                logger.info(f"Lange teksten sheet: {len(long_texts_df)} rows (>{max_text_length} characters)")
            else:
                logger.info("No long texts to separate")

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

