# hienfeld/config.py
"""
Central configuration for Hienfeld VB Converter.
Uses dataclasses for type-safe configuration management.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os
import json


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
class AIConfig:
    """Configuration for AI/ML features (optional)."""
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
    ai: AIConfig = field(default_factory=AIConfig)
    
    # UI settings
    app_title: str = "Hienfeld VB Converter"
    app_version: str = "2.0.0"


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from file or return defaults.
    
    Args:
        config_path: Optional path to JSON config file
        
    Returns:
        AppConfig instance with loaded or default values
    """
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            # TODO: Implement proper deserialization from dict
            # For now, return defaults
            return AppConfig()
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            return AppConfig()
    
    return AppConfig()


def save_config(config: AppConfig, config_path: str) -> None:
    """
    Save configuration to JSON file.
    
    Args:
        config: AppConfig instance to save
        config_path: Path to save the config file
    """
    # TODO: Implement proper serialization
    pass

