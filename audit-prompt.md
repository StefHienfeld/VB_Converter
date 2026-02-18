# 🔍 VB Converter – Volledige App Audit & Verbeterplan

## Context

Je bent een senior software architect die een volledige audit uitvoert op de **Hienfeld VB Converter** app. Dit is een corporate tool voor verzekeringsanalisten die vrije polisteksten automatisch analyseert, clustert, vergelijkt met referentiebestanden (polisvoorwaarden) en acties/adviezen genereert (VERWIJDEREN, SPLITSEN, STANDAARDISEREN, BEHOUDEN, HANDMATIG CHECKEN).

### Projectlocatie
- **Pad:** `C:\Users\Stef\Desktop\Vb agent`
- **Repo:** https://github.com/StefHienfeld/VB_Converter

### Huidige tech stack
- **Backend:** Python (Reflex framework + FastAPI REST API)
- **Frontend:** React/Vite/TypeScript + shadcn-ui + Tailwind CSS (Lovable-project)
- **NLP/ML:** SpaCy (nl_core_news_md), RapidFuzz, Gensim TF-IDF, Sentence-transformers, Open Dutch WordNet
- **Clustering:** Leader algorithm
- **Parsing:** PyMuPDF/pdfplumber voor PDF, python-docx voor DOCX
- **Export:** Excel (openpyxl)
- **Optionele AI:** OpenAI/Anthropic LLM integratie

### Bekende pijnpunten
1. **Snelheid:** Analyse kan tot ~1 uur duren bij grote bestanden
2. **Kwaliteit:** De matching en clustering kunnen waarschijnlijk beter met nieuwere modellen/methodes
3. **Security & compliance:** Moet corporate-ready zijn (data privacy, geen lekkage, audit trails)
4. **Frontend:** Twee frontend-systemen naast elkaar (Reflex + React/Lovable) — moet gestroomlijnd worden
5. **Algemeen:** De app moet production-grade worden voor een corporate omgeving

---

## Opdracht

Voer een **volledige audit** uit in de volgende 6 domeinen en schrijf per domein een gedetailleerd verbeterplan met concrete acties, prioriteiten (P0/P1/P2), en geschatte effort.

### Gebruik een Agent Team met de volgende structuur:

Maak een agent team aan met **5 gespecialiseerde teammates + 1 lead**:

```
Maak een agent team aan voor een volledige audit van deze codebase.

TEAM LEAD (jij): Coördineer de audit, synthetiseer resultaten, schrijf het finale rapport.

TEAMMATE 1 — "NLP & Quality Analyst":
- Analyseer alle NLP/ML pipelines in hienfeld\services\
- Benchmark de huidige matching-methoden (RapidFuzz, SpaCy lemma, TF-IDF, embeddings, synoniemen)
- Onderzoek of er betere modellen/libraries bestaan voor:
  * Nederlandse tekst embeddings (bijv. multilingual-e5-large, BGE-M3, Cohere embed v4, of nieuwere)
  * Clustering (HDBSCAN, agglomerative clustering vs huidige Leader algorithm)
  * Fuzzy matching (bijv. polyfuzz, thefuzz met process extractOne)
  * Semantic similarity (cross-encoders voor re-ranking na bi-encoder retrieval)
- Evalueer of een RAG-pipeline (Retrieval Augmented Generation) met een LLM de kwaliteit van voorwaarden-matching drastisch kan verbeteren
- Onderzoek of fine-tuning van een klein model op verzekeringstaal meerwaarde heeft
- Lever op: docs\quality_audit.md met benchmarks, aanbevelingen, en een migratieplan

TEAMMATE 2 — "Performance Engineer":
- Profile de volledige analyse-pipeline: waar zit de bottleneck?
- Meet actual tijden per stap (ingestion, preprocessing, clustering, matching, export)
- Onderzoek verbeteringen:
  * Batch processing & async/parallel execution
  * Caching van embeddings (FAISS/Annoy/Qdrant in-memory)
  * Lazy loading van NLP modellen
  * Vectorized operaties (numpy/polars i.p.v. pandas loops)
  * Pre-computed embedding indices voor referentiebestanden
  * Incremental analysis (alleen gewijzigde teksten heranalyseren)
  * GPU-acceleratie voor embeddings (als beschikbaar)
- Lever op: docs\performance_audit.md met profiling data, bottleneck analyse, en optimalisatieplan

TEAMMATE 3 — "Security & Compliance Specialist":
- Audit alle bestanden op security issues:
  * Hardcoded API keys of secrets
  * Input validation & sanitization (file uploads, tekstvelden)
  * Dependency vulnerabilities (pip-audit, safety check)
  * OWASP top 10 check voor de FastAPI endpoints
  * CORS configuratie
  * Rate limiting
  * Data-at-rest en data-in-transit encryptie
- Compliance check:
  * AVG/GDPR readiness (data minimalisatie, recht op verwijdering, geen onnodig loggen van persoonsgegevens)
  * Is er een DPIA nodig? (check TECHSTACK_DPIA.md)
  * Audit logging (wie deed wat wanneer)
  * Data retention policies
  * Toegangscontrole / authenticatie / autorisatie
- Corporate readiness:
  * Secrets management (env vars, vault)
  * CI/CD pipeline security
  * Container security (als Docker wordt gebruikt)
  * Pen-test readiness
- Lever op: docs\security_audit.md met findings (severity: CRITICAL/HIGH/MEDIUM/LOW), fixes, en compliance checklist

TEAMMATE 4 — "Frontend & UX Architect":
- Analyseer de huidige frontend situatie:
  * Er zijn TWEE frontend systemen: Reflex (Python) en React/Vite/Lovable in src\
  * Bepaal welke de primaire moet worden en waarom
  * Evalueer of een migratie naar één framework nodig is
- UX audit:
  * User flow analyse (upload → config → analyse → resultaat → download)
  * Accessibility (WCAG 2.1 AA)
  * Responsive design
  * Error handling & user feedback
  * Loading states & progress indicators
  * Dark mode / theming
- Frontend architectuur:
  * Component structuur en herbruikbaarheid
  * State management
  * API layer (error handling, retries, caching)
  * Type safety (TypeScript strictheid)
  * Bundle size & performance (lighthouse audit)
  * Testing (unit, integration, e2e)
- Design system:
  * Consistentie met Hienfeld Design System
  * Component library evaluatie
- Lever op: docs\frontend_audit.md met wireframes/suggesties, UX verbeteringen, en architectuurplan

TEAMMATE 5 — "DevOps & Architecture Reviewer":
- Code kwaliteit & architectuur:
  * Evalueer de huidige MVC/DDD structuur
  * Identificeer code smells, dead code, duplicatie
  * Test coverage analyse
  * Documentatie completheid
  * Error handling consistentie
  * Logging strategie
- DevOps & deployment:
  * CI/CD pipeline (GitHub Actions of alternatives)
  * Docker/containerisatie
  * Environment management (dev/staging/prod)
  * Monitoring & alerting
  * Health checks
  * Backup strategie
  * Rollback mechanisme
- Dependency management:
  * Verouderde dependencies identificeren
  * Onnodige dependencies verwijderen
  * Lock files consistentie (requirements.txt vs package-lock.json vs bun.lockb — waarom zijn er 3?)
  * Python version pinning
- Schaalbaarheid:
  * Kan de app meerdere gebruikers tegelijk aan?
  * Queue-based processing voor lange analyses
  * Horizontal scaling mogelijkheden
- Lever op: docs\architecture_audit.md met dependency graph, tech debt lijst, en moderniseringsplan
```

---

## Specifieke instructies voor de audit

### 1. Begin met het lezen van de volledige codebase
```
Lees eerst CLAUDE.md, README.md, TECHSTACK_DPIA.md, en CUSTOM_INSTRUCTIONS_DEBUG.md.
Lees daarna de volledige directory structuur.
Lees vervolgens de key files:
- hienfeld\config.py (configuratie)
- hienfeld\services\ (alle services)
- hienfeld\domain\ (domeinmodellen)
- hienfeld_api\app.py (API endpoints)
- src\ (React frontend)
- requirements.txt en package.json (dependencies)
- tests\ (bestaande tests)
```

### 2. Gebruik subagents voor deep-dive research
```
Gebruik subagents om de volgende vragen te beantwoorden:
1. Wat zijn de BESTE Nederlandse tekst embedding modellen in februari 2026?
2. Wat zijn de snelste vector similarity search libraries voor Python?
3. Wat zijn de beste practices voor RAG pipelines in een verzekerings-domein?
4. Welke OWASP vulnerabilities zijn het meest relevant voor file-upload applicaties?
5. Wat zijn de nieuwste React patterns voor file-processing dashboards?
```

### 3. Output format
```
Schrijf het finale rapport als docs\AUDIT_REPORT.md met:

# VB Converter Audit Report
**Datum:** [datum]
**Versie:** v3.0.0 → v4.0.0 roadmap

## Executive Summary
[2-3 alinea's met de belangrijkste bevindingen en aanbevelingen]

## 1. NLP & Analyse Kwaliteit
### Huidige staat
### Bevindingen
### Aanbevelingen (P0/P1/P2)
### Migratieplan

## 2. Performance
### Huidige staat (met profiling data)
### Bottleneck analyse
### Optimalisatieplan (P0/P1/P2)
### Geschatte verbetering per optimalisatie

## 3. Security & Compliance
### Findings (CRITICAL/HIGH/MEDIUM/LOW)
### AVG/GDPR Compliance Status
### Remediation plan
### Corporate readiness checklist

## 4. Frontend & UX
### Huidige staat
### Framework beslissing (met onderbouwing)
### UX verbeteringen
### Implementatieplan

## 5. Architectuur & DevOps
### Code quality metrics
### Tech debt inventory
### CI/CD plan
### Moderniseringsroadmap

## 6. Prioritized Roadmap
### Phase 1: Quick Wins (week 1-2) — P0 items
### Phase 2: Core Improvements (week 3-6) — P1 items
### Phase 3: Excellence (week 7-12) — P2 items

## Appendix
### A. Dependency update matrix
### B. Security findings detail
### C. Performance profiling raw data
### D. Recommended tech stack changes
```

### 4. Aanvullende checks
```
Controleer ook:
- Of de Reflex framework nog actief onderhouden wordt en of migratie nodig is
- Of er betere alternatieven zijn voor Gensim (bijv. scikit-learn TfidfVectorizer is sneller)
- Of sentence-transformers het beste model gebruikt voor Nederlands (check MTEB leaderboard)
- Of de Excel export vervangen kan worden door iets snellers (bijv. xlsxwriter)
- Of er een betere PDF parser is dan PyMuPDF (bijv. docling, marker, pymupdf4llm)
- Of de synoniemen-database uitgebreid kan worden met een LLM-gegenereerde thesaurus
- Of WebSocket gebruikt kan worden voor real-time progress updates i.p.v. polling
- Of de app als Docker container geleverd kan worden voor eenvoudige deployment
```

---

## Belangrijk: Stijl & Taal

- Schrijf het rapport in het **Nederlands** (technische termen mogen in het Engels)
- Wees **concreet**: geen vage adviezen, maar specifieke libraries, versies, en code-voorbeelden
- Wees **eerlijk**: als iets goed is, zeg dat ook. Niet alles hoeft veranderd te worden
- Geef bij elke aanbeveling een **effort-schatting** (S/M/L/XL) en **impact-schatting** (laag/midden/hoog)
- Gebruik **tabellen** voor overzichtelijke vergelijkingen

---

## Na de audit

Als het rapport klaar is, maak dan ook:
1. **docs\MIGRATION_GUIDE.md** — Stap-voor-stap migratie handleiding voor de belangrijkste veranderingen
2. **docs\ARCHITECTURE_V4.md** — Doelarchitectuur voor v4.0 met diagrammen (mermaid)
3. **.github\workflows\ci.yml** — Basis CI pipeline als die nog niet bestaat
4. **Dockerfile** — Als containerisatie wordt aanbevolen
5. **Update CLAUDE.md** — Met de nieuwe architectuurbeslissingen en conventies
