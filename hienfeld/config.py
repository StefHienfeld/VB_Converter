# hienfeld/config.py
"""
Central configuration for Hienfeld VB Converter.
Uses dataclasses for type-safe configuration management.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os


@dataclass
class ClusteringConfig:
    """Configuration for the clustering algorithm."""
    min_text_length: int = 5
    similarity_threshold: float = 0.90
    leader_window_size: int = 100
    use_rapidfuzz: bool = True
    
    # Length-based filtering
    length_tolerance: float = 0.2  # 20% length difference allowed


@dataclass
class MultiClauseConfig:
    """Configuration for multi-clause detection."""
    max_text_length: int = 1000
    clause_code_pattern: str = r'\b[0-9][A-Z]{2}[0-9]\b'  # Matches 9NX3 format
    min_codes_for_split: int = 2


@dataclass
class ConditionsMatchConfig:
    """Configuration for matching against policy conditions."""
    # Thresholds for similarity matching
    exact_match_threshold: float = 0.95      # Bijna identiek -> VERWIJDEREN
    high_similarity_threshold: float = 0.85  # Zeer vergelijkbaar -> VERWIJDEREN met check
    medium_similarity_threshold: float = 0.75  # Vergelijkbaar -> HANDMATIG CHECKEN
    
    # Minimum text length for matching
    min_text_length: int = 20
    
    # Enable/disable different matching strategies
    enable_exact_substring: bool = True
    enable_fuzzy_section_match: bool = True
    enable_fragment_match: bool = True


@dataclass
class AnalysisRuleConfig:
    """Configuration for analysis rules and thresholds."""
    frequency_standardize_threshold: int = 20
    
    # Conditions matching config
    conditions_match: ConditionsMatchConfig = field(default_factory=ConditionsMatchConfig)
    
    # Keyword rules mapping keywords to categories
    # EXTENDED v2.1: More rules for common clause types
    keyword_rules: Dict[str, Dict] = field(default_factory=lambda: {
        'fraude': {
            'keywords': ['fraude', 'misleiding'],
            'max_length': 400,
            'advice': 'VERWIJDEREN',
            'reason': 'Fraude is al uitgesloten in voorwaarden (Art 2.8/3.3).',
            'article': 'Art 2.8',
            'confidence': 'Hoog'
        },
        'rangorde': {
            'keywords': ['rangorde', 'strijd'],
            'max_length': 300,
            'advice': 'VERWIJDEREN',
            'reason': 'Standaard Rangorde bepaling (Art 9.1). Let op: alleen verwijderen als de tekst leeg is van andere clausules.',
            'article': 'Art 9.1',
            'confidence': 'Hoog'
        },
        'molest': {
            'keywords': ['molest'],
            'inclusion_keywords': ['inclusief', 'meeverzekerd'],
            'advice': 'BEHOUDEN (CLAUSULE)',
            'reason': 'Afwijking: Voorwaarden sluiten Molest uit (Art 2.14), polis dekt het expliciet.',
            'article': 'Art 2.14',
            'confidence': 'Hoog'
        },
        # === NEW RULES v2.1 ===
        'evacuatie': {
            'keywords': ['evacuatie', 'noodgedwongen'],
            'inclusion_keywords': ['verblijf', 'bevoegd gezag'],
            'advice': 'HANDMATIG CHECKEN',
            'reason': 'Evacuatieclausule - controleer of dekking afwijkt van voorwaarden.',
            'article': '-',
            'confidence': 'Midden'
        },
        'uitsluiting_kunst': {
            'keywords': ['uitsluiting', 'uitgesloten'],
            'inclusion_keywords': ['kunstvoorwerpen', 'kunst', 'antiek', 'kunstobjecten'],
            'advice': 'BEHOUDEN (MAATWERK)',
            'reason': 'Specifieke uitsluiting van kunstobjecten - polisspecifiek maatwerk.',
            'article': '-',
            'confidence': 'Hoog'
        },
        'braak_clausule': {
            'keywords': ['braak'],
            'inclusion_keywords': ['diefstal', 'inbraak'],
            'advice': 'BEHOUDEN (CLAUSULE)',
            'reason': 'Braakclausule - specifieke voorwaarde voor diefstal. Controleer of consistent met voorwaarden.',
            'article': '-',
            'confidence': 'Midden'
        },
        'vervangende_woonruimte': {
            'keywords': ['vervangende woonruimte', 'verblijf elders'],
            'advice': 'HANDMATIG CHECKEN',
            'reason': 'Vervangende woonruimte clausule - vergelijk met Art 10 voorwaarden.',
            'article': 'Art 10',
            'confidence': 'Midden'
        },
        'juwelen_sieraden': {
            'keywords': ['juwelen', 'sieraden', 'horloges', 'lijfsieraden'],
            'inclusion_keywords': ['kluis', 'verzekerd', 'dekking'],
            'advice': 'BEHOUDEN (MAATWERK)',
            'reason': 'Specifieke juwelen/sieraden bepaling - vaak polisspecifiek maatwerk.',
            'article': '-',
            'confidence': 'Midden'
        },
        'alarm_beveiliging': {
            'keywords': ['alarm', 'inbraakalarm', 'beveiligingsysteem'],
            'inclusion_keywords': ['doormelding', 'pac', 'bewakingscentrale'],
            'advice': 'BEHOUDEN (VERPLICHTING)',
            'reason': 'Beveiligingsverplichting - controleer of eisen correct zijn vastgelegd.',
            'article': '-',
            'confidence': 'Midden'
        },
        'monumenten': {
            'keywords': ['monument', 'monumentenlijst', 'rijksmonument'],
            'advice': 'BEHOUDEN (MAATWERK)',
            'reason': 'Monumentenclausule - specifieke bepalingen voor monumentenpanden.',
            'article': '-',
            'confidence': 'Hoog'
        },
        'secundaire_dekking': {
            'keywords': ['secundaire dekking', 'secundaire verzekering', 'primaire verzekering'],
            'advice': 'BEHOUDEN (CLAUSULE)',
            'reason': 'Secundaire dekkingsclausule - regelt samenloop met andere verzekeringen.',
            'article': '-',
            'confidence': 'Hoog'
        },
        'buitenland': {
            'keywords': ['buitenland', 'woonachtig in het buitenland', 'land van vestiging'],
            'advice': 'BEHOUDEN (MAATWERK)',
            'reason': 'Buitenlandclausule - specifieke bepalingen voor verzekerden in het buitenland.',
            'article': '-',
            'confidence': 'Midden'
        },
        'verhuur': {
            'keywords': ['verhuur', 'verhuurd', 'huurder'],
            'advice': 'BEHOUDEN (MAATWERK)',
            'reason': 'Verhuurclausule - afwijkende voorwaarden bij verhuur. Controleer details.',
            'article': '-',
            'confidence': 'Midden'
        },
        'taxatie': {
            'keywords': ['taxatie', 'taxatierapport', 'getaxeerd'],
            'inclusion_keywords': ['7:960', 'herbouwwaarde', 'waarde'],
            'advice': 'HANDMATIG CHECKEN',
            'reason': 'Taxatieclausule - controleer of taxatie nog geldig is (max 3 jaar).',
            'article': 'Art 7:960 BW',
            'confidence': 'Midden'
        },
        'overdekking': {
            'keywords': ['overdekking', 'automatisch gedekt'],
            'advice': 'HANDMATIG CHECKEN',
            'reason': 'Overdekkingsclausule - controleer percentage en voorwaarden.',
            'article': '-',
            'confidence': 'Midden'
        },
        'sanctie_wetgeving': {
            'keywords': ['sanctie', 'sanctiewetgeving', 'sanctieland'],
            'advice': 'VERWIJDEREN',
            'reason': 'Standaard sanctiewetgeving - al opgenomen in voorwaarden (Art 7).',
            'article': 'Art 7',
            'confidence': 'Hoog'
        },
        'terrorisme': {
            'keywords': ['terrorisme', 'nht'],
            'advice': 'VERWIJDEREN',
            'reason': 'Standaard terrorismeclausule via NHT - zie Clausuleblad Terrorismedekking.',
            'article': 'Bijlage',
            'confidence': 'Hoog'
        },
        'annulering': {
            'keywords': ['annulering', 'annuleringskosten'],
            'inclusion_keywords': ['reis', 'doorlopend'],
            'advice': 'HANDMATIG CHECKEN',
            'reason': 'Annuleringsclausule - controleer of bedragen/voorwaarden afwijken.',
            'article': 'Art 9',
            'confidence': 'Midden'
        }
    })
    
    # Article mapping for reference
    article_mapping: Dict[str, str] = field(default_factory=lambda: {
        'fraude': 'Art 2.8',
        'molest': 'Art 2.14',
        'rangorde': 'Art 9.1',
        'terrorisme': 'Art 2.13'
    })


@dataclass
class ClusterNamingConfig:
    """Configuration for cluster naming heuristics."""
    theme_patterns: Dict[str, str] = field(default_factory=lambda: {
        'terrorisme': 'Terrorisme Clausule',
        'sanctie': 'Sanctiewetgeving',
        'brandregres': 'Brandregres',
        'molest': 'Molest Dekking',
        'verzekerde hoedanigheid': 'Doelgroepomschrijving',
        'eigen risico': 'Eigen Risico Bepaling',
        'buitenland': 'Buitenland Dekking',
        'premie': 'Premie Bepaling',  # Combined with naverrekening check
        'rangorde': 'Rangorde Bepaling'
    })
    
    fallback_word_count: int = 5  # Number of words for fallback name


@dataclass
class IngestionConfig:
    """Configuration for file ingestion."""
    preferred_text_columns: List[str] = field(default_factory=lambda: [
        'Tekst', 'Vrije Tekst', 'Clausule', 'Text', 'Description'
    ])
    
    csv_delimiters: List[str] = field(default_factory=lambda: [';', ',', '\t'])
    default_encoding: str = 'utf-8'
    fallback_encoding: str = 'latin1'


@dataclass
class ExportConfig:
    """Configuration for export settings."""
    output_columns: List[str] = field(default_factory=lambda: [
        'Cluster_ID', 'Cluster_Naam', 'Frequentie', 
        'Advies', 'Vertrouwen', 'Reden', 'Artikel'
    ])
    
    excel_sheet_name: str = "Hienfeld Analyse"
    default_filename: str = "Hienfeld_Analyse.xlsx"


@dataclass
class SemanticConfig:
    """Configuration for semantic analysis (no external APIs required)."""
    # Master switch for semantic features
    enabled: bool = True
    
    # Sentence embeddings (sentence-transformers)
    # Enabled; skips gracefully if model not cached locally (avoids 5-10min first download).
    # Pre-download once with: python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
    # Or use a smaller/faster model like "all-MiniLM-L6-v2" (90MB, English-optimized but works for Dutch too)
    enable_embeddings: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"  # Fast & small (90MB); or "paraphrase-multilingual-MiniLM-L12-v2" for better Dutch (470MB)
    
    # SpaCy NLP (lemmatization, NER)
    enable_nlp: bool = True
    spacy_model: str = "nl_core_news_md"  # Dutch medium model
    
    # TF-IDF document similarity
    enable_tfidf: bool = True
    
    # Synonym expansion
    enable_synonyms: bool = True
    
    # Hybrid similarity weights
    weight_rapidfuzz: float = 0.25
    weight_lemmatized: float = 0.20
    weight_tfidf: float = 0.15
    weight_synonyms: float = 0.15
    weight_embeddings: float = 0.25
    
    # Thresholds
    semantic_match_threshold: float = 0.70
    semantic_high_threshold: float = 0.80


@dataclass
class AIConfig:
    """Configuration for AI/ML features (optional - requires API keys)."""
    enabled: bool = False
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    vector_store_type: str = "faiss"
    similarity_top_k: int = 3
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None


@dataclass
class AppConfig:
    """Main application configuration combining all sub-configs."""
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    multi_clause: MultiClauseConfig = field(default_factory=MultiClauseConfig)
    analysis_rules: AnalysisRuleConfig = field(default_factory=AnalysisRuleConfig)
    cluster_naming: ClusterNamingConfig = field(default_factory=ClusterNamingConfig)
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    
    # UI settings
    app_title: str = "Hienfeld VB Converter"
    app_version: str = "3.0.0"  # Semantic enhancement


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from file or return defaults.
    
    Args:
        config_path: Optional path to JSON config file
        
    Returns:
        AppConfig instance with loaded or default values
    """
    return AppConfig()
