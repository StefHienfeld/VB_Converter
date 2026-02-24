"""
Integration tests for the Product Library system (v5.0).

Tests the library-based analysis path through the orchestrator,
verifying that pre-computed data (sections, FAISS, TF-IDF) is
correctly injected and used.
"""

import json
import pickle
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hienfeld.config import load_config
from hienfeld.domain.policy_document import PolicyDocumentSection
from hienfeld.domain.standard_clause import StandardClause
from hienfeld.services.library_context import LibraryContext
from hienfeld.services.library_service import LibraryService
from hienfeld_api.database import Base
from hienfeld_api.models.library_models import (
    LibraryClause,
    LibrarySection,
    LibraryTfidfIndex,
    ProductLibrary,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database with all tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def session_factory(db_session):
    """Return a callable that always yields the same session."""
    return lambda: db_session


@pytest.fixture
def library_service(session_factory):
    """Create a LibraryService bound to the in-memory database."""
    return LibraryService(session_factory)


@pytest.fixture
def active_library(db_session):
    """Create a fully-built active library with sections, TF-IDF, and clauses."""
    lib_id = str(uuid.uuid4())
    library = ProductLibrary(
        id=lib_id,
        naam="Test Collectief Ongevallen",
        verzekeraar="Allianz",
        versie="2025-Q1",
        status="active",
        aangemaakt_door="test",
        section_count=3,
        clause_count=1,
    )
    db_session.add(library)

    # Add sections with embeddings (3 sections)
    section_texts = [
        ("Art. 1", "Begripsomschrijvingen", "In deze voorwaarden wordt verstaan onder verzekerde: de natuurlijke persoon die als zodanig op de polis is vermeld."),
        ("Art. 2", "Dekking bij blijvende invaliditeit", "De verzekering biedt dekking bij blijvende invaliditeit als gevolg van een ongeval."),
        ("Art. 3", "Uitsluitingen", "Van de verzekering is uitgesloten schade als gevolg van opzet of bewuste roekeloosheid."),
    ]
    dim = 64  # Small embedding dimension for test
    for i, (art_nr, title, text) in enumerate(section_texts):
        emb = np.random.randn(dim).astype(np.float32)
        db_session.add(LibrarySection(
            id=str(uuid.uuid4()),
            library_id=lib_id,
            artikel_nummer=art_nr,
            artikel_titel=title,
            ruwe_tekst=text,
            embedding_vector=emb.tobytes(),
            embedding_model="test-model",
            bron_bestand="test.pdf",
            pagina_nummer=i + 1,
            volgorde=i,
        ))

    # Add a TF-IDF index
    from sklearn.feature_extraction.text import TfidfVectorizer
    texts = [t for _, _, t in section_texts]
    vec = TfidfVectorizer(max_features=1000, min_df=1)
    mat = vec.fit_transform(texts)
    db_session.add(LibraryTfidfIndex(
        id=str(uuid.uuid4()),
        library_id=lib_id,
        serialized_index=pickle.dumps({"vectorizer": vec, "matrix": mat}),
        vocabulary_size=len(vec.vocabulary_),
        document_count=len(texts),
    ))

    # Add a clause
    db_session.add(LibraryClause(
        id=str(uuid.uuid4()),
        library_id=lib_id,
        code="CO-001",
        tekst="Standaard ongevallenclausule voor collectieve polissen",
        categorie="Dekking",
    ))

    db_session.commit()
    return lib_id


class TestLibraryContextLoading:
    """Test that LibraryService.load_library_for_analysis produces valid context."""

    def test_load_returns_context_for_active_library(self, library_service, active_library):
        ctx = library_service.load_library_for_analysis(active_library)
        assert ctx is not None
        assert isinstance(ctx, LibraryContext)
        assert ctx.library_id == active_library
        assert ctx.is_loaded

    def test_load_returns_none_for_missing_library(self, library_service):
        ctx = library_service.load_library_for_analysis("nonexistent-id")
        assert ctx is None

    def test_load_returns_none_for_draft_library(self, library_service, db_session):
        lib = ProductLibrary(naam="Draft", aangemaakt_door="test", status="draft")
        db_session.add(lib)
        db_session.commit()
        ctx = library_service.load_library_for_analysis(lib.id)
        assert ctx is None

    def test_context_has_policy_sections(self, library_service, active_library):
        ctx = library_service.load_library_for_analysis(active_library)
        assert len(ctx.policy_sections) == 3
        assert all(isinstance(s, PolicyDocumentSection) for s in ctx.policy_sections)
        assert ctx.policy_sections[0].title == "Begripsomschrijvingen"

    def test_context_has_faiss_store(self, library_service, active_library):
        ctx = library_service.load_library_for_analysis(active_library)
        assert ctx.has_faiss
        assert ctx.faiss_store is not None

    def test_context_has_tfidf(self, library_service, active_library):
        ctx = library_service.load_library_for_analysis(active_library)
        assert ctx.has_tfidf
        assert ctx.tfidf_vectorizer is not None
        assert ctx.tfidf_matrix is not None

    def test_context_has_standard_clauses(self, library_service, active_library):
        ctx = library_service.load_library_for_analysis(active_library)
        assert ctx.has_clauses
        assert len(ctx.standard_clauses) == 1
        assert ctx.standard_clauses[0].code == "CO-001"


class TestDocumentSimilarityPrecomputed:
    """Test the set_precomputed method on DocumentSimilarityService."""

    def test_set_precomputed_marks_trained(self):
        from hienfeld.services.document_similarity_service import DocumentSimilarityService

        config = load_config()
        config.semantic.enable_tfidf = True
        svc = DocumentSimilarityService(config)

        from sklearn.feature_extraction.text import TfidfVectorizer
        texts = ["document een", "document twee", "document drie"]
        vec = TfidfVectorizer()
        mat = vec.fit_transform(texts)

        svc.set_precomputed(vec, mat, texts)
        assert svc.is_trained

    def test_set_precomputed_allows_similarity(self):
        from hienfeld.services.document_similarity_service import DocumentSimilarityService

        config = load_config()
        config.semantic.enable_tfidf = True
        svc = DocumentSimilarityService(config)

        from sklearn.feature_extraction.text import TfidfVectorizer
        texts = ["de verzekering biedt dekking", "de polis is van kracht"]
        vec = TfidfVectorizer()
        mat = vec.fit_transform(texts)

        svc.set_precomputed(vec, mat, texts)
        score = svc.similarity("de verzekering biedt dekking", "de polis is van kracht")
        assert 0.0 <= score <= 1.0


class TestClauseLibraryPreloaded:
    """Test load_from_standard_clauses on ClauseLibraryService."""

    def test_load_from_standard_clauses(self):
        from hienfeld.services.clause_library_service import ClauseLibraryService

        config = load_config()
        svc = ClauseLibraryService(config)

        clauses = [
            StandardClause(code="CO-001", text="Standaard clausule", simplified_text="standaard clausule", category="Dekking"),
            StandardClause(code="CO-002", text="Andere clausule", simplified_text="andere clausule", category="Uitsluiting"),
        ]
        count = svc.load_from_standard_clauses(clauses)
        assert count == 2
        assert svc.is_loaded
        assert svc.clause_count == 2


class TestAnalysisServiceRAGPath:
    """Test that AnalysisService uses RAG when rag_service is provided."""

    def test_rag_service_wired_to_analysis(self):
        from hienfeld.services.analysis_service import AnalysisService

        config = load_config()
        mock_rag = MagicMock()
        mock_rag.is_ready.return_value = True

        svc = AnalysisService(config, rag_service=mock_rag)
        assert svc.rag_service is mock_rag

    def test_step2_uses_rag_when_available(self):
        """When RAG is ready, _step2_conditions_check_rag is called instead of classic."""
        from hienfeld.services.analysis_service import AnalysisService
        from hienfeld.domain.cluster import Cluster
        from hienfeld.domain.clause import Clause

        config = load_config()

        # Create a mock RAG service that returns candidates
        mock_rag = MagicMock()
        mock_rag.is_ready.return_value = True
        mock_rag.retrieve_relevant_sections.return_value = []

        svc = AnalysisService(config, rag_service=mock_rag)

        # Create a cluster with enough text to pass length checks
        clause = Clause(
            id="c1",
            raw_text="De verzekering biedt dekking bij blijvende invaliditeit als gevolg van een ongeval dat optreedt tijdens de looptijd van de polis.",
            simplified_text="de verzekering biedt dekking bij blijvende invaliditeit als gevolg van een ongeval dat optreedt tijdens de looptijd van de polis",
        )
        cluster = Cluster(id="cl1", leader_clause=clause, member_ids=["c1"], frequency=1)

        # Set up policy sections so step2 doesn't skip
        section = PolicyDocumentSection(
            id="s1", title="Dekking", raw_text="Dekking info",
            simplified_text="dekking info", page_number=1, document_id="test.pdf",
        )
        svc._policy_sections = [section]
        svc._policy_section_lookup = {"s1": section}
        svc._policy_full_text = "dekking info"

        # Call the RAG method directly
        result = svc._step2_conditions_check_rag(cluster)
        # RAG returned empty candidates, so it falls back to classic (which also returns None here)
        # The key point: RAG retrieval was called
        mock_rag.retrieve_relevant_sections.assert_called_once()


class TestOrchestratorLibraryPath:
    """Test that the orchestrator correctly branches on library_id."""

    def test_analysis_input_uses_library(self):
        from hienfeld_api.orchestrators import AnalysisInput

        input_with = AnalysisInput(
            policy_bytes=b"test",
            policy_filename="test.xlsx",
            conditions_files=[],
            clause_library_files=[],
            reference_file=None,
            settings={"library_id": "some-uuid"},
        )
        assert input_with.uses_library
        assert input_with.library_id == "some-uuid"

    def test_analysis_input_no_library(self):
        from hienfeld_api.orchestrators import AnalysisInput

        input_without = AnalysisInput(
            policy_bytes=b"test",
            policy_filename="test.xlsx",
            conditions_files=[],
            clause_library_files=[],
            reference_file=None,
            settings={},
        )
        assert not input_without.uses_library
        assert input_without.library_id is None

    def test_orchestrator_accepts_library_service(self):
        from hienfeld_api.orchestrators import AnalysisOrchestrator

        mock_svc = MagicMock()
        orch = AnalysisOrchestrator(library_service=mock_svc)
        assert orch._library_service is mock_svc
