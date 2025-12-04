"""
Hienfeld VB Converter - Streamlit Application Entry Point

This is the main entry point for the Streamlit application.
It acts as a thin wiring layer, connecting the View to the Controller.

Architecture:
    - View (HienfeldView): Handles all UI rendering
    - Controller (HienfeldController): Orchestrates services
    - Services: Business logic (ingestion, clustering, analysis, export)
    - Domain: Core entities (Clause, Cluster, AnalysisAdvice)

Usage:
    streamlit run app.py
"""
import streamlit as st

from hienfeld.config import load_config, AppConfig
from hienfeld.ui.view import HienfeldView
from hienfeld.ui.controller import create_controller, HienfeldController
from hienfeld.logging_config import setup_logging

# Initialize logging
setup_logging()


def main():
    """Main application entry point."""
    # Load configuration
    config = load_config()
    
    # Initialize View
    view = HienfeldView(config)
    
    # Initialize Controller (cached in session state for persistence)
    if 'controller' not in st.session_state:
        st.session_state.controller = create_controller(config)
    
    controller: HienfeldController = st.session_state.controller
    
    # Render header
    view.render_header(logo_path="hienfeld-logo.png")
    
    # Render sidebar and get settings (now returns dict)
    settings = view.render_sidebar()
    
    # Create two-column layout
    col_input, col_results = view.create_two_column_layout()
    
    # Left column: Inputs
    with col_input:
        uploaded_file = view.render_policy_file_uploader()
        use_conditions, uploaded_conditions = view.render_conditions_uploader()
        
        # Clause library upload (for sanering/standardization)
        uploaded_clause_library = view.render_clause_library_uploader()
        
        # Load clause library if provided
        if uploaded_clause_library:
            if 'clause_library_loaded' not in st.session_state or st.session_state.clause_library_file != uploaded_clause_library.name:
                try:
                    num_clauses = controller.load_clause_library(
                        uploaded_clause_library.getvalue(),
                        uploaded_clause_library.name
                    )
                    st.session_state.clause_library_loaded = True
                    st.session_state.clause_library_file = uploaded_clause_library.name
                except Exception as e:
                    view.render_error(f"Fout bij laden clausulebibliotheek: {str(e)}")
            
            # Show clause library stats
            if st.session_state.get('clause_library_loaded'):
                view.render_clause_library_stats(controller.get_clause_library_stats())
        
        extra_instruction = view.render_extra_instruction()
        
        # Start button
        start_disabled = uploaded_file is None
        start_clicked = view.render_start_button(disabled=start_disabled)
    
    # Right column: Results or Welcome
    with col_results:
        if start_clicked and uploaded_file is not None:
            run_analysis(
                controller, 
                view, 
                uploaded_file, 
                use_conditions,
                uploaded_conditions, 
                settings
            )
        elif 'results_ready' in st.session_state and st.session_state.results_ready:
            # Show previous results
            display_results(controller, view)
        else:
            view.render_welcome()


def run_analysis(
    controller: HienfeldController,
    view: HienfeldView,
    uploaded_file,
    use_conditions: bool,
    uploaded_conditions,
    settings: dict
):
    """
    Execute the analysis pipeline.
    
    Args:
        controller: Application controller
        view: View for UI updates
        uploaded_file: Uploaded policy file
        use_conditions: Whether to use condition files for comparison
        uploaded_conditions: List of uploaded condition files
        settings: Dictionary with all settings from sidebar
    """
    # Initialize progress display
    progress_bar, status_text = view.init_progress()
    
    def update_progress(progress: int, message: str):
        """Progress callback for pipeline."""
        view.update_progress(progress_bar, status_text, progress, message)
    
    try:
        # Step 1: Load policy data
        update_progress(5, "📄 Bestand inlezen...")
        controller.load_policy_dataframe(
            uploaded_file.getvalue(),
            uploaded_file.name
        )
        
        # Step 2: Parse condition files (only if enabled and files provided)
        if use_conditions and uploaded_conditions:
            update_progress(10, "📚 Voorwaarden verwerken...")
            condition_files = [
                (f.getvalue(), f.name) for f in uploaded_conditions
            ]
            controller.parse_policy_conditions(condition_files)
        else:
            # Clear any previous conditions
            controller.policy_sections = []
            if not use_conditions:
                update_progress(10, "📊 Modus: Interne analyse (zonder voorwaarden)")
        
        # Step 3: Run analysis with all settings
        stats = controller.run_analysis(
            strictness=settings['strictness'],
            min_frequency=settings['min_frequency'],
            window_size=settings['window_size'],
            use_conditions=use_conditions,
            progress_callback=update_progress
        )
        
        # Mark analysis complete
        view.complete_progress(progress_bar, status_text)
        st.session_state.results_ready = True
        
        # Display results
        display_results(controller, view, stats)
        
    except Exception as e:
        view.render_error(f"Fout tijdens analyse: {str(e)}")
        import traceback
        traceback.print_exc()


def display_results(
    controller: HienfeldController,
    view: HienfeldView,
    stats: dict = None
):
    """
    Display analysis results.
    
    Args:
        controller: Application controller with results
        view: View for rendering
        stats: Optional pre-computed statistics
    """
    # Get statistics if not provided
    if stats is None:
        stats = controller.get_statistics()
    
    # Display metrics
    view.render_metrics(stats)
    
    # Display advice distribution
    if 'advice_distribution' in stats:
        view.render_advice_distribution(stats['advice_distribution'])
    
    # Display results table
    results_df = controller.get_results_dataframe()
    if not results_df.empty:
        view.render_results_table(results_df)
        
        # Download button
        excel_data = controller.get_excel_bytes(include_summary=True)
        view.render_download_button(excel_data)


if __name__ == "__main__":
    main()
