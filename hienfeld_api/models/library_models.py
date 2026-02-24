"""
SQLAlchemy ORM models for Product Library persistence.

Defines the database schema for product libraries, sections, clauses,
TF-IDF indices, and synonym overrides. These models support the
library-based RAG analysis pipeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hienfeld_api.database import Base


def _new_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class ProductLibrary(Base):
    """
    A product library containing pre-processed policy conditions.

    Represents a specific insurance product (e.g. "Collectieve Ongevallen",
    "Aansprakelijkheid") with pre-computed embeddings and TF-IDF indices
    for fast RAG-based analysis.

    Status lifecycle: draft -> building -> active -> archived
    """

    __tablename__ = "product_libraries"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    # Library metadata (Dutch domain names per convention)
    naam: Mapped[str] = mapped_column(String(255), nullable=False)
    verzekeraar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    versie: Mapped[str | None] = mapped_column(String(100), nullable=True)
    beschrijving: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: "draft" | "building" | "active" | "archived"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    # Creator
    aangemaakt_door: Mapped[str] = mapped_column(String(255), nullable=False, default="anonymous")

    # Timestamps
    aangemaakt_op: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    bijgewerkt_op: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Build progress (0-100)
    build_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    build_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cached counts for fast display
    section_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    sections: Mapped[list["LibrarySection"]] = relationship(
        back_populates="library", cascade="all, delete-orphan", order_by="LibrarySection.volgorde"
    )
    clauses: Mapped[list["LibraryClause"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )
    tfidf_index: Mapped["LibraryTfidfIndex | None"] = relationship(
        back_populates="library", cascade="all, delete-orphan", uselist=False
    )
    synonym_overrides: Mapped[list["LibrarySynonymOverride"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )


class LibrarySection(Base):
    """
    A section (article/clause) from a policy conditions document.

    Stores the raw text, metadata, and pre-computed embedding vector
    for fast similarity search via FAISS.
    """

    __tablename__ = "library_sections"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    # Foreign key to library
    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_libraries.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Section metadata
    artikel_nummer: Mapped[str | None] = mapped_column(String(50), nullable=True)
    artikel_titel: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ruwe_tekst: Mapped[str] = mapped_column(Text, nullable=False)
    samenvatting: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Section classification: "dekking" | "uitsluiting" | "definitie" | "procedureel"
    sectie_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Key concepts as JSON array string: ["invaliditeit", "uitkering"]
    kernbegrippen: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pre-computed embedding (numpy array as bytes via np.tobytes/np.frombuffer)
    embedding_vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Source file information
    bron_bestand: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pagina_nummer: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Sort order within the library
    volgorde: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationship back to library
    library: Mapped["ProductLibrary"] = relationship(back_populates="sections")


class LibraryClause(Base):
    """
    A standard clause from a clause library file (CSV/Excel).

    Used for clause library matching in analysis Step 1.
    """

    __tablename__ = "library_clauses"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    # Foreign key to library
    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_libraries.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Clause data
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    tekst: Mapped[str] = mapped_column(Text, nullable=False)
    categorie: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Optional pre-computed embedding
    embedding_vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Source file
    bron_bestand: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationship back to library
    library: Mapped["ProductLibrary"] = relationship(back_populates="clauses")


class LibraryTfidfIndex(Base):
    """
    Serialized TF-IDF index for a library.

    Stores the sklearn TfidfVectorizer + matrix as a serialized blob.
    Only one per library (unique constraint on library_id).
    """

    __tablename__ = "library_tfidf_indices"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    # Foreign key to library (unique: one index per library)
    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_libraries.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Serialized index data (pickle/joblib)
    serialized_index: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Index metadata
    vocabulary_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship back to library
    library: Mapped["ProductLibrary"] = relationship(back_populates="tfidf_index")


class LibrarySynonymOverride(Base):
    """
    Custom synonym override for a specific library.

    Allows product-specific synonym mappings that extend or override
    the default insurance_synonyms.json database.
    """

    __tablename__ = "library_synonym_overrides"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)

    # Foreign key to library
    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_libraries.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Synonym data
    term: Mapped[str] = mapped_column(String(255), nullable=False)
    # JSON array of synonyms: ["blijvende invaliditeit", "permanent letsel"]
    synoniemen: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship back to library
    library: Mapped["ProductLibrary"] = relationship(back_populates="synonym_overrides")

    __table_args__ = (
        UniqueConstraint("library_id", "term", name="uq_library_synonym_term"),
    )
