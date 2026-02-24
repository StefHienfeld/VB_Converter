"""
Unit tests for Product Library database models.

Tests CRUD operations on all library models using in-memory SQLite.
"""

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hienfeld_api.database import Base
from hienfeld_api.models.library_models import (
    LibraryClause,
    LibrarySection,
    LibrarySynonymOverride,
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


class TestProductLibrary:
    """Tests for the ProductLibrary model."""

    def test_create_library(self, db_session):
        library = ProductLibrary(
            id=str(uuid.uuid4()),
            naam="Collectieve Ongevallen",
            verzekeraar="Allianz",
            versie="2025-Q1",
            beschrijving="Test library",
            status="draft",
            aangemaakt_door="test-user",
        )
        db_session.add(library)
        db_session.commit()

        result = db_session.query(ProductLibrary).first()
        assert result is not None
        assert result.naam == "Collectieve Ongevallen"
        assert result.verzekeraar == "Allianz"
        assert result.versie == "2025-Q1"
        assert result.status == "draft"
        assert result.section_count == 0
        assert result.clause_count == 0
        assert result.build_progress == 0

    def test_default_values(self, db_session):
        library = ProductLibrary(
            naam="Test",
            aangemaakt_door="user",
        )
        db_session.add(library)
        db_session.commit()

        result = db_session.query(ProductLibrary).first()
        assert result.id is not None  # UUID auto-generated
        assert result.status == "draft"
        assert result.build_progress == 0
        assert result.section_count == 0
        assert result.clause_count == 0
        assert result.aangemaakt_op is not None
        assert result.bijgewerkt_op is not None

    def test_status_lifecycle(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        # draft -> building -> active -> archived
        for status in ["building", "active", "archived"]:
            library.status = status
            db_session.commit()
            result = db_session.query(ProductLibrary).first()
            assert result.status == status


class TestLibrarySection:
    """Tests for the LibrarySection model."""

    def test_create_section(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        section = LibrarySection(
            library_id=library.id,
            artikel_nummer="Art. 2.3",
            artikel_titel="Dekking bij blijvende invaliditeit",
            ruwe_tekst="De verzekering biedt dekking bij blijvende invaliditeit...",
            sectie_type="dekking",
            kernbegrippen=json.dumps(["invaliditeit", "uitkering"]),
            embedding_vector=b"\x00" * 128,  # Dummy embedding bytes
            embedding_model="test-model",
            bron_bestand="voorwaarden.pdf",
            pagina_nummer=5,
            volgorde=1,
        )
        db_session.add(section)
        db_session.commit()

        result = db_session.query(LibrarySection).first()
        assert result is not None
        assert result.artikel_nummer == "Art. 2.3"
        assert result.ruwe_tekst.startswith("De verzekering")
        assert result.embedding_vector == b"\x00" * 128
        assert result.library_id == library.id

    def test_section_library_relationship(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        section = LibrarySection(
            library_id=library.id,
            ruwe_tekst="Test tekst",
            volgorde=0,
        )
        db_session.add(section)
        db_session.commit()

        # Access via relationship
        db_session.refresh(library)
        assert len(library.sections) == 1
        assert library.sections[0].ruwe_tekst == "Test tekst"

    def test_cascade_delete(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        section = LibrarySection(library_id=library.id, ruwe_tekst="Test", volgorde=0)
        db_session.add(section)
        db_session.commit()

        db_session.delete(library)
        db_session.commit()

        assert db_session.query(LibrarySection).count() == 0


class TestLibraryClause:
    """Tests for the LibraryClause model."""

    def test_create_clause(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        clause = LibraryClause(
            library_id=library.id,
            code="CO-001",
            tekst="Standaard clausule tekst",
            categorie="Dekking",
            bron_bestand="clausules.xlsx",
        )
        db_session.add(clause)
        db_session.commit()

        result = db_session.query(LibraryClause).first()
        assert result.code == "CO-001"
        assert result.tekst == "Standaard clausule tekst"
        assert result.categorie == "Dekking"


class TestLibraryTfidfIndex:
    """Tests for the LibraryTfidfIndex model."""

    def test_create_tfidf_index(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        index = LibraryTfidfIndex(
            library_id=library.id,
            serialized_index=b"serialized-data",
            vocabulary_size=500,
            document_count=47,
        )
        db_session.add(index)
        db_session.commit()

        result = db_session.query(LibraryTfidfIndex).first()
        assert result.vocabulary_size == 500
        assert result.document_count == 47
        assert result.serialized_index == b"serialized-data"

    def test_one_index_per_library(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        # Access via relationship (uselist=False)
        index = LibraryTfidfIndex(
            library_id=library.id,
            serialized_index=b"data",
            vocabulary_size=100,
            document_count=10,
        )
        db_session.add(index)
        db_session.commit()

        db_session.refresh(library)
        assert library.tfidf_index is not None
        assert library.tfidf_index.vocabulary_size == 100


class TestLibrarySynonymOverride:
    """Tests for the LibrarySynonymOverride model."""

    def test_create_synonym_override(self, db_session):
        library = ProductLibrary(naam="Test", aangemaakt_door="user")
        db_session.add(library)
        db_session.commit()

        override = LibrarySynonymOverride(
            library_id=library.id,
            term="BI",
            synoniemen=json.dumps(["blijvende invaliditeit", "permanent letsel"]),
        )
        db_session.add(override)
        db_session.commit()

        result = db_session.query(LibrarySynonymOverride).first()
        assert result.term == "BI"
        synonyms = json.loads(result.synoniemen)
        assert "blijvende invaliditeit" in synonyms
        assert "permanent letsel" in synonyms


class TestFullLibraryWorkflow:
    """Integration-style tests for the complete library workflow."""

    def test_complete_library_with_all_related_objects(self, db_session):
        """Test creating a complete library with sections, clauses, index, and synonyms."""
        # Create library
        library = ProductLibrary(
            naam="Collectieve Ongevallen",
            verzekeraar="Allianz",
            versie="2025-Q1",
            aangemaakt_door="test-user",
            status="active",
            section_count=2,
            clause_count=1,
        )
        db_session.add(library)
        db_session.commit()

        # Add sections
        for i in range(2):
            section = LibrarySection(
                library_id=library.id,
                artikel_nummer=f"Art. {i + 1}",
                artikel_titel=f"Artikel {i + 1}",
                ruwe_tekst=f"Tekst van artikel {i + 1}",
                embedding_vector=bytes(range(128)),
                embedding_model="test-model",
                volgorde=i,
            )
            db_session.add(section)

        # Add clause
        clause = LibraryClause(
            library_id=library.id,
            code="CO-001",
            tekst="Standaard clausule",
            categorie="Dekking",
        )
        db_session.add(clause)

        # Add TF-IDF index
        index = LibraryTfidfIndex(
            library_id=library.id,
            serialized_index=b"tfidf-data",
            vocabulary_size=300,
            document_count=2,
        )
        db_session.add(index)

        # Add synonym override
        synonym = LibrarySynonymOverride(
            library_id=library.id,
            term="BI",
            synoniemen=json.dumps(["blijvende invaliditeit"]),
        )
        db_session.add(synonym)

        db_session.commit()
        db_session.refresh(library)

        # Verify all relationships
        assert len(library.sections) == 2
        assert len(library.clauses) == 1
        assert library.tfidf_index is not None
        assert len(library.synonym_overrides) == 1

        # Verify cascade delete removes everything
        db_session.delete(library)
        db_session.commit()

        assert db_session.query(ProductLibrary).count() == 0
        assert db_session.query(LibrarySection).count() == 0
        assert db_session.query(LibraryClause).count() == 0
        assert db_session.query(LibraryTfidfIndex).count() == 0
        assert db_session.query(LibrarySynonymOverride).count() == 0
