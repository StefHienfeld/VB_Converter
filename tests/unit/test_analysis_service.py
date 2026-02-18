"""
Unit tests for AnalysisService.

Tests the 5-step waterfall analysis pipeline:
- Step 0: Admin check (hygiene issues)
- Step 0.5: Custom instructions check
- Step 1: Clause library check
- Step 2: Policy conditions check
- Step 3: Fallback analysis

Note: Uses mocks for heavy dependencies (NLP, embeddings).
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from typing import List

from hienfeld.config import load_config
from hienfeld.services.analysis_service import AnalysisService
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.domain.cluster import Cluster
from hienfeld.domain.clause import Clause
from hienfeld.domain.policy_document import PolicyDocumentSection


# ============================================================
# Helper Functions
# ============================================================

def create_clause(text: str, clause_id: str = None) -> Clause:
    """Create a test Clause."""
    return Clause(
        id=clause_id or f"clause_{hash(text) % 10000}",
        raw_text=text,
        simplified_text=text.lower().strip(),
        source_file_name="test.xlsx"
    )


def create_cluster(text: str, cluster_id: str = None, frequency: int = 1, name: str = "") -> Cluster:
    """Create a test Cluster."""
    clause = create_clause(text, f"clause_{cluster_id or 'test'}")
    return Cluster(
        id=cluster_id or f"CL-{hash(text) % 10000:04d}",
        leader_clause=clause,
        member_ids=[],
        frequency=frequency,
        name=name or "Test Cluster"
    )


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def analysis_service(config):
    """Create an AnalysisService with default config."""
    return AnalysisService(config)


@pytest.fixture
def analysis_service_with_mocks(config, mock_similarity_service, mock_hybrid_similarity_service):
    """Create an AnalysisService with mocked dependencies."""
    service = AnalysisService(
        config,
        similarity_service=mock_similarity_service,
        hybrid_similarity_service=mock_hybrid_similarity_service
    )
    return service


# ============================================================
# Tests for AnalysisService Initialization
# ============================================================

class TestAnalysisServiceInit:
    """Tests for AnalysisService initialization."""

    def test_init_with_default_config(self, config):
        """Should initialize with default config."""
        service = AnalysisService(config)

        assert service.config is config
        assert service.similarity_service is not None
        assert service._hybrid_enabled is False  # No hybrid service provided

    def test_init_with_hybrid_service(self, config, mock_hybrid_similarity_service):
        """Should enable hybrid mode when service is provided."""
        service = AnalysisService(
            config,
            hybrid_similarity_service=mock_hybrid_similarity_service
        )

        assert service._hybrid_enabled is True
        assert service.hybrid_similarity_service is mock_hybrid_similarity_service

    def test_init_with_clause_library(self, config, mock_clause_library_service):
        """Should accept clause library service."""
        service = AnalysisService(
            config,
            clause_library_service=mock_clause_library_service
        )

        assert service.clause_library_service is mock_clause_library_service


# ============================================================
# Tests for Threshold Configuration
# ============================================================

class TestAnalysisServiceThresholds:
    """Tests for similarity threshold configuration."""

    def test_default_thresholds(self, analysis_service):
        """Should have correct default thresholds."""
        assert analysis_service.EXACT_MATCH_THRESHOLD == 0.95
        assert analysis_service.HIGH_SIMILARITY_THRESHOLD == 0.85
        assert analysis_service.MEDIUM_SIMILARITY_THRESHOLD == 0.75

    def test_set_similarity_thresholds(self, analysis_service):
        """Should allow updating thresholds."""
        analysis_service.set_similarity_thresholds(
            exact=0.98,
            high=0.90,
            medium=0.80
        )

        assert analysis_service.EXACT_MATCH_THRESHOLD == 0.98
        assert analysis_service.HIGH_SIMILARITY_THRESHOLD == 0.90
        assert analysis_service.MEDIUM_SIMILARITY_THRESHOLD == 0.80

    def test_set_semantic_thresholds(self, analysis_service):
        """Should allow updating semantic thresholds."""
        analysis_service.set_semantic_thresholds(
            match_threshold=0.75,
            high_threshold=0.85
        )

        assert analysis_service.SEMANTIC_MATCH_THRESHOLD == 0.75
        assert analysis_service.SEMANTIC_HIGH_THRESHOLD == 0.85


# ============================================================
# Tests for Short Text Handling
# ============================================================

class TestAnalysisServiceShortText:
    """Tests for short text handling."""

    def test_very_short_text_returns_manual_check(self, analysis_service):
        """Very short texts should require manual check."""
        cluster = create_cluster("ABC", frequency=1)

        stats = {'step0_admin_issues': 0, 'step05_custom_instructions': 0,
                 'step1_library_match': 0, 'step2_conditions_match': 0,
                 'step3_fallback': 0, 'multi_clause': 0}

        advice = analysis_service._analyze_with_waterfall(cluster, stats)

        assert advice.advice_code == AdviceCode.HANDMATIG_CHECKEN.value
        assert "te kort" in advice.reason.lower()


# ============================================================
# Tests for Long Text Handling
# ============================================================

class TestAnalysisServiceLongText:
    """Tests for long text (brei) handling."""

    def test_very_long_text_returns_manual_check(self, analysis_service, long_text):
        """Very long texts should require manual check."""
        cluster = create_cluster(long_text, frequency=1)

        stats = {'step0_admin_issues': 0, 'step05_custom_instructions': 0,
                 'step1_library_match': 0, 'step2_conditions_match': 0,
                 'step3_fallback': 0, 'multi_clause': 0}

        advice = analysis_service._analyze_with_waterfall(cluster, stats)

        assert advice.advice_code == AdviceCode.HANDMATIG_CHECKEN.value
        assert "te lang" in advice.reason.lower()
        assert advice.category == "LONG_TEXT"


# ============================================================
# Tests for Keyword Rules (Step 3)
# ============================================================

class TestAnalysisServiceKeywordRules:
    """Tests for keyword-based rule matching."""

    def test_fraude_keyword_triggers_verwijderen(self, analysis_service, fraude_clausule_text):
        """Fraude keyword should trigger VERWIJDEREN advice."""
        cluster = create_cluster(fraude_clausule_text, frequency=1)

        advice = analysis_service._check_keyword_rules(
            cluster,
            fraude_clausule_text.lower()
        )

        assert advice is not None
        assert advice.advice_code == "VERWIJDEREN"
        assert "Art 2.8" in advice.reference_article

    def test_molest_with_inclusion_keyword(self, analysis_service, molest_clausule_text):
        """Molest with 'inclusief' should trigger BEHOUDEN advice."""
        cluster = create_cluster(molest_clausule_text, frequency=1)

        advice = analysis_service._check_keyword_rules(
            cluster,
            molest_clausule_text.lower()
        )

        assert advice is not None
        assert "BEHOUDEN" in advice.advice_code
        assert "Art 2.14" in advice.reference_article

    def test_terrorisme_triggers_verwijderen(self, analysis_service, terrorisme_clausule_text):
        """Terrorisme keyword should trigger VERWIJDEREN advice."""
        cluster = create_cluster(terrorisme_clausule_text, frequency=1)

        advice = analysis_service._check_keyword_rules(
            cluster,
            terrorisme_clausule_text.lower()
        )

        assert advice is not None
        assert advice.advice_code == "VERWIJDEREN"

    def test_no_keyword_match_returns_none(self, analysis_service):
        """Text without matching keywords should return None."""
        text = "Dit is een normale clausule zonder speciale keywords."
        cluster = create_cluster(text, frequency=1)

        advice = analysis_service._check_keyword_rules(cluster, text.lower())

        assert advice is None

    def test_add_keyword_rule(self, analysis_service):
        """Should be able to add new keyword rules."""
        analysis_service.add_keyword_rule(
            name='test_rule',
            keywords=['testwoord'],
            advice='TEST_ADVICE',
            reason='Test reden',
            article='Art Test',
            confidence='Hoog'
        )

        text = "Dit bevat testwoord in de tekst."
        cluster = create_cluster(text, frequency=1)

        advice = analysis_service._check_keyword_rules(cluster, text.lower())

        assert advice is not None
        assert advice.advice_code == 'TEST_ADVICE'


# ============================================================
# Tests for Frequency Analysis (Step 3)
# ============================================================

class TestAnalysisServiceFrequency:
    """Tests for frequency-based analysis."""

    def test_high_frequency_suggests_standardization(self, analysis_service):
        """High frequency clusters should suggest standardization."""
        text = "Normale clausule zonder keywords"
        cluster = create_cluster(text, frequency=25)  # Above threshold (20)

        advice = analysis_service._step3_fallback_analysis(cluster)

        assert advice.advice_code == AdviceCode.STANDAARDISEREN.value
        assert "25x" in advice.reason
        assert advice.confidence == ConfidenceLevel.HOOG.value

    def test_low_frequency_internal_analysis(self, analysis_service):
        """Low frequency without conditions should get internal analysis."""
        text = "Normale clausule zonder keywords"
        cluster = create_cluster(text, frequency=3)

        # No policy sections loaded
        analysis_service._policy_sections = []

        advice = analysis_service._internal_analysis_fallback(cluster, frequency=3)

        assert advice.advice_code == AdviceCode.CONSISTENTIE_CHECK.value

    def test_unique_cluster_internal_analysis(self, analysis_service):
        """Unique (freq=1) clusters should get UNIEK advice."""
        text = "Unieke clausule"
        cluster = create_cluster(text, frequency=1)

        # No policy sections loaded
        analysis_service._policy_sections = []

        advice = analysis_service._internal_analysis_fallback(cluster, frequency=1)

        assert advice.advice_code == AdviceCode.UNIEK.value
        assert "1x" in advice.reason


# ============================================================
# Tests for Policy Conditions Check (Step 2)
# ============================================================

class TestAnalysisServiceConditionsCheck:
    """Tests for policy conditions matching."""

    def test_exact_substring_match(self, analysis_service, sample_policy_sections):
        """Exact substring match should return VERWIJDEREN."""
        # Set up policy sections
        analysis_service._policy_sections = sample_policy_sections
        analysis_service._policy_full_text = " ".join(
            s.simplified_text for s in sample_policy_sections
        )

        # Create cluster with text that appears in conditions
        text = "fraude en misleiding zijn uitgesloten van dekking"
        cluster = create_cluster(text, frequency=1)

        advice = analysis_service._step2_conditions_check(cluster)

        assert advice is not None
        assert advice.advice_code == AdviceCode.VERWIJDEREN.value
        assert "EXACT" in advice.reason.upper() or "voorwaarden" in advice.reason.lower()

    def test_no_conditions_returns_none(self, analysis_service):
        """Without conditions loaded, should return None."""
        analysis_service._policy_sections = []
        analysis_service._policy_full_text = ""

        cluster = create_cluster("Test tekst", frequency=1)

        advice = analysis_service._step2_conditions_check(cluster)

        assert advice is None


# ============================================================
# Tests for Clause Library Check (Step 1)
# ============================================================

class TestAnalysisServiceClauseLibrary:
    """Tests for clause library matching."""

    def test_no_library_returns_none(self, analysis_service):
        """Without library loaded, should return None."""
        analysis_service.clause_library_service = None

        cluster = create_cluster("Test tekst", frequency=1)

        advice = analysis_service._step1_clause_library_check(cluster)

        assert advice is None

    def test_library_not_loaded_returns_none(self, analysis_service, mock_clause_library_service):
        """Library service that's not loaded should return None."""
        mock_clause_library_service.is_loaded = False
        analysis_service.clause_library_service = mock_clause_library_service

        cluster = create_cluster("Test tekst", frequency=1)

        advice = analysis_service._step1_clause_library_check(cluster)

        assert advice is None

    def test_high_match_returns_replace(self, analysis_service, mock_clause_library_service):
        """High similarity library match should return REPLACE advice."""
        # Set up mock to return a high similarity match
        mock_match = MagicMock()
        mock_match.is_replacement_candidate = True
        mock_match.is_review_candidate = False
        mock_match.similarity_score = 0.97
        mock_match.clause.code = "STD-001"

        mock_clause_library_service.is_loaded = True
        mock_clause_library_service.find_match.return_value = mock_match
        analysis_service.clause_library_service = mock_clause_library_service

        cluster = create_cluster("Test tekst", frequency=1)

        advice = analysis_service._step1_clause_library_check(cluster)

        assert advice is not None
        assert "VERVANGEN" in advice.advice_code
        assert "STD-001" in advice.reference_article

    def test_medium_match_returns_review(self, analysis_service, mock_clause_library_service):
        """Medium similarity match should return review advice."""
        mock_match = MagicMock()
        mock_match.is_replacement_candidate = False
        mock_match.is_review_candidate = True
        mock_match.similarity_score = 0.88
        mock_match.clause.code = "STD-002"

        mock_clause_library_service.is_loaded = True
        mock_clause_library_service.find_match.return_value = mock_match
        analysis_service.clause_library_service = mock_clause_library_service

        cluster = create_cluster("Test tekst", frequency=1)

        advice = analysis_service._step1_clause_library_check(cluster)

        assert advice is not None
        assert "CONTROLEER" in advice.advice_code


# ============================================================
# Tests for Custom Instructions Check (Step 0.5)
# ============================================================

class TestAnalysisServiceCustomInstructions:
    """Tests for custom instructions matching."""

    def test_no_service_returns_none(self, analysis_service):
        """Without custom instructions service, should return None."""
        analysis_service.custom_instructions_service = None

        cluster = create_cluster("Test tekst met meeverzekerde", frequency=1)

        advice = analysis_service._step05_custom_instructions_check(cluster)

        assert advice is None

    def test_service_not_loaded_returns_none(self, analysis_service):
        """Custom instructions service that's not loaded should return None."""
        mock_service = MagicMock()
        mock_service.is_loaded = False
        analysis_service.custom_instructions_service = mock_service

        cluster = create_cluster("Test tekst", frequency=1)

        advice = analysis_service._step05_custom_instructions_check(cluster)

        assert advice is None

    def test_match_returns_custom_action(self, analysis_service):
        """Custom instruction match should return custom action advice."""
        mock_service = MagicMock()
        mock_service.is_loaded = True
        mock_service.instruction_count = 3

        # Create mock match result
        mock_instruction = MagicMock()
        mock_instruction.search_text = "meeverzekerde"
        mock_instruction.action = "Vullen in partijenkaart"

        mock_match = MagicMock()
        mock_match.instruction = mock_instruction
        mock_match.score = 1.0

        mock_service.find_match.return_value = mock_match
        analysis_service.custom_instructions_service = mock_service

        cluster = create_cluster("Dit gaat over meeverzekerde ondernemingen", frequency=1)

        advice = analysis_service._step05_custom_instructions_check(cluster)

        assert advice is not None
        assert "Vullen in partijenkaart" in advice.advice_code
        assert advice.category == "CUSTOM_INSTRUCTION"


# ============================================================
# Tests for Full Waterfall Pipeline
# ============================================================

class TestAnalysisServiceWaterfall:
    """Tests for the full waterfall analysis pipeline."""

    def test_waterfall_stops_at_first_match(self, analysis_service, fraude_clausule_text):
        """Waterfall should stop at first matching step."""
        cluster = create_cluster(fraude_clausule_text, frequency=1)

        stats = {'step0_admin_issues': 0, 'step05_custom_instructions': 0,
                 'step1_library_match': 0, 'step2_conditions_match': 0,
                 'step3_fallback': 0, 'multi_clause': 0}

        advice = analysis_service._analyze_with_waterfall(cluster, stats)

        # Fraude keyword should trigger Step 3 fallback
        assert advice is not None
        assert stats['step3_fallback'] == 1

    def test_analyze_clusters_returns_advice_map(self, analysis_service, sample_clusters):
        """analyze_clusters should return dictionary of advice."""
        advice_map = analysis_service.analyze_clusters(
            sample_clusters,
            policy_sections=[]
        )

        assert isinstance(advice_map, dict)
        assert len(advice_map) == len(sample_clusters)

        for cluster in sample_clusters:
            assert cluster.id in advice_map
            assert isinstance(advice_map[cluster.id], AnalysisAdvice)

    def test_analyze_clusters_with_progress_callback(self, analysis_service, sample_clusters):
        """Progress callback should be called during analysis."""
        progress_values = []

        def callback(progress: int):
            progress_values.append(progress)

        analysis_service.analyze_clusters(
            sample_clusters,
            policy_sections=[],
            progress_callback=callback
        )

        # Should have received progress updates including 100%
        assert 100 in progress_values


# ============================================================
# Tests for Reference Formatting
# ============================================================

class TestAnalysisServiceReferenceFormatting:
    """Tests for reference article formatting."""

    def test_format_section_with_article_and_title(self, analysis_service):
        """Should format article + title properly."""
        section = PolicyDocumentSection(
            id="Art 5",
            title="Motorrijtuigen",
            raw_text="...",
            simplified_text="...",
            document_id="Voorwaarden",
            page_number=8
        )

        ref = analysis_service._format_section_reference(section)

        assert "Art 5" in ref
        assert "Motorrijtuigen" in ref

    def test_format_section_truncates_long_title(self, analysis_service):
        """Should truncate very long references."""
        section = PolicyDocumentSection(
            id="Art 5",
            title="Dit is een heel erg lange titel die veel meer dan tachtig karakters bevat en daarom moet worden afgekort",
            raw_text="...",
            simplified_text="...",
            document_id="Voorwaarden",
            page_number=8
        )

        ref = analysis_service._format_section_reference(section)

        assert len(ref) <= 80
        assert "..." in ref

    def test_format_section_fallback_to_document_page(self, analysis_service):
        """Should fall back to document + page when no article."""
        section = PolicyDocumentSection(
            id="section_1",  # Not an article ID
            title="",
            raw_text="...",
            simplified_text="...",
            document_id="Voorwaarden 2024",
            page_number=15
        )

        ref = analysis_service._format_section_reference(section)

        assert "Voorwaarden 2024" in ref
        assert "15" in ref

    def test_format_none_section(self, analysis_service):
        """Should handle None section gracefully."""
        ref = analysis_service._format_section_reference(None)

        assert ref == "Voorwaarden"


# ============================================================
# Tests for Service Setters
# ============================================================

class TestAnalysisServiceSetters:
    """Tests for service setter methods."""

    def test_set_clause_library_service(self, analysis_service, mock_clause_library_service):
        """Should set clause library service."""
        analysis_service.set_clause_library_service(mock_clause_library_service)

        assert analysis_service.clause_library_service is mock_clause_library_service

    def test_set_hybrid_similarity_service(self, analysis_service, mock_hybrid_similarity_service):
        """Should set hybrid similarity service and enable hybrid mode."""
        analysis_service.set_hybrid_similarity_service(mock_hybrid_similarity_service)

        assert analysis_service.hybrid_similarity_service is mock_hybrid_similarity_service
        assert analysis_service._hybrid_enabled is True

    def test_set_custom_instructions_service(self, analysis_service):
        """Should set custom instructions service."""
        mock_service = MagicMock()
        mock_service.is_loaded = True
        mock_service.instruction_count = 5

        analysis_service.set_custom_instructions_service(mock_service)

        assert analysis_service.custom_instructions_service is mock_service
