"""Service for managing product libraries."""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple
import numpy as np
from hienfeld.logging_config import get_logger
from hienfeld.services.library_context import LibraryContext
from hienfeld_api.models.library_models import (
    LibraryClause, LibrarySection, LibrarySynonymOverride,
    LibraryTfidfIndex, ProductLibrary,
)

logger = get_logger("library_service")


class LibraryService:
    """Service for managing product libraries."""

    def __init__(self, session_factory, config=None):
        self._session_factory = session_factory
        self._config = config

    def create_library(self, naam, verzekeraar=None, versie=None,
                       beschrijving=None, aangemaakt_door="anonymous"):
        """Create a new library record in draft status."""
        session = self._session_factory()
        try:
            lib = ProductLibrary(id=str(uuid.uuid4()), naam=naam,
                verzekeraar=verzekeraar, versie=versie, beschrijving=beschrijving,
                aangemaakt_door=aangemaakt_door, status="draft")
            session.add(lib)
            session.commit()
            logger.info("Created library %r (id=%s)", naam, lib.id)
            return self._to_dict(lib)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_libraries(self, status_filter=None):
        """Return all libraries ordered by bijgewerkt_op descending."""
        session = self._session_factory()
        try:
            q = session.query(ProductLibrary)
            if status_filter:
                q = q.filter(ProductLibrary.status == status_filter)
            return [self._to_dict(x) for x in q.order_by(ProductLibrary.bijgewerkt_op.desc()).all()]
        finally:
            session.close()

    def get_library(self, library_id):
        """Return a single library by ID, or None."""
        session = self._session_factory()
        try:
            lib = session.query(ProductLibrary).filter_by(id=library_id).first()
            return self._to_dict(lib) if lib else None
        finally:
            session.close()

    def get_build_status(self, library_id):
        """Return build progress dict, or None if library not found."""
        session = self._session_factory()
        try:
            lib = session.query(ProductLibrary).filter_by(id=library_id).first()
            if not lib:
                return None
            return {
                "status": lib.status, "build_progress": lib.build_progress,
                "build_message": lib.build_message,
                "section_count": lib.section_count, "clause_count": lib.clause_count,
            }
        finally:
            session.close()

    def archive_library(self, library_id):
        """Set library status to archived."""
        session = self._session_factory()
        try:
            lib = session.query(ProductLibrary).filter_by(id=library_id).first()
            if not lib:
                return False
            lib.status = "archived"
            lib.bijgewerkt_op = datetime.now(timezone.utc)
            session.commit()
            logger.info("Archived library %r", lib.naam)
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_library(self, library_id):
        """Delete a draft library. Raises ValueError for non-draft status."""
        session = self._session_factory()
        try:
            lib = session.query(ProductLibrary).filter_by(id=library_id).first()
            if not lib:
                return False
            if lib.status != "draft":
                raise ValueError(
                    f"Kan bibliotheek met status {repr(lib.status)} niet verwijderen. "
                    "Alleen concept-bibliotheken kunnen worden verwijderd."
                )
            session.delete(lib)
            session.commit()
            logger.info("Deleted library %r", lib.naam)
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_sections(self, library_id):
        """Return section preview data (ruwe_tekst truncated to 500 chars)."""
        session = self._session_factory()
        try:
            rows = (session.query(LibrarySection).filter_by(library_id=library_id)
                    .order_by(LibrarySection.volgorde).all())
            return [
                {
                    "id": s.id, "artikel_nummer": s.artikel_nummer,
                    "artikel_titel": s.artikel_titel,
                    "ruwe_tekst": s.ruwe_tekst[:500],
                    "sectie_type": s.sectie_type, "bron_bestand": s.bron_bestand,
                    "pagina_nummer": s.pagina_nummer,
                    "has_embedding": s.embedding_vector is not None,
                }
                for s in rows
            ]
        finally:
            session.close()

    def get_clauses(self, library_id):
        """Return clause preview data (tekst truncated to 300 chars)."""
        session = self._session_factory()
        try:
            rows = session.query(LibraryClause).filter_by(library_id=library_id).all()
            return [
                {"id": c.id, "code": c.code, "tekst": c.tekst[:300],
                 "categorie": c.categorie, "bron_bestand": c.bron_bestand}
                for c in rows
            ]
        finally:
            session.close()

    def build_library(
        self, library_id, conditions_files, clause_files,
        embeddings_service=None, policy_parser=None,
        clause_library_service=None, progress_callback=None,
    ):
        """
        Build a complete library index from uploaded documents.

        Stages:
        1. Parse policy conditions documents (PDF/DOCX/TXT)  [0-30%]
        2. Compute embeddings for each section               [30-70%]
        3. Parse clause library files (CSV/Excel)            [70-80%]
        4. Build TF-IDF index                                [80-90%]
        5. Finalize: set status=active                       [90-100%]

        On error the library is reset to draft status for retry.
        """
        session = self._session_factory()
        try:
            library = session.query(ProductLibrary).filter_by(id=library_id).first()
            if not library:
                raise ValueError(f"Bibliotheek {library_id} niet gevonden")
            library.status = "building"
            library.build_progress = 0
            library.build_message = "Build gestart..."
            session.commit()

            def _update(pct, msg):
                library.build_progress = pct
                library.build_message = msg
                session.commit()
                logger.debug("Build %d%%: %s", pct, msg)
                if progress_callback:
                    progress_callback(pct, msg)

            try:
                # Stage 1: parse conditions (0-30%)
                if conditions_files:
                    filenames = [f[1] for f in conditions_files]
                    _update(5, f"Voorwaarden parsen: {', '.join(filenames[:3])}{'...' if len(filenames) > 3 else ''}")
                else:
                    _update(5, "Geen voorwaarden-bestanden — alleen clausules")
                sections = []
                if policy_parser and conditions_files:
                    sections = policy_parser.parse_files_parallel(conditions_files)
                    logger.info("Parsed %d sections from %d file(s)", len(sections), len(conditions_files))
                _update(30, f"✓ {len(sections)} secties gevonden in {len(conditions_files)} bestand(en)")

                # Stage 2: persist sections + embeddings (30-70%)
                if embeddings_service:
                    _update(35, f"Secties opslaan en embeddings berekenen ({len(sections)} secties)...")
                else:
                    _update(35, f"Secties opslaan ({len(sections)} secties, geen embeddings)...")
                emb_model = getattr(embeddings_service, "model_name", "unknown") if embeddings_service else None

                for i, sec in enumerate(sections):
                    emb_bytes = None
                    if embeddings_service:
                        try:
                            vec = embeddings_service.embed_single(sec.raw_text)
                            emb_bytes = np.array(vec, dtype=np.float32).tobytes()
                        except Exception as e:
                            logger.warning("Embedding failed for %r: %s", sec.id, e)
                    session.add(LibrarySection(
                        id=str(uuid.uuid4()), library_id=library_id,
                        artikel_nummer=sec.id, artikel_titel=sec.title,
                        ruwe_tekst=sec.raw_text, sectie_type=None,
                        embedding_vector=emb_bytes,
                        embedding_model=emb_model if emb_bytes else None,
                        bron_bestand=sec.document_id, pagina_nummer=sec.page_number,
                        volgorde=i,
                    ))
                    if (i + 1) % 100 == 0:
                        session.flush()
                    if sections:
                        pct = 35 + int((i + 1) / len(sections) * 35)
                        if pct != library.build_progress:
                            _update(pct, f"Sectie {i + 1}/{len(sections)} verwerkt")
                session.commit()
                emb_status = "met embeddings" if embeddings_service else "zonder embeddings"
                _update(70, f"✓ {len(sections)} secties opgeslagen ({emb_status})")

                # Stage 3: clause library (70-80%)
                clause_count = 0
                if clause_library_service and clause_files:
                    _update(72, "Clausulebibliotheek laden...")
                    try:
                        clause_library_service.load_from_files(clause_files)
                        for cl in getattr(clause_library_service, "_clauses", []):
                            session.add(LibraryClause(
                                id=str(uuid.uuid4()), library_id=library_id,
                                code=cl.code, tekst=cl.text, categorie=cl.category,
                            ))
                            clause_count += 1
                        session.commit()
                        logger.info("Loaded %d clauses from clause library", clause_count)
                    except Exception as e:
                        logger.warning("Clause library load failed: %s", e)
                _update(80, f"✓ {clause_count} clausules opgeslagen")

                # Stage 4: TF-IDF index (80-90%)
                if sections:
                    _update(82, "TF-IDF index bouwen...")
                    try:
                        from sklearn.feature_extraction.text import TfidfVectorizer
                        texts = [s.raw_text for s in sections]
                        tfidf_vec = TfidfVectorizer(max_features=10000,
                            ngram_range=(1, 2), min_df=1, max_df=0.95)
                        tfidf_mat = tfidf_vec.fit_transform(texts)
                        existing = session.query(LibraryTfidfIndex).filter_by(library_id=library_id).first()
                        if existing:
                            session.delete(existing)
                            session.flush()
                        session.add(LibraryTfidfIndex(
                            id=str(uuid.uuid4()), library_id=library_id,
                            serialized_index=pickle.dumps({"vectorizer": tfidf_vec, "matrix": tfidf_mat}),
                            vocabulary_size=len(tfidf_vec.vocabulary_),
                            document_count=len(texts),
                        ))
                        session.commit()
                        logger.info("TF-IDF built: %d docs, %d terms", len(texts), len(tfidf_vec.vocabulary_))
                    except Exception as e:
                        logger.warning("TF-IDF index build failed: %s", e)
                _update(90, "✓ TF-IDF index opgebouwd")

                # Stage 5: finalize (90-100%)
                library.section_count = len(sections)
                library.clause_count = clause_count
                library.status = "active"
                library.build_progress = 100
                library.build_message = f"✅ Build voltooid: {len(sections)} secties, {clause_count} clausules"
                library.bijgewerkt_op = datetime.now(timezone.utc)
                session.commit()
                logger.info("Library %r build complete: %d sections, %d clauses",
                    library.naam, len(sections), clause_count)

            except Exception as e:
                logger.error("Library build failed: %s", e, exc_info=True)
                library.status = "draft"
                library.build_message = f"Build mislukt: {e}"
                library.build_progress = 0
                session.commit()
                raise

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def load_library_for_analysis(self, library_id):
        """
        Load an active library from the database into a LibraryContext.

        Returns None if library not found or not active.
        """
        from hienfeld.domain.policy_document import PolicyDocumentSection
        from hienfeld.domain.standard_clause import StandardClause

        session = self._session_factory()
        try:
            library = session.query(ProductLibrary).filter_by(id=library_id).first()
            if not library or library.status != "active":
                logger.warning("Library %s not available (status=%s)", library_id,
                    library.status if library else "not found")
                return None

            ctx = LibraryContext(library_id=library.id, library_naam=library.naam,
                section_count=library.section_count, clause_count=library.clause_count)

            # Load sections -> domain objects
            db_secs = (session.query(LibrarySection).filter_by(library_id=library_id)
                       .order_by(LibrarySection.volgorde).all())
            embeddings, sec_ids, sec_texts = [], [], []
            for s in db_secs:
                ctx.policy_sections.append(PolicyDocumentSection(
                    id=s.artikel_nummer or s.id, title=s.artikel_titel or "",
                    raw_text=s.ruwe_tekst, simplified_text=s.ruwe_tekst.lower().strip(),
                    page_number=s.pagina_nummer, document_id=s.bron_bestand,
                ))
                if s.embedding_vector:
                    embeddings.append(np.frombuffer(s.embedding_vector, dtype=np.float32))
                    sec_ids.append(s.id)
                    sec_texts.append(s.ruwe_tekst)

            # Build FAISS index from stored embeddings
            if embeddings:
                try:
                    from hienfeld.services.ai.vector_store import FaissVectorStore
                    dim = len(embeddings[0])
                    store = FaissVectorStore(embedding_dim=dim)
                    store.add_documents(
                        ids=sec_ids, vectors=np.stack(embeddings).astype(np.float32),
                        metadata=[{"text": t, "library_id": library_id} for t in sec_texts],
                    )
                    ctx.faiss_store = store
                    logger.info("FAISS index built: %d vectors, dim=%d", len(embeddings), dim)
                except Exception as e:
                    logger.warning("FAISS build failed: %s", e)

            # Deserialize TF-IDF index
            tfidf_rec = session.query(LibraryTfidfIndex).filter_by(library_id=library_id).first()
            if tfidf_rec:
                try:
                    data = pickle.loads(tfidf_rec.serialized_index)
                    ctx.tfidf_vectorizer = data["vectorizer"]
                    ctx.tfidf_matrix = data["matrix"]
                    logger.info("TF-IDF index loaded: %d docs", tfidf_rec.document_count)
                except Exception as e:
                    logger.warning("TF-IDF load failed: %s", e)

            # Load standard clauses
            for c in session.query(LibraryClause).filter_by(library_id=library_id).all():
                ctx.standard_clauses.append(StandardClause(
                    code=c.code, text=c.tekst, simplified_text=c.tekst.lower().strip(),
                    category=c.categorie or "",
                ))

            # Load synonym overrides
            for syn in session.query(LibrarySynonymOverride).filter_by(library_id=library_id).all():
                try:
                    ctx.synonym_overrides[syn.term] = json.loads(syn.synoniemen)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Synonym override parse error for %r: %s", syn.term, e)

            logger.info("Library %r loaded: %d sections, %d clauses, FAISS=%s, TF-IDF=%s",
                library.naam, len(ctx.policy_sections), len(ctx.standard_clauses),
                ctx.has_faiss, ctx.has_tfidf)
            return ctx
        finally:
            session.close()

    @staticmethod
    def _to_dict(library):
        """Serialize ProductLibrary ORM object to dict for API responses."""
        return {
            "id": library.id, "naam": library.naam,
            "verzekeraar": library.verzekeraar, "versie": library.versie,
            "beschrijving": library.beschrijving, "status": library.status,
            "aangemaakt_door": library.aangemaakt_door,
            "aangemaakt_op": library.aangemaakt_op.isoformat() if library.aangemaakt_op else None,
            "bijgewerkt_op": library.bijgewerkt_op.isoformat() if library.bijgewerkt_op else None,
            "build_progress": library.build_progress,
            "build_message": library.build_message,
            "section_count": library.section_count,
            "clause_count": library.clause_count,
        }
