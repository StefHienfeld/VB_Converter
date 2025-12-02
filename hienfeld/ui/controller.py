# hienfeld/ui/controller.py
"""
Controller component for Hienfeld VB Converter.
Orchestrates the Model (services) and View.
"""
from typing import List, Optional, Dict, Tuple, Callable
import pandas as pd

from ..config import AppConfig
from ..domain.clause import Clause
from ..domain.cluster import Cluster
from ..domain.policy_document import PolicyDocumentSection
from ..domain.analysis import AnalysisAdvice
from ..services.ingestion_service import IngestionService
from ..services.preprocessing_service import PreprocessingService
from ..services.policy_parser_service import PolicyParserService
from ..services.multi_clause_service import MultiClauseDetectionService
from ..services.clustering_service import ClusteringService
from ..services.analysis_service import AnalysisService
from ..services.export_service import ExportService
from ..services.similarity_service import RapidFuzzSimilarityService
from ..logging_config import get_logger

logger = get_logger('controller')


class HienfeldController:
    """
    Controller orchestrating the analysis pipeline.
    
    Responsibilities:
    - Coordinate services for the analysis workflow
    - Manage application state
    - Handle user actions from the view
    """
    
    def __init__(
        self,
        config: AppConfig,
        ingestion_service: Optional[IngestionService] = None,
        preprocessing_service: Optional[PreprocessingService] = None,
        policy_parser_service: Optional[PolicyParserService] = None,
        multi_clause_service: Optional[MultiClauseDetectionService] = None,
        clustering_service: Optional[ClusteringService] = None,
        analysis_service: Optional[AnalysisService] = None,
        export_service: Optional[ExportService] = None,
    ):
        """
        Initialize controller with services.
        
        Services are created with defaults if not provided.
        
        Args:
            config: Application configuration
            ingestion_service: Service for loading files
            preprocessing_service: Service for text preprocessing
            policy_parser_service: Service for parsing policy documents
            multi_clause_service: Service for multi-clause detection
            clustering_service: Service for clustering
            analysis_service: Service for analysis
            export_service: Service for export
        """
        self.config = config
        
        # Initialize services (with defaults)
        self.ingestion_service = ingestion_service or IngestionService(config)
        self.preprocessing_service = preprocessing_service or PreprocessingService(config)
        self.policy_parser_service = policy_parser_service or PolicyParserService(config)
        self.multi_clause_service = multi_clause_service or MultiClauseDetectionService(config)
        self.clustering_service = clustering_service or ClusteringService(config)
        self.analysis_service = analysis_service or AnalysisService(config)
        self.export_service = export_service or ExportService(config)
        
        # State
        self.df: Optional[pd.DataFrame] = None
        self.clauses: List[Clause] = []
        self.clusters: List[Cluster] = []
        self.advice_map: Dict[str, AnalysisAdvice] = {}
        self.policy_sections: List[PolicyDocumentSection] = []
        self._text_col: Optional[str] = None
    
    def load_policy_dataframe(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        """
        Load a policy file into a DataFrame.
        
        Args:
            file_bytes: Raw bytes of the file
            filename: Original filename
            
        Returns:
            Loaded DataFrame
        """
        logger.info(f"Loading policy file: {filename}")
        self.df = self.ingestion_service.load_policy_file(file_bytes, filename)
        self._text_col = self.ingestion_service.detect_text_column(self.df)
        return self.df
    
    def get_text_column(self) -> Optional[str]:
        """Get the detected text column name."""
        return self._text_col
    
    def parse_policy_conditions(
        self, 
        files: List[Tuple[bytes, str]]
    ) -> List[PolicyDocumentSection]:
        """
        Parse policy condition files.
        
        Args:
            files: List of (file_bytes, filename) tuples
            
        Returns:
            List of parsed policy sections
        """
        logger.info(f"Parsing {len(files)} condition files")
        
        sections = []
        for file_bytes, filename in files:
            try:
                file_sections = self.policy_parser_service.parse_policy_file(
                    file_bytes, filename
                )
                sections.extend(file_sections)
            except Exception as e:
                logger.warning(f"Failed to parse {filename}: {e}")
        
        self.policy_sections = sections
        logger.info(f"Parsed {len(sections)} total sections")
        return sections
    
    def run_analysis(
        self,
        strictness: float = 0.9,
        min_frequency: int = 20,
        window_size: int = 100,
        use_conditions: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, any]:
        """
        Run the complete analysis pipeline.
        
        Args:
            strictness: Clustering similarity threshold (0-1)
            min_frequency: Minimum frequency for standardization
            window_size: Cluster window size (0 = no limit)
            use_conditions: Whether to compare against policy conditions
            progress_callback: Optional callback(progress, message)
            
        Returns:
            Dictionary with analysis results
        """
        if self.df is None:
            raise ValueError("No data loaded. Call load_policy_dataframe first.")
        
        logger.info(f"Starting analysis (strictness={strictness}, min_freq={min_frequency}, window={window_size}, use_conditions={use_conditions})")
        
        # Update config
        self.config.clustering.similarity_threshold = strictness
        self.config.analysis_rules.frequency_standardize_threshold = min_frequency
        self.config.clustering.leader_window_size = window_size if window_size > 0 else 999999  # 0 = no limit
        
        # Step 1: Convert DataFrame to Clauses
        if progress_callback:
            progress_callback(5, "📄 Data voorbereiden...")
        
        self.clauses = self.preprocessing_service.dataframe_to_clauses(
            self.df,
            self._text_col,
            policy_number_col=self.ingestion_service.detect_policy_number_column(self.df)
        )
        
        # Step 2: Mark multi-clause texts
        if progress_callback:
            progress_callback(10, "🔍 Multi-clausule detectie...")
        
        self.multi_clause_service.mark_multi_clauses(self.clauses)
        
        # Step 3: Clustering
        if progress_callback:
            if window_size == 0:
                progress_callback(15, "🔗 Slim clusteren (geen window limiet)...")
            else:
                progress_callback(15, f"🔗 Slim clusteren (window={window_size})...")
        
        # Create progress wrapper for clustering
        def cluster_progress(p):
            if progress_callback:
                # Map 0-100 to 15-50
                adjusted = 15 + int(p * 0.35)
                progress_callback(adjusted, f"🔗 Clusteren... ({p}%)")
        
        # Update similarity service threshold
        self.clustering_service.update_similarity_threshold(strictness)
        
        self.clusters, clause_to_cluster = self.clustering_service.cluster_clauses(
            self.clauses,
            progress_callback=cluster_progress
        )
        
        # Update clause cluster assignments
        for clause in self.clauses:
            clause.cluster_id = clause_to_cluster.get(clause.id)
        
        # Step 4: Analysis
        if progress_callback:
            if use_conditions and self.policy_sections:
                progress_callback(55, "🧠 Analyse met voorwaarden...")
            else:
                progress_callback(55, "🧠 Interne analyse (zonder voorwaarden)...")
        
        def analysis_progress(p):
            if progress_callback:
                # Map 0-100 to 55-95
                adjusted = 55 + int(p * 0.40)
                progress_callback(adjusted, f"🧠 Analyseren... ({p}%)")
        
        # Pass policy sections only if use_conditions is True
        sections_to_use = self.policy_sections if use_conditions else []
        
        self.advice_map = self.analysis_service.analyze_clusters(
            self.clusters,
            sections_to_use,
            progress_callback=analysis_progress
        )
        
        # Step 5: Generate statistics
        if progress_callback:
            progress_callback(98, "📊 Resultaten samenstellen...")
        
        stats = self.export_service.get_statistics_summary(
            self.clauses, self.clusters, self.advice_map
        )
        
        # Add mode info to stats
        stats['analysis_mode'] = 'with_conditions' if (use_conditions and self.policy_sections) else 'internal_only'
        
        if progress_callback:
            progress_callback(100, "✅ Analyse voltooid!")
        
        logger.info(f"Analysis complete: {stats['unique_clusters']} clusters from {stats['total_rows']} rows")
        
        return stats
    
    def get_results_dataframe(self) -> pd.DataFrame:
        """
        Get analysis results as DataFrame.
        
        Returns:
            DataFrame with all results
        """
        if not self.clauses:
            return pd.DataFrame()
        
        df = self.export_service.build_results_dataframe(
            self.clauses,
            self.clusters,
            self.advice_map
        )
        
        # Format columns
        return self.export_service.format_column_selection(df, self._text_col or 'Tekst')
    
    def get_cluster_summary_dataframe(self) -> pd.DataFrame:
        """
        Get cluster summary as DataFrame.
        
        Returns:
            Summary DataFrame with one row per cluster
        """
        return self.export_service.build_cluster_summary(
            self.clusters,
            self.advice_map
        )
    
    def get_excel_bytes(self, include_summary: bool = True) -> bytes:
        """
        Generate Excel file with results.
        
        Args:
            include_summary: Whether to include summary sheet
            
        Returns:
            Excel file as bytes
        """
        df = self.get_results_dataframe()
        
        return self.export_service.to_excel_bytes(
            df,
            include_summary=include_summary,
            clusters=self.clusters,
            advice_map=self.advice_map
        )
    
    def get_statistics(self) -> dict:
        """
        Get current analysis statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.export_service.get_statistics_summary(
            self.clauses, self.clusters, self.advice_map
        )
    
    def reset(self):
        """Reset controller state for new analysis."""
        self.df = None
        self.clauses = []
        self.clusters = []
        self.advice_map = {}
        self.policy_sections = []
        self._text_col = None
        logger.info("Controller state reset")


def create_controller(config: Optional[AppConfig] = None) -> HienfeldController:
    """
    Factory function to create a fully configured controller.
    
    Args:
        config: Optional configuration (uses defaults if not provided)
        
    Returns:
        Configured HienfeldController instance
    """
    from ..config import load_config
    
    if config is None:
        config = load_config()
    
    # Create similarity service
    similarity_service = RapidFuzzSimilarityService(
        threshold=config.clustering.similarity_threshold
    )
    
    # Create all services
    ingestion = IngestionService(config)
    preprocessing = PreprocessingService(config)
    policy_parser = PolicyParserService(config)
    multi_clause = MultiClauseDetectionService(config)
    clustering = ClusteringService(config, similarity_service=similarity_service)
    analysis = AnalysisService(config)
    export = ExportService(config)
    
    return HienfeldController(
        config=config,
        ingestion_service=ingestion,
        preprocessing_service=preprocessing,
        policy_parser_service=policy_parser,
        multi_clause_service=multi_clause,
        clustering_service=clustering,
        analysis_service=analysis,
        export_service=export
    )

