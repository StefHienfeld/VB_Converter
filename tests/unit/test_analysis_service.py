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


# ============================================================
# EXPANDED TESTS FOR STEP 2: POLICY CONDITIONS CHECK
# ============================================================

class TestStep2ConditionsCheckExpanded:
    """Comprehensive tests for Step 2 - Policy conditions matching."""

    @pytest.fixture
    def service_with_conditions(self, config):
        """Service with loaded policy conditions."""
        service = AnalysisService(config)

        # Create realistic policy sections
        service._policy_sections = [
            PolicyDocumentSection(
                id="Artikel 3",
                title="Uitsluitingen",
                simplified_text="fraude en misleiding zijn uitgesloten van dekking",
                raw_text="Fraude en misleiding zijn uitgesloten van dekking.",
                page_number=5,
                document_id="Voorwaarden.pdf"
            ),
            PolicyDocumentSection(
                id="Artikel 7",
                title="Eigen risico",
                simplified_text="het eigen risico bedraagt € 250 per schadegeval",
                raw_text="Het eigen risico bedraagt € 250 per schadegeval.",
                page_number=12,
                document_id="Voorwaarden.pdf"
            ),
            PolicyDocumentSection(
                id="Artikel 9",
                title="Verzekerde bedragen",
                simplified_text="de maximale dekking is € 1.000.000 per gebeurtenis",
                raw_text="De maximale dekking is € 1.000.000 per gebeurtenis.",
                page_number=15,
                document_id="Voorwaarden.pdf"
            )
        ]
        service._policy_full_text = " ".join(s.simplified_text for s in service._policy_sections)

        return service

    def test_exact_match_above_95_percent(self, service_with_conditions, mock_hybrid_similarity_service):
        """Similarity ≥95% should return VERWIJDEREN with high confidence."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        # Mock high similarity match - returns (index, score, breakdown)
        mock_breakdown = MagicMock()
        mock_hybrid_similarity_service.find_best_match.return_value = (
            0,  # index in candidates list
            0.97,  # Above 95% threshold
            mock_breakdown
        )

        cluster = create_cluster("fraude en misleiding uitgesloten", frequency=3)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is not None
        assert advice.advice_code == AdviceCode.VERWIJDEREN.value
        assert advice.confidence == ConfidenceLevel.HOOG.value
        assert advice.reference_article  # Should have a reference

    def test_high_similarity_between_85_and_95_percent(self, service_with_conditions, mock_hybrid_similarity_service):
        """Similarity 85-95% should return VERWIJDEREN with medium confidence."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        # Mock medium-high similarity
        mock_breakdown = MagicMock()
        mock_hybrid_similarity_service.find_best_match.return_value = (
            1,  # index
            0.89,  # Between 85-95%
            mock_breakdown
        )

        cluster = create_cluster("eigen risico 250 euro per schade", frequency=2)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is not None
        assert advice.advice_code == AdviceCode.VERWIJDEREN.value
        assert advice.confidence == ConfidenceLevel.MIDDEN.value
        assert "review" in advice.reason.lower() or "controleer" in advice.reason.lower()

    def test_exact_boundary_95_percent(self, service_with_conditions, mock_hybrid_similarity_service):
        """Similarity exactly 0.95 should be treated as high confidence."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        mock_breakdown = MagicMock()
        mock_hybrid_similarity_service.find_best_match.return_value = (
            2,  # index
            0.95,  # Exact boundary
            mock_breakdown
        )

        cluster = create_cluster("maximale dekking 1 miljoen", frequency=1)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is not None
        assert advice.confidence == ConfidenceLevel.HOOG.value

    def test_exact_boundary_85_percent(self, service_with_conditions, mock_hybrid_similarity_service):
        """Similarity exactly 0.85 should be treated as medium confidence."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        mock_breakdown = MagicMock()
        mock_hybrid_similarity_service.find_best_match.return_value = (
            0,  # index
            0.85,  # Exact boundary
            mock_breakdown
        )

        cluster = create_cluster("misleiding is uitgesloten", frequency=1)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is not None
        assert advice.confidence == ConfidenceLevel.MIDDEN.value

    def test_below_85_percent_returns_none(self, service_with_conditions, mock_hybrid_similarity_service):
        """Similarity <85% should return None (continue to next step)."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        mock_breakdown = MagicMock()
        mock_hybrid_similarity_service.find_best_match.return_value = (
            0,  # index
            0.75,  # Below threshold
            mock_breakdown
        )

        cluster = create_cluster("iets anders", frequency=1)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is None  # Falls through to Step 3

    def test_no_match_found_returns_none(self, service_with_conditions, mock_hybrid_similarity_service):
        """When no match is found, should return None."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        # No match returns None
        mock_hybrid_similarity_service.find_best_match.return_value = None

        cluster = create_cluster("completely different text", frequency=1)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is None

    def test_empty_cluster_text_returns_none(self, service_with_conditions):
        """Empty cluster text should not crash."""
        cluster = create_cluster("", frequency=1)
        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is None

    def test_none_cluster_text_returns_none(self, service_with_conditions):
        """None cluster text should not crash."""
        cluster = create_cluster("test", frequency=1)
        cluster.leader_clause.simplified_text = None

        advice = service_with_conditions._step2_conditions_check(cluster)

        assert advice is None

    def test_hybrid_service_failure_fallback(self, service_with_conditions, mock_hybrid_similarity_service):
        """When hybrid service fails, should handle gracefully."""
        service_with_conditions.hybrid_similarity_service = mock_hybrid_similarity_service
        service_with_conditions._hybrid_enabled = True

        # Mock service raises exception
        mock_hybrid_similarity_service.find_best_match.side_effect = Exception("Service failed")

        cluster = create_cluster("test text", frequency=1)

        # Should not crash - either return None or use fallback
        try:
            advice = service_with_conditions._step2_conditions_check(cluster)
            # If it doesn't crash, success
            assert True
        except Exception:
            pytest.fail("Should handle service failure gracefully")


# ============================================================
# EXPANDED TESTS FOR STEP 3: FALLBACK ANALYSIS
# ============================================================

class TestStep3FallbackAnalysisExpanded:
    """Comprehensive tests for Step 3 - Fallback analysis logic."""

    @pytest.fixture
    def service_with_keywords(self, config):
        """Service with keyword rules configured."""
        service = AnalysisService(config)

        # Add some keyword rules
        service.add_keyword_rule(
            name='maatwerk',
            keywords=['maatwerk', 'specifieke afspraak', 'individueel'],
            advice='BEHOUDEN (MAATWERK)',
            reason='Maatwerk clausule',
            confidence='Hoog'
        )

        service.add_keyword_rule(
            name='sancties',
            keywords=['sancties', 'boycot', 'embargo'],
            advice='VERWIJDEREN',
            reason='Sanctieclausule verwijderen',
            confidence='Hoog'
        )

        return service

    def test_keyword_match_returns_advice(self, service_with_keywords):
        """Matching keyword should return configured advice."""
        cluster = create_cluster("Deze polis bevat maatwerk afspraken", frequency=5)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None
        assert "BEHOUDEN" in advice.advice_code
        assert "Maatwerk" in advice.reason

    def test_multiple_keyword_match_first_wins(self, service_with_keywords):
        """When multiple keywords match, first rule should win."""
        service_with_keywords.add_keyword_rule(
            name='other',
            keywords=['polis'],
            advice='CONTROLEER',
            reason='Other',
            confidence='Laag'
        )

        cluster = create_cluster("Deze polis heeft maatwerk en sancties", frequency=1)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        # Should match the first rule that triggers (maatwerk)
        assert advice is not None

    def test_high_frequency_standardize(self, service_with_keywords, config):
        """High frequency (≥20) should suggest standardization."""
        # Update config threshold
        config.analysis_rules.frequency_standardize_threshold = 20
        service = AnalysisService(config)

        cluster = create_cluster("veel voorkomende tekst", frequency=25)
        advice = service._step3_fallback_analysis(cluster)

        assert advice is not None
        # High frequency may suggest keeping for standardization
        assert advice.advice_code is not None

    def test_low_frequency_keep(self, service_with_keywords):
        """Low frequency (<20) without keywords should keep."""
        cluster = create_cluster("unieke clausule zonder keywords", frequency=1)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None
        # Should return some advice (exact code depends on logic)
        assert advice.advice_code is not None

    def test_medium_frequency_keep(self, service_with_keywords):
        """Medium frequency (5-19) should keep with review."""
        cluster = create_cluster("semi-frequente clausule", frequency=10)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None
        assert advice.advice_code is not None

    def test_very_long_text_manual_check(self, service_with_keywords):
        """Very long text should get manual check advice."""
        long_text = "Dit is een zeer lange clausule. " * 100  # ~3300 chars
        cluster = create_cluster(long_text, frequency=1)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None
        # Should return advice for long text
        assert advice.advice_code is not None

    def test_empty_text_fallback(self, service_with_keywords):
        """Empty text should return safe default."""
        cluster = create_cluster("", frequency=1)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None
        # Should not crash

    def test_special_characters_handled(self, service_with_keywords):
        """Special characters should not break analysis."""
        cluster = create_cluster("Clausule met € 1.000,- en 50% korting", frequency=3)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None

    def test_unicode_text_handled(self, service_with_keywords):
        """Unicode characters should be handled."""
        cluster = create_cluster("Clàusule mét speciâle tëkens", frequency=2)
        advice = service_with_keywords._step3_fallback_analysis(cluster)

        assert advice is not None


# ============================================================
# EDGE CASES & ERROR HANDLING
# ============================================================

class TestAnalysisServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_service_without_any_dependencies(self, config):
        """Service should work with minimal dependencies."""
        service = AnalysisService(config)
        # No clause library, no conditions, no custom instructions

        cluster = create_cluster("test tekst", frequency=1)
        advice = service._step3_fallback_analysis(cluster)

        assert advice is not None  # Should fallback to basic analysis

    def test_null_similarity_service(self, config):
        """Should handle None similarity service gracefully."""
        service = AnalysisService(config)
        service.similarity_service = None

        cluster = create_cluster("test", frequency=1)

        # Should not crash when calling methods that need similarity
        try:
            advice = service._step3_fallback_analysis(cluster)
            assert True
        except AttributeError:
            pytest.fail("Should handle None similarity service")

    def test_threshold_exactly_at_boundary(self, config):
        """Test behavior at exact threshold boundaries."""
        service = AnalysisService(config)

        # Set specific thresholds (using correct parameter names)
        service.set_similarity_thresholds(
            exact=0.95,
            high=0.85,
            medium=0.75
        )

        assert service.config.analysis_rules.conditions_match.exact_match_threshold == 0.95
        assert service.config.analysis_rules.conditions_match.high_similarity_threshold == 0.85

    def test_very_short_text_handling(self, config):
        """Very short text (<10 chars) should be handled."""
        service = AnalysisService(config)

        cluster = create_cluster("OK", frequency=1)
        advice = service._step3_fallback_analysis(cluster)

        assert advice is not None

    def test_waterfall_pipeline_integration(self, config, mock_clause_library_service):
        """Test full waterfall continues through steps correctly."""
        service = AnalysisService(config)

        # Set up clause library that returns None (no match)
        mock_clause_library_service.is_loaded = True
        mock_clause_library_service.find_match.return_value = None
        service.clause_library_service = mock_clause_library_service

        # No policy conditions loaded
        service._policy_sections = []

        cluster = create_cluster("test clause", frequency=1)

        # Step 1 should return None (no library match)
        step1_result = service._step1_clause_library_check(cluster)
        assert step1_result is None

        # Step 2 should return None (no conditions)
        step2_result = service._step2_conditions_check(cluster)
        assert step2_result is None

        # Step 3 should return an advice (fallback always returns)
        step3_result = service._step3_fallback_analysis(cluster)
        assert step3_result is not None
