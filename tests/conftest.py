"""
Pytest configuration and fixtures for VB_Converter.

Provides shared fixtures for:
- Configuration objects
- Domain models (Clause, Cluster, PolicyDocumentSection)
- Mock services
- FastAPI test client
"""

import os
import pytest
from unittest.mock import MagicMock, Mock
from typing import List

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"


# ============================================================
# Configuration Fixtures
# ============================================================

@pytest.fixture(scope="session")
def config():
    """Load default application config for tests."""
    from hienfeld.config import load_config
    return load_config()


@pytest.fixture
def fast_mode_config():
    """Config with FAST analysis mode (no embeddings)."""
    from hienfeld.config import load_config, AnalysisMode
    cfg = load_config()
    cfg.semantic.apply_mode(AnalysisMode.FAST)
    return cfg


@pytest.fixture
def balanced_mode_config():
    """Config with BALANCED analysis mode."""
    from hienfeld.config import load_config, AnalysisMode
    cfg = load_config()
    cfg.semantic.apply_mode(AnalysisMode.BALANCED)
    return cfg


# ============================================================
# Domain Model Fixtures
# ============================================================

@pytest.fixture
def sample_clause():
    """Create a sample Clause object."""
    from hienfeld.domain.clause import Clause
    return Clause(
        id="clause_001",
        raw_text="Dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5.",
        simplified_text="dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5.",
        source_file_name="test_policy.xlsx"
    )


@pytest.fixture
def sample_clauses() -> List:
    """Create a list of sample clauses for clustering tests."""
    from hienfeld.domain.clause import Clause
    return [
        Clause(
            id=f"clause_{i:03d}",
            raw_text=text,
            simplified_text=text.lower().strip(),
            source_file_name="test.xlsx"
        )
        for i, text in enumerate([
            "Dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5.",
            "Dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5.",  # Duplicate
            "Schade aan gebouwen door brand is uitgesloten van dekking.",
            "Schade aan gebouwen door brand is uitgesloten.",  # Similar
            "Terrorisme is uitgesloten van dekking conform de standaard terrorismeclausule.",
            "Fraude en misleiding zijn uitgesloten van dekking.",
            "De verzekerde heeft recht op vergoeding van kosten tot EUR 10.000.",
            "De verzekerde heeft recht op vergoeding van kosten tot EUR 25.000.",  # Similar
            "Molest is meeverzekerd onder deze polis.",
            "Dit is een unieke clausule die maar een keer voorkomt.",
        ])
    ]


@pytest.fixture
def sample_cluster(sample_clause):
    """Create a sample Cluster object."""
    from hienfeld.domain.cluster import Cluster
    return Cluster(
        id="CL-0001",
        leader_clause=sample_clause,
        member_ids=["clause_002", "clause_003"],
        frequency=3,
        name="Motorrijtuig Dekking"
    )


@pytest.fixture
def sample_clusters(sample_clauses) -> List:
    """Create sample clusters from clauses."""
    from hienfeld.domain.cluster import Cluster

    # Manually create clusters from known groupings
    clusters = []

    # Cluster 1: Motorrijtuig dekking (2 identical clauses)
    clusters.append(Cluster(
        id="CL-0001",
        leader_clause=sample_clauses[0],
        member_ids=[sample_clauses[1].id],
        frequency=2,
        name="Motorrijtuig Dekking"
    ))

    # Cluster 2: Brand uitsluiting (2 similar clauses)
    clusters.append(Cluster(
        id="CL-0002",
        leader_clause=sample_clauses[2],
        member_ids=[sample_clauses[3].id],
        frequency=2,
        name="Brand Uitsluiting"
    ))

    # Cluster 3: Terrorisme (1 clause)
    clusters.append(Cluster(
        id="CL-0003",
        leader_clause=sample_clauses[4],
        member_ids=[],
        frequency=1,
        name="Terrorisme"
    ))

    # Cluster 4: Fraude (1 clause)
    clusters.append(Cluster(
        id="CL-0004",
        leader_clause=sample_clauses[5],
        member_ids=[],
        frequency=1,
        name="Fraude Uitsluiting"
    ))

    return clusters


@pytest.fixture
def sample_policy_sections() -> List:
    """Create sample policy document sections."""
    from hienfeld.domain.policy_document import PolicyDocumentSection
    return [
        PolicyDocumentSection(
            id="Art 1",
            title="Algemene Bepalingen",
            raw_text="Artikel 1 - Algemene Bepalingen\nDeze verzekering dekt schade aan het motorrijtuig.",
            simplified_text="artikel 1 - algemene bepalingen deze verzekering dekt schade aan het motorrijtuig.",
            document_id="Voorwaarden 2024",
            page_number=1
        ),
        PolicyDocumentSection(
            id="Art 2.8",
            title="Fraude Uitsluiting",
            raw_text="Artikel 2.8 - Fraude\nFraude en misleiding zijn uitgesloten van dekking.",
            simplified_text="artikel 2.8 - fraude fraude en misleiding zijn uitgesloten van dekking.",
            document_id="Voorwaarden 2024",
            page_number=3
        ),
        PolicyDocumentSection(
            id="Art 2.14",
            title="Molest",
            raw_text="Artikel 2.14 - Molest\nMolest en gewapend conflict zijn uitgesloten tenzij anders overeengekomen.",
            simplified_text="artikel 2.14 - molest molest en gewapend conflict zijn uitgesloten tenzij anders overeengekomen.",
            document_id="Voorwaarden 2024",
            page_number=4
        ),
        PolicyDocumentSection(
            id="Art 5",
            title="Dekking Motorrijtuigen",
            raw_text="Artikel 5 - Motorrijtuigen\nDekking voor schade aan het motorrijtuig is meeverzekerd.",
            simplified_text="artikel 5 - motorrijtuigen dekking voor schade aan het motorrijtuig is meeverzekerd.",
            document_id="Voorwaarden 2024",
            page_number=8
        )
    ]


# ============================================================
# Service Fixtures (Mocks)
# ============================================================

@pytest.fixture
def mock_similarity_service():
    """Create a mock similarity service."""
    mock = MagicMock()
    mock.similarity.return_value = 0.85
    mock.is_similar.return_value = True
    mock.threshold = 0.90
    return mock


@pytest.fixture
def mock_hybrid_similarity_service():
    """Create a mock hybrid similarity service."""
    from hienfeld.services.hybrid_similarity_service import SimilarityBreakdown

    mock = MagicMock()
    mock.similarity.return_value = 0.80
    mock.is_similar.return_value = True
    mock.find_best_match.return_value = (0, 0.85, SimilarityBreakdown(
        rapidfuzz=0.85,
        lemmatized=0.82,
        tfidf=0.75,
        synonyms=0.80,
        embeddings=0.88,
        final_score=0.85,
        methods_used=['rapidfuzz', 'lemmatized', 'embeddings']
    ))
    mock.train_tfidf = MagicMock()
    return mock


@pytest.fixture
def mock_clause_library_service():
    """Create a mock clause library service."""
    mock = MagicMock()
    mock.is_loaded = True
    mock.clause_count = 50
    mock.find_match.return_value = None  # No match by default
    return mock


@pytest.fixture
def mock_nlp_service():
    """Create a mock NLP service."""
    mock = MagicMock()
    mock.is_available = True
    mock.lemmatize_cached.side_effect = lambda text: text.lower()
    mock.extract_key_noun_phrases.return_value = ["dekking", "motorrijtuig"]
    return mock


# ============================================================
# FastAPI Test Client
# ============================================================

@pytest.fixture(scope="session")
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from hienfeld_api.app import app

    with TestClient(app) as c:
        yield c


# ============================================================
# Sample Text Fixtures
# ============================================================

@pytest.fixture
def sample_policy_text():
    """Sample policy text for tests."""
    return "Dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5."


@pytest.fixture
def sample_conditions_text():
    """Sample conditions text for tests."""
    return """
    Artikel 5 - Dekking motorrijtuigen
    Wij verzekeren schade aan het motorrijtuig volgens de voorwaarden van deze polis.
    """


@pytest.fixture
def fraude_clausule_text():
    """Sample fraude clause text for keyword rule tests."""
    return "Fraude en misleiding zijn uitgesloten van deze verzekering."


@pytest.fixture
def molest_clausule_text():
    """Sample molest clause text for keyword rule tests."""
    return "Molest is inclusief meeverzekerd onder deze polis."


@pytest.fixture
def terrorisme_clausule_text():
    """Sample terrorisme clause text for keyword rule tests."""
    return "Terrorisme is uitgesloten conform de NHT clausule."


@pytest.fixture
def long_text():
    """Very long text for length check tests."""
    base = "Dit is een voorbeeld clausule met veel tekst. "
    return base * 50  # ~2500 characters


@pytest.fixture
def short_text():
    """Very short text for minimum length tests."""
    return "ABC"


# ============================================================
# Helper Functions (not fixtures)
# ============================================================

def create_clause(text: str, clause_id: str = None):
    """Helper to create a Clause object."""
    from hienfeld.domain.clause import Clause
    return Clause(
        id=clause_id or f"clause_{hash(text) % 10000}",
        raw_text=text,
        simplified_text=text.lower().strip(),
        source_file_name="test.xlsx"
    )


def create_cluster(clause, cluster_id: str = None, frequency: int = 1, name: str = None):
    """Helper to create a Cluster object."""
    from hienfeld.domain.cluster import Cluster
    return Cluster(
        id=cluster_id or f"CL-{hash(clause.id) % 10000:04d}",
        leader_clause=clause,
        member_ids=[],
        frequency=frequency,
        name=name or "Test Cluster"
    )
