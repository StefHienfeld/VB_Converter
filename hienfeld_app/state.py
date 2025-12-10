"""
Hienfeld VB Converter - Reflex State Management

This module contains the main application state, replacing the Streamlit controller.
Uses async event handlers for long-running operations to keep the UI responsive.
"""
import reflex as rx
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import base64
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hienfeld.config import load_config, AppConfig
from hienfeld.domain.clause import Clause
from hienfeld.domain.cluster import Cluster
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.domain.analysis import AnalysisAdvice
from hienfeld.services.ingestion_service import IngestionService
from hienfeld.services.preprocessing_service import PreprocessingService
from hienfeld.services.policy_parser_service import PolicyParserService
from hienfeld.services.multi_clause_service import MultiClauseDetectionService
from hienfeld.services.clustering_service import ClusteringService
from hienfeld.services.analysis_service import AnalysisService
from hienfeld.services.export_service import ExportService
from hienfeld.services.clause_library_service import ClauseLibraryService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService
from hienfeld.services.admin_check_service import AdminCheckService
from hienfeld.logging_config import setup_logging, get_logger

# Initialize logging
setup_logging()
logger = get_logger('reflex_state')


class UploadedFileInfo(BaseModel):
    """Model for uploaded file information."""
    name: str = ""
    size: int = 0
    content_base64: str = ""  # Store as base64 for serialization
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class AnalysisResultRow(BaseModel):
    """Model for a single analysis result row (for display)."""
    cluster_id: str = ""
    cluster_name: str = ""
    frequency: int = 0
    advice_code: str = ""
    confidence: str = ""
    reason: str = ""
    reference_article: str = ""
    original_text: str = ""
    row_type: str = "SINGLE"  # SINGLE, PARENT, CHILD
    parent_id: str = ""
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class StatisticsModel(BaseModel):
    """Model for analysis statistics."""
    total_rows: int = 0
    unique_clusters: int = 0
    reduction_percentage: int = 0
    multi_clause_count: int = 0
    analysis_mode: str = "with_conditions"
    advice_distribution: Dict[str, int] = {}
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


class HienfeldState(rx.State):
    """
    Main application state for Hienfeld VB Converter.
    
    Handles:
    - File uploads (policy file, conditions, clause library)
    - Analysis pipeline execution
    - Results display
    - Settings management
    """
    
    # ==========================================================================
    # SETTINGS STATE
    # ==========================================================================
    strictness: int = 90  # 80-100, stored as int for slider
    min_frequency: int = 20
    window_size: int = 100
    use_window_limit: bool = True
    enable_ai: bool = False
    use_conditions: bool = True
    
    # ==========================================================================
    # FILE UPLOAD STATE
    # ==========================================================================
    # Store file info as dicts for serialization
    policy_file_name: str = ""
    policy_file_size: int = 0
    policy_file_content: str = ""  # base64 encoded
    
    condition_file_names: List[str] = []
    condition_file_contents: List[str] = []  # base64 encoded
    
    clause_library_file_name: str = ""
    clause_library_file_content: str = ""  # base64 encoded
    
    # File upload status messages
    policy_file_status: str = ""
    conditions_status: str = ""
    clause_library_status: str = ""
    
    # Clause library stats
    clause_library_loaded: bool = False
    clause_library_total: int = 0
    
    # Extra instruction
    extra_instruction: str = ""
    
    # ==========================================================================
    # ANALYSIS STATE
    # ==========================================================================
    is_analyzing: bool = False
    analysis_progress: int = 0
    analysis_status: str = ""
    analysis_error: str = ""
    
    # Results stored as serializable dicts
    results_ready: bool = False
    stats_total_rows: int = 0
    stats_unique_clusters: int = 0
    stats_reduction_percentage: int = 0
    stats_multi_clause_count: int = 0
    stats_analysis_mode: str = "with_conditions"
    stats_advice_distribution: Dict[str, int] = {}
    
    # Results as list of dicts
    results_data: List[Dict[str, Any]] = []
    
    # Excel download
    excel_data_base64: str = ""
    
    # Help modal
    show_help: bool = False
    
    # Sidebar visibility
    sidebar_open: bool = False
    
    # ==========================================================================
    # COMPUTED PROPERTIES
    # ==========================================================================
    
    @rx.var
    def can_start_analysis(self) -> bool:
        """Check if analysis can be started."""
        return self.policy_file_name != "" and not self.is_analyzing
    
    @rx.var
    def strictness_display(self) -> str:
        """Display strictness as percentage."""
        return f"{self.strictness}%"
    
    @rx.var
    def has_conditions(self) -> bool:
        """Check if condition files are loaded."""
        return len(self.condition_file_names) > 0
    
    @rx.var
    def conditions_count(self) -> int:
        """Number of condition files."""
        return len(self.condition_file_names)
    
    @rx.var
    def has_policy_file(self) -> bool:
        """Check if policy file is loaded."""
        return self.policy_file_name != ""
    
    @rx.var
    def advice_distribution_items(self) -> List[Dict[str, Any]]:
        """Convert advice distribution to list for chart."""
        if not self.stats_advice_distribution:
            return []
        return [
            {"advice": k, "count": v}
            for k, v in sorted(
                self.stats_advice_distribution.items(),
                key=lambda x: -x[1]
            )
        ]
    
    @rx.var
    def display_results(self) -> List[Dict[str, Any]]:
        """Get first 10 results for display preview."""
        return self.results_data[:10] if self.results_data else []
    
    @rx.var
    def total_results_count(self) -> int:
        """Total number of results."""
        return len(self.results_data)
    
    # ==========================================================================
    # EVENT HANDLERS - SETTINGS
    # ==========================================================================
    
    def set_strictness(self, value: List[int]):
        """Update strictness setting."""
        if value:
            self.strictness = value[0]
    
    def set_min_frequency(self, value: str):
        """Update minimum frequency setting."""
        try:
            self.min_frequency = int(value)
        except ValueError:
            pass
    
    def set_window_size(self, value: str):
        """Update window size setting."""
        try:
            self.window_size = int(value)
        except ValueError:
            pass
    
    def toggle_window_limit(self, value: bool):
        """Toggle window size limit."""
        self.use_window_limit = value
    
    def toggle_ai(self, value: bool):
        """Toggle AI analysis."""
        self.enable_ai = value
    
    def toggle_conditions(self, value: bool):
        """Toggle use of conditions."""
        self.use_conditions = value
    
    def set_extra_instruction(self, value: str):
        """Update extra instruction."""
        self.extra_instruction = value
    
    def toggle_help(self):
        """Toggle help modal."""
        self.show_help = not self.show_help
    
    def close_help(self):
        """Close help modal."""
        self.show_help = False
    
    def toggle_sidebar(self):
        """Toggle sidebar visibility."""
        self.sidebar_open = not self.sidebar_open
    
    def close_sidebar(self):
        """Close sidebar."""
        self.sidebar_open = False
    
    # ==========================================================================
    # EVENT HANDLERS - FILE UPLOAD
    # ==========================================================================
    
    async def handle_policy_upload(self, files: List[rx.UploadFile]):
        """Handle policy file upload."""
        if not files:
            return
        
        file = files[0]
        upload_data = await file.read()
        
        self.policy_file_name = file.filename
        self.policy_file_size = len(upload_data)
        self.policy_file_content = base64.b64encode(upload_data).decode('utf-8')
        self.policy_file_status = f"✅ {file.filename} geladen ({len(upload_data):,} bytes)"
        
        # Reset results when new file is uploaded
        self.results_ready = False
        self.results_data = []
        self.excel_data_base64 = ""
        self.analysis_error = ""
    
    async def handle_conditions_upload(self, files: List[rx.UploadFile]):
        """Handle condition files upload."""
        if not files:
            return
        
        self.condition_file_names = []
        self.condition_file_contents = []
        
        for file in files:
            upload_data = await file.read()
            self.condition_file_names.append(file.filename)
            self.condition_file_contents.append(base64.b64encode(upload_data).decode('utf-8'))
        
        self.conditions_status = f"✅ {len(self.condition_file_names)} bestand(en) geladen"
    
    async def handle_clause_library_upload(self, files: List[rx.UploadFile]):
        """Handle clause library file upload."""
        if not files:
            return
        
        file = files[0]
        upload_data = await file.read()
        
        self.clause_library_file_name = file.filename
        self.clause_library_file_content = base64.b64encode(upload_data).decode('utf-8')
        self.clause_library_status = f"✅ {file.filename} geladen"
        
        # Load clause library immediately
        try:
            config = load_config()
            clause_service = ClauseLibraryService(config)
            count = clause_service.load_from_file(upload_data, file.filename)
            self.clause_library_loaded = True
            self.clause_library_total = count
        except Exception as e:
            self.clause_library_status = f"❌ Fout: {str(e)}"
            self.clause_library_loaded = False
    
    def clear_policy_file(self):
        """Clear the policy file."""
        self.policy_file_name = ""
        self.policy_file_size = 0
        self.policy_file_content = ""
        self.policy_file_status = ""
        self.results_ready = False
        self.results_data = []
    
    def clear_condition_files(self):
        """Clear condition files."""
        self.condition_file_names = []
        self.condition_file_contents = []
        self.conditions_status = ""
    
    def clear_clause_library(self):
        """Clear clause library."""
        self.clause_library_file_name = ""
        self.clause_library_file_content = ""
        self.clause_library_status = ""
        self.clause_library_loaded = False
        self.clause_library_total = 0
    
    # ==========================================================================
    # EVENT HANDLERS - ANALYSIS
    # ==========================================================================
    
    @rx.event
    async def run_analysis(self):
        """
        Run the complete analysis pipeline.
        
        Uses yield to update UI during long operations.
        """
        if self.policy_file_name == "":
            self.analysis_error = "Geen polisbestand geüpload"
            return
        
        self.is_analyzing = True
        self.analysis_progress = 0
        self.analysis_status = "Initialiseren..."
        self.analysis_error = ""
        self.results_ready = False
        yield  # Update UI
        
        try:
            # Initialize services
            config = load_config()
            
            # Update config with current settings
            strictness_float = self.strictness / 100.0
            min_freq = self.min_frequency
            win_size = self.window_size if self.use_window_limit else 999999
            use_cond = self.use_conditions
            
            config.clustering.similarity_threshold = strictness_float
            config.analysis_rules.frequency_standardize_threshold = min_freq
            config.clustering.leader_window_size = win_size
            
            # Create services
            similarity_service = RapidFuzzSimilarityService(threshold=strictness_float)
            ingestion = IngestionService(config)
            preprocessing = PreprocessingService(config)
            policy_parser = PolicyParserService(config)
            multi_clause = MultiClauseDetectionService(config)
            clustering = ClusteringService(config, similarity_service=similarity_service)
            admin_check = AdminCheckService(config=config, llm_client=None, enable_ai_checks=False)
            analysis = AnalysisService(config, admin_check_service=admin_check)
            export = ExportService(config)
            clause_library_service = ClauseLibraryService(config)
            
            # Step 1: Load policy file
            self.analysis_progress = 5
            self.analysis_status = "📄 Bestand inlezen..."
            yield
            
            policy_bytes = base64.b64decode(self.policy_file_content)
            df = ingestion.load_policy_file(policy_bytes, self.policy_file_name)
            text_col = ingestion.detect_text_column(df)
            policy_number_col = ingestion.detect_policy_number_column(df)
            
            # Step 2: Parse conditions (if enabled)
            policy_sections: List[PolicyDocumentSection] = []
            
            condition_files_data = list(zip(
                [base64.b64decode(c) for c in self.condition_file_contents],
                self.condition_file_names
            )) if self.condition_file_contents else []
            
            if use_cond and condition_files_data:
                self.analysis_progress = 10
                self.analysis_status = "📚 Voorwaarden verwerken..."
                yield
                
                for file_bytes, filename in condition_files_data:
                    try:
                        sections = policy_parser.parse_policy_file(file_bytes, filename)
                        policy_sections.extend(sections)
                    except Exception as e:
                        logger.warning(f"Failed to parse {filename}: {e}")
            else:
                self.analysis_progress = 10
                self.analysis_status = "📊 Modus: Interne analyse"
                yield
            
            # Step 3: Load clause library if available
            if self.clause_library_file_content:
                clause_bytes = base64.b64decode(self.clause_library_file_content)
                clause_library_service.load_from_file(clause_bytes, self.clause_library_file_name)
                analysis.set_clause_library_service(clause_library_service)
            
            # Step 4: Convert to clauses
            self.analysis_progress = 15
            self.analysis_status = "📄 Data voorbereiden..."
            yield
            
            clauses = preprocessing.dataframe_to_clauses(df, text_col, policy_number_col=policy_number_col)
            
            # Step 5: Multi-clause detection
            self.analysis_progress = 20
            self.analysis_status = "🔍 Multi-clausule detectie..."
            yield
            
            multi_clause.mark_multi_clauses(clauses)
            
            # Step 6: Clustering
            self.analysis_progress = 25
            self.analysis_status = "🔗 Slim clusteren..."
            yield
            
            clusters, clause_to_cluster = clustering.cluster_clauses(clauses)
            
            # Update clause cluster assignments
            for clause in clauses:
                clause.cluster_id = clause_to_cluster.get(clause.id)
            
            self.analysis_progress = 50
            self.analysis_status = "🧠 Analyseren..."
            yield
            
            # Step 7: Analysis
            sections_to_use = policy_sections if use_cond else []
            hierarchical_results = []
            advice_map: Dict[str, AnalysisAdvice] = {}
            
            total_clusters = len(clusters)
            for idx, cluster in enumerate(clusters):
                # Update progress periodically
                if idx % 10 == 0:
                    progress_pct = 50 + int((idx / max(total_clusters, 1)) * 40)
                    self.analysis_progress = progress_pct
                    self.analysis_status = f"🧠 Analyseren... ({idx}/{total_clusters})"
                    yield
                
                # Analyze cluster
                parent_advice = analysis.analyze_clusters(
                    [cluster],
                    sections_to_use,
                    progress_callback=None
                ).get(cluster.id)
                
                if not parent_advice:
                    from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
                    parent_advice = AnalysisAdvice(
                        cluster_id=cluster.id,
                        advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                        reason="Geen advies gegenereerd",
                        confidence=ConfidenceLevel.LAAG.value,
                        reference_article="-",
                        category="UNKNOWN",
                        cluster_name=cluster.name,
                        frequency=cluster.frequency
                    )
                
                # Check for multi-clause splitting
                leader_clause = cluster.leader_clause
                if multi_clause.is_multi_clause(leader_clause):
                    sub_segments = multi_clause.split_clause(cluster.original_text)
                    
                    # Only create hierarchical structure if we actually split into multiple segments
                    # AND the segments are different from the original
                    if len(sub_segments) > 1 and sub_segments[0] != cluster.original_text:
                        child_rows = []
                        advice_summary = {}  # Track advice codes for summary
                        
                        for seg_idx, segment in enumerate(sub_segments):
                            child_advice = analysis.analyze_text_segment(
                                text=segment,
                                segment_id=f"{cluster.id}.{seg_idx+1}",
                                cluster_name=cluster.name,
                                frequency=1,
                                policy_sections=sections_to_use
                            )
                            
                            # Track advice codes
                            code = child_advice.advice_code if child_advice else "ONBEKEND"
                            advice_summary[code] = advice_summary.get(code, 0) + 1
                            
                            child_rows.append({
                                'type': 'CHILD',
                                'id': f"{cluster.id}.{seg_idx+1}",
                                'parent_id': cluster.id,
                                'text': segment,  # Actual segment text, not full original
                                'advice': child_advice,
                                'cluster': None
                            })
                        
                        # Create summary of child advices
                        summary_parts = [f"{count}x {code}" for code, count in advice_summary.items()]
                        summary_str = ", ".join(summary_parts)
                        
                        parent_advice.advice_code = "⚠️ GESPLITST"
                        parent_advice.reason = f"Gesplitst in {len(sub_segments)} onderdelen: {summary_str}"
                        
                        hierarchical_results.append({
                            'type': 'PARENT',
                            'id': cluster.id,
                            'cluster': cluster,
                            'advice': parent_advice,
                            'children': child_rows
                        })
                        hierarchical_results.extend(child_rows)
                    else:
                        # Split failed or returned single segment - treat as SINGLE with note
                        if len(cluster.original_text) > 1000:
                            parent_advice.advice_code = "⚠️ SPLITSEN CONTROLEREN"
                            parent_advice.reason = f"Lange tekst ({len(cluster.original_text)} tekens) - automatisch splitsen niet mogelijk. {parent_advice.reason}"
                        
                        hierarchical_results.append({
                            'type': 'SINGLE',
                            'id': cluster.id,
                            'cluster': cluster,
                            'advice': parent_advice
                        })
                else:
                    hierarchical_results.append({
                        'type': 'SINGLE',
                        'id': cluster.id,
                        'cluster': cluster,
                        'advice': parent_advice
                    })
                
                advice_map[cluster.id] = parent_advice
            
            # Step 8: Generate statistics
            self.analysis_progress = 95
            self.analysis_status = "📊 Resultaten samenstellen..."
            yield
            
            stats = export.get_statistics_summary(clauses, clusters, advice_map)
            stats['analysis_mode'] = 'with_conditions' if (use_cond and policy_sections) else 'internal_only'
            
            # Step 9: Build results for display
            result_rows: List[Dict[str, Any]] = []
            for result in hierarchical_results:
                cluster = result.get('cluster')
                advice = result.get('advice')
                
                text_content = ""
                if cluster:
                    text_content = cluster.original_text[:500] + '...' if len(cluster.original_text) > 500 else cluster.original_text
                else:
                    text_content = result.get('text', '')[:500]
                
                row = {
                    "cluster_id": result.get('id', ''),
                    "cluster_name": cluster.name if cluster else '',
                    "frequency": cluster.frequency if cluster else 1,
                    "advice_code": advice.advice_code if advice else '',
                    "confidence": advice.confidence if advice else '',
                    "reason": advice.reason if advice else '',
                    "reference_article": advice.reference_article if advice else '',
                    "original_text": text_content,
                    "row_type": result.get('type', 'SINGLE'),
                    "parent_id": result.get('parent_id', '')
                }
                result_rows.append(row)
            
            # Step 10: Generate Excel
            results_df = export.build_results_dataframe(
                clauses, clusters, advice_map,
                include_original_columns=True,
                original_df=df,
                hierarchical_results=hierarchical_results
            )
            excel_bytes = export.to_excel_bytes(
                results_df,
                include_summary=True,
                clusters=clusters,
                advice_map=advice_map
            )
            
            # Update final state
            self.analysis_progress = 100
            self.analysis_status = "✅ Analyse voltooid!"
            self.results_ready = True
            self.results_data = result_rows
            self.stats_total_rows = stats.get('total_rows', 0)
            self.stats_unique_clusters = stats.get('unique_clusters', 0)
            self.stats_reduction_percentage = stats.get('reduction_percentage', 0)
            self.stats_multi_clause_count = stats.get('multi_clause_count', 0)
            self.stats_analysis_mode = stats.get('analysis_mode', 'with_conditions')
            self.stats_advice_distribution = stats.get('advice_distribution', {})
            self.excel_data_base64 = base64.b64encode(excel_bytes).decode('utf-8')
            self.is_analyzing = False
            yield
            
            logger.info(f"Analysis complete: {stats.get('unique_clusters', 0)} clusters")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            self.analysis_error = f"Fout tijdens analyse: {str(e)}"
            self.is_analyzing = False
            self.analysis_progress = 0
            self.analysis_status = ""
            yield
    
    def reset_analysis(self):
        """Reset the analysis state for a new run."""
        self.is_analyzing = False
        self.analysis_progress = 0
        self.analysis_status = ""
        self.analysis_error = ""
        self.results_ready = False
        self.results_data = []
        self.excel_data_base64 = ""
    
    def cancel_analysis(self):
        """Cancel the running analysis."""
        self.is_analyzing = False
        self.analysis_progress = 0
        self.analysis_status = ""
        self.analysis_error = "Analyse geannuleerd door gebruiker"
    
    def start_new_analysis(self):
        """Reset everything for a completely new analysis."""
        # Reset files
        self.policy_file_name = ""
        self.policy_file_size = 0
        self.policy_file_content = ""
        self.policy_file_status = ""
        self.condition_file_names = []
        self.condition_file_contents = []
        self.conditions_status = ""
        self.clause_library_file_name = ""
        self.clause_library_file_content = ""
        self.clause_library_status = ""
        self.clause_library_loaded = False
        self.clause_library_total = 0
        self.extra_instruction = ""
        # Reset analysis state
        self.is_analyzing = False
        self.analysis_progress = 0
        self.analysis_status = ""
        self.analysis_error = ""
        self.results_ready = False
        self.results_data = []
        self.excel_data_base64 = ""
        self.stats_total_rows = 0
        self.stats_unique_clusters = 0
        self.stats_reduction_percentage = 0
        self.stats_multi_clause_count = 0
        self.stats_advice_distribution = {}