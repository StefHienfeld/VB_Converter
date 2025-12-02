# hienfeld/ui/view.py
"""
Streamlit View component for Hienfeld VB Converter.
Handles all UI rendering and display logic.
"""
import streamlit as st
import pandas as pd
from typing import Optional, Tuple, List, Any


class HienfeldView:
    """
    View component handling all Streamlit UI rendering.
    
    Follows Hienfeld Design System with brand colors:
    - Deep Sea: #0A0466
    - Ultra Marine: #10069F
    - Light Blue: #7CC2FE
    """
    
    def __init__(self, config=None):
        """
        Initialize the view and configure Streamlit page.
        
        Args:
            config: Optional AppConfig for customization
        """
        self.config = config
        self._configure_page()
        self._apply_styles()
    
    def _configure_page(self):
        """Configure Streamlit page settings."""
        st.set_page_config(
            page_title="Hienfeld VB Converter",
            page_icon="🛡️",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def _apply_styles(self):
        """Inject Hienfeld Design System CSS."""
        st.markdown("""
            <style>
                /* Global Settings */
                .main {
                    background-color: #FFFFFF;
                    font-family: 'Graphik', 'Open Sans', 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
                    color: #333333;
                }
                
                /* Titles & Headers - Hienfeld Deep Sea */
                h1, h2, h3, h4, h5, h6, .stTitle {
                    color: #0A0466 !important;
                    font-family: 'Graphik', 'Open Sans', sans-serif;
                    font-weight: 700;
                }
                
                /* Custom Buttons - Hienfeld Ultra Marine */
                .stButton > button {
                    background-color: #10069F;
                    color: white;
                    border-radius: 0px;
                    border: none;
                    padding: 0.6rem 1.5rem;
                    font-family: 'Graphik', 'Open Sans', sans-serif;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    transition: all 0.3s ease;
                }
                
                .stButton > button:hover {
                    background-color: #7CC2FE;
                    color: #0A0466;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }

                /* File Uploader Styling */
                .stFileUploader {
                    border: 2px dashed #E0E0E0;
                    padding: 2rem;
                    background-color: #F5F5F5;
                    border-radius: 0px;
                }
                .stFileUploader:hover {
                    border-color: #7CC2FE;
                }

                /* Sidebar Styling */
                [data-testid="stSidebar"] {
                    background-color: #F5F5F5;
                }
                
                /* Alert/Info Boxes */
                .stAlert {
                    background-color: #F0F7FC;
                    border-left: 4px solid #10069F;
                    color: #0A0466;
                }
                
                /* Progress Bar Color */
                .stProgress > div > div > div > div {
                    background-color: #10069F;
                }
                
                /* Header Line */
                .header-line {
                    height: 4px;
                    background: linear-gradient(90deg, #0A0466 0%, #10069F 50%, #7CC2FE 100%);
                    margin-bottom: 2rem;
                }
                
                /* Card Styling */
                .hienfeld-card {
                    background-color: #F5F5F5;
                    padding: 1.5rem;
                    border-radius: 0px;
                    border: 1px solid #E0E0E0;
                    margin-bottom: 1rem;
                }
                
                /* Metric Cards */
                .metric-card {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    padding: 1rem;
                    text-align: center;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }
                .metric-value {
                    font-size: 1.8rem;
                    font-weight: 700;
                    color: #0A0466;
                }
                .metric-label {
                    font-size: 0.9rem;
                    color: #666;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                
                /* Advice badges */
                .advice-verwijderen {
                    background-color: #dc3545;
                    color: white;
                    padding: 0.2rem 0.5rem;
                    border-radius: 3px;
                }
                .advice-splitsen {
                    background-color: #ffc107;
                    color: #333;
                    padding: 0.2rem 0.5rem;
                    border-radius: 3px;
                }
                .advice-standaardiseren {
                    background-color: #17a2b8;
                    color: white;
                    padding: 0.2rem 0.5rem;
                    border-radius: 3px;
                }
            </style>
        """, unsafe_allow_html=True)
    
    def render_header(self, logo_path: Optional[str] = None):
        """
        Render the application header with logo and title.
        
        Args:
            logo_path: Optional path to logo image
        """
        col_logo, col_title = st.columns([1, 4])
        
        with col_logo:
            if logo_path:
                try:
                    st.image(logo_path, width=160)
                except:
                    st.markdown("### 🛡️")
            else:
                st.markdown("### 🛡️")
        
        with col_title:
            st.title("VB Converter")
            st.markdown("""
            **Automatisch vrije teksten analyseren en standaardiseren.**  
            """)
        
        st.markdown('<div class="header-line"></div>', unsafe_allow_html=True)
    
    def render_sidebar(self) -> dict:
        """
        Render the sidebar with settings.
        
        Returns:
            Dictionary with all settings
        """
        with st.sidebar:
            st.header("⚙️ Instellingen")
            st.markdown("Pas de gevoeligheid van het algoritme aan.")
            
            strictness = st.slider(
                "Cluster Nauwkeurigheid",
                min_value=80,
                max_value=100,
                value=90,
                help="Hoe streng moet de matching zijn? Hoger = minder, maar zuiverdere clusters."
            )
            
            min_freq = st.number_input(
                "Min. Frequentie voor Standaardisatie",
                value=20,
                min_value=1,
                help="Vanaf hoe vaak moet een tekst als 'standaard' worden gezien?"
            )
            
            st.markdown("---")
            
            # Window Size settings
            st.subheader("🔗 Clustering")
            
            use_window_limit = st.checkbox(
                "Gebruik Window Size limiet",
                value=True,
                help="Beperk het aantal clusters waartegen vergeleken wordt voor snelheid"
            )
            
            if use_window_limit:
                window_size = st.number_input(
                    "Window Size",
                    value=100,
                    min_value=10,
                    max_value=1000,
                    help="Tegen hoeveel clusters wordt vergeleken. Hoger = nauwkeuriger maar trager."
                )
            else:
                window_size = 0  # 0 = no limit
                st.info("📊 Geen limiet: vergelijkt tegen ALLE clusters (kan trager zijn bij grote bestanden)")
            
            st.markdown("---")
            
            # Advanced settings (collapsible)
            with st.expander("🔧 Geavanceerde Instellingen"):
                enable_ai = st.checkbox(
                    "AI Analyse (experimenteel)",
                    value=False,
                    help="Gebruik AI voor geavanceerde analyse (vereist configuratie)"
                )
            
            st.markdown("---")
            st.markdown("**Support**\n\nNeem bij vragen contact op met de systeembeheerder.")
            
            # Return all settings as dict
            return {
                'strictness': strictness / 100.0,
                'min_frequency': min_freq,
                'window_size': window_size,
                'use_window_limit': use_window_limit,
                'enable_ai': enable_ai
            }
    
    def render_policy_file_uploader(self) -> Optional[Any]:
        """
        Render the policy file upload widget.
        
        Returns:
            Uploaded file object or None
        """
        st.markdown('<div class="hienfeld-card">', unsafe_allow_html=True)
        st.subheader("📄 1. Data Input")
        
        uploaded_file = st.file_uploader(
            "Sleep Polisbestand (CSV/Excel)",
            type=['csv', 'xlsx', 'xls'],
            help="Upload een CSV of Excel bestand met vrije teksten"
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
        return uploaded_file
    
    def render_conditions_uploader(self) -> Tuple[bool, List[Any]]:
        """
        Render the conditions file upload widget with mode selection.
        
        Returns:
            Tuple of (use_conditions: bool, condition_files: List)
        """
        st.markdown('<div class="hienfeld-card">', unsafe_allow_html=True)
        st.subheader("📜 2. Voorwaarden & Clausules")
        
        # Mode selection
        use_conditions = st.checkbox(
            "🔍 Vergelijk met voorwaarden/clausules",
            value=True,
            help="Vink uit om alleen binnen het bestand te analyseren (zonder voorwaarden)"
        )
        
        conditions = []
        
        if use_conditions:
            st.markdown("""
            Upload de polisvoorwaarden en/of clausules.  
            De tool vergelijkt elke vrije tekst tegen deze documenten om te bepalen 
            of de tekst al gedekt is en verwijderd kan worden.
            """)
            
            conditions = st.file_uploader(
                "Sleep voorwaarden en/of clausules (PDF/DOCX/TXT)",
                type=['txt', 'pdf', 'docx'],
                accept_multiple_files=True,
                help="Upload polisvoorwaarden EN/OF clausulebladen. Meerdere bestanden mogelijk."
            )
            
            if not conditions:
                st.warning("⚠️ Upload voorwaarden om te bepalen welke teksten al gedekt zijn.")
            else:
                st.success(f"✅ {len(conditions)} bestand(en) geladen")
        else:
            st.info("""
            📊 **Modus: Alleen interne analyse**  
            
            De tool analyseert het bestand zonder vergelijking met voorwaarden.  
            Beschikbare analyses:
            - 🔗 **Clustering** van vergelijkbare teksten
            - 🛠️ **Standaardiseren** (vaak voorkomende teksten)
            - ⚠️ **Splitsen** (teksten met meerdere clausules)
            - 📊 **Frequentie-analyse** per cluster
            - 🔄 **Consistentie-check** (varianten van dezelfde tekst)
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
        return use_conditions, conditions or []
    
    def render_extra_instruction(self) -> str:
        """
        Render the extra instruction input.
        
        Returns:
            User-provided instruction text
        """
        st.markdown('<div class="hienfeld-card">', unsafe_allow_html=True)
        st.subheader("💬 3. Extra Instructies (Optioneel)")
        
        instruction = st.text_area(
            "Specifieke instructies voor de analyse:",
            height=100,
            placeholder="Bijv: 'Let extra op clausules over asbest'...",
            help="Voeg extra context toe voor de analyse"
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
        return instruction
    
    def render_start_button(self, disabled: bool = False) -> bool:
        """
        Render the start analysis button.
        
        Args:
            disabled: Whether button should be disabled
            
        Returns:
            True if button was clicked
        """
        return st.button(
            "🚀 Start Analyse",
            disabled=disabled,
            use_container_width=True
        )
    
    def render_welcome(self):
        """Render the welcome/instruction message."""
        st.markdown("""
        Deze tool helpt u om grote hoeveelheden vrije teksten te analyseren, 
        te clusteren en te toetsen aan de polisvoorwaarden.
        
        ## Hoe werkt het?
        
        ### 1. 📄 Polisbestand uploaden
        Sleep het Excel- of CSV-bestand met vrije teksten in het eerste vak.
        
        ### 2. 📜 Kies je analyse-modus
        
        **Optie A: Met voorwaarden** (aanbevolen)  
        Upload de polisvoorwaarden en/of clausulebladen.  
        De tool vergelijkt elke vrije tekst tegen deze documenten.
        
        **Optie B: Alleen interne analyse**  
        Analyseer alleen binnen het bestand, zonder voorwaarden.  
        Nuttig voor: frequentie-analyse, duplicaat-detectie, consistentie-checks.
        
        ### 3. 🚀 Start Analyse
        De tool clustert vergelijkbare teksten en geeft advies:
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Met voorwaarden:**
            - ✅ VERWIJDEREN (staat in voorwaarden)
            - ⚠️ SPLITSEN (meerdere clausules)
            - 🛠️ STANDAARDISEREN (vaak voorkomend)
            - 🔒 BEHOUDEN (afwijking)
            """)
        
        with col2:
            st.markdown("""
            **Zonder voorwaarden:**
            - 🛠️ STANDAARDISEREN (vaak voorkomend)
            - ⚠️ SPLITSEN (meerdere clausules)
            - 🔄 CONSISTENTIE CHECK (varianten)
            - 📊 FREQUENTIE INFO
            """)
        
        st.info("💡 **Tip:** Zorg dat uw invoerbestand een kolom heeft met de naam 'Tekst', 'Vrije Tekst' of 'Clausule'.")
    
    def init_progress(self) -> Tuple[Any, Any]:
        """
        Initialize progress display elements.
        
        Returns:
            Tuple of (progress_bar, status_text) Streamlit objects
        """
        st.subheader("📊 Analyse Voortgang")
        progress_bar = st.progress(0)
        status_text = st.empty()
        return progress_bar, status_text
    
    def update_progress(self, bar, status, progress: int, message: str):
        """
        Update progress display.
        
        Args:
            bar: Progress bar object
            status: Status text object
            progress: Progress percentage (0-100)
            message: Status message
        """
        bar.progress(progress)
        status.text(message)
    
    def complete_progress(self, bar, status):
        """
        Mark progress as complete.
        
        Args:
            bar: Progress bar object
            status: Status text object
        """
        bar.progress(100)
        status.success("✅ Analyse succesvol afgerond!")
    
    def render_metrics(self, stats: dict):
        """
        Render analysis metrics in cards.
        
        Adapts display based on analysis mode (with/without conditions).
        
        Args:
            stats: Dictionary with statistics
        """
        advice_dist = stats.get('advice_distribution', {})
        analysis_mode = stats.get('analysis_mode', 'with_conditions')
        
        # Count various advice types
        verwijderen_count = advice_dist.get('VERWIJDEREN', 0)
        standaardiseren_count = advice_dist.get('🛠️ STANDAARDISEREN', 0)
        uniek_count = advice_dist.get('✨ UNIEK', 0)
        
        if analysis_mode == 'with_conditions':
            # Mode WITH conditions - show verwijderen count
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{stats.get('total_rows', 0):,}</div>
                        <div class="metric-label">Polisregels</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{stats.get('unique_clusters', 0):,}</div>
                        <div class="metric-label">Unieke Clusters</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{stats.get('reduction_percentage', 0)}%</div>
                        <div class="metric-label">Reductie</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #28a745;">{verwijderen_count}</div>
                        <div class="metric-label">🗑️ Te Verwijderen</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col5:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #ffc107;">{stats.get('multi_clause_count', 0)}</div>
                        <div class="metric-label">⚠️ Te Splitsen</div>
                    </div>
                """, unsafe_allow_html=True)
        
        else:
            # Mode WITHOUT conditions - show different metrics
            st.info("📊 **Modus: Interne analyse** - Geen voorwaarden gebruikt")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{stats.get('total_rows', 0):,}</div>
                        <div class="metric-label">Polisregels</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{stats.get('unique_clusters', 0):,}</div>
                        <div class="metric-label">Unieke Clusters</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value">{stats.get('reduction_percentage', 0)}%</div>
                        <div class="metric-label">Reductie</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #17a2b8;">{standaardiseren_count}</div>
                        <div class="metric-label">🛠️ Standaardiseren</div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col5:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-value" style="color: #6c757d;">{uniek_count}</div>
                        <div class="metric-label">✨ Uniek</div>
                    </div>
                """, unsafe_allow_html=True)
    
    def render_advice_distribution(self, advice_counts: dict):
        """
        Render advice type distribution.
        
        Args:
            advice_counts: Dictionary of advice_code -> count
        """
        if not advice_counts:
            return
        
        st.subheader("📈 Advies Verdeling")
        
        # Create simple bar chart
        df = pd.DataFrame([
            {'Advies': k, 'Aantal': v}
            for k, v in sorted(advice_counts.items(), key=lambda x: -x[1])
        ])
        
        st.bar_chart(df.set_index('Advies'))
    
    def render_results_table(self, df: pd.DataFrame, max_rows: int = 100):
        """
        Render the results table.
        
        Args:
            df: Results DataFrame
            max_rows: Maximum rows to display
        """
        st.subheader("📋 Detailoverzicht")
        
        if len(df) > max_rows:
            st.warning(f"Tabel toont eerste {max_rows} van {len(df)} rijen. Download Excel voor volledige data.")
        
        st.dataframe(
            df.head(max_rows),
            use_container_width=True,
            hide_index=True
        )
    
    def render_download_button(
        self, 
        data: bytes, 
        filename: str = "Hienfeld_Analyse.xlsx"
    ):
        """
        Render the download button.
        
        Args:
            data: Excel file as bytes
            filename: Download filename
        """
        st.download_button(
            label="📥 Download Rapport (Excel)",
            data=data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    
    def render_error(self, message: str):
        """
        Display an error message.
        
        Args:
            message: Error message to display
        """
        st.error(f"❌ {message}")
    
    def render_warning(self, message: str):
        """
        Display a warning message.
        
        Args:
            message: Warning message to display
        """
        st.warning(f"⚠️ {message}")
    
    def render_info(self, message: str):
        """
        Display an info message.
        
        Args:
            message: Info message to display
        """
        st.info(f"ℹ️ {message}")
    
    def create_two_column_layout(self) -> Tuple[Any, Any]:
        """
        Create a two-column layout.
        
        Returns:
            Tuple of (left_column, right_column) Streamlit containers
        """
        return st.columns([1, 2], gap="large")

