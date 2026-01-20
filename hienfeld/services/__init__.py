# Services module for Hienfeld VB Converter
from .ingestion_service import IngestionService
from .preprocessing_service import PreprocessingService
from .policy_parser_service import PolicyParserService
from .clustering_service import ClusteringService
from .similarity_service import SimilarityService, RapidFuzzSimilarityService
from .analysis_service import AnalysisService
from .export_service import ExportService
from .clause_library_service import ClauseLibraryService
from .admin_check_service import AdminCheckService

# Semantic enhancement services (v3.0)
from .nlp_service import NLPService
from .synonym_service import SynonymService
from .document_similarity_service import DocumentSimilarityService
from .hybrid_similarity_service import HybridSimilarityService

# Service interfaces (v4.3 - MVC refactoring)
from .interfaces import (
    ISimilarityService,
    IBatchSimilarityService,
    ISemanticSimilarityService,
    IAnalysisStrategy,
    AnalysisContext,
)

__all__ = [
    'IngestionService',
    'PreprocessingService',
    'PolicyParserService',
    'ClusteringService',
    'SimilarityService',
    'RapidFuzzSimilarityService',
    'AnalysisService',
    'ExportService',
    'ClauseLibraryService',
    'AdminCheckService',
    # Semantic enhancement services
    'NLPService',
    'SynonymService',
    'DocumentSimilarityService',
    'HybridSimilarityService',
    # Service interfaces
    'ISimilarityService',
    'IBatchSimilarityService',
    'ISemanticSimilarityService',
    'IAnalysisStrategy',
    'AnalysisContext',
]

