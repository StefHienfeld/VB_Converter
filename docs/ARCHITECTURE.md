# Architectuur Overzicht

Dit document beschrijft de technische architectuur van de VB Converter applicatie.

---

## Inhoudsopgave

1. [High-Level Overzicht](#high-level-overzicht)
2. [Component Beschrijvingen](#component-beschrijvingen)
3. [Data Flow](#data-flow)
4. [API Endpoints](#api-endpoints)
5. [Database Schema](#database-schema)
6. [Deployment Architectuur](#deployment-architectuur)

---

## High-Level Overzicht

### Systeem Diagram

```
+------------------------------------------------------------------+
|                        VB CONVERTER SYSTEEM                       |
+------------------------------------------------------------------+

                    +------------------+
                    |     GEBRUIKER    |
                    +--------+---------+
                             |
                             | HTTPS
                             v
+------------------------------------------------------------------+
|                         FRONTEND LAAG                             |
+------------------------------------------------------------------+
|                                                                    |
|  +------------------------------------------------------------+   |
|  |                 React/Vite Frontend                         |   |
|  |  +----------+  +----------+  +----------+  +----------+    |   |
|  |  |  Upload  |  |  Status  |  | Results  |  | Settings |    |   |
|  |  |  Page    |  |  Tracker |  |  Table   |  |  Panel   |    |   |
|  |  +----------+  +----------+  +----------+  +----------+    |   |
|  |                                                             |   |
|  |  TanStack Query | shadcn-ui | Tailwind CSS | TypeScript    |   |
|  +------------------------------------------------------------+   |
|                                                                    |
+-----------------------------+--------------------------------------+
                              |
                              | REST API (JSON)
                              | http://localhost:8000/api/...
                              v
+------------------------------------------------------------------+
|                         BACKEND LAAG                              |
+------------------------------------------------------------------+
|                                                                    |
|  +------------------------------------------------------------+   |
|  |                    FastAPI Application                       |   |
|  |  +----------+  +----------+  +----------+  +----------+    |   |
|  |  | Analyze  |  |  Status  |  | Results  |  |  Report  |    |   |
|  |  | Endpoint |  | Endpoint |  | Endpoint |  | Download |    |   |
|  |  +----------+  +----------+  +----------+  +----------+    |   |
|  +-----------------------------+-------------------------------+   |
|                                |                                   |
|  +-----------------------------v-------------------------------+   |
|  |                    MIDDLEWARE                                |   |
|  |  Security Headers | Rate Limiting | CORS | Request Logging  |   |
|  +------------------------------------------------------------+   |
|                                                                    |
+-----------------------------+--------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                       SERVICE LAAG                                |
+------------------------------------------------------------------+
|                                                                    |
|  +------------------------------------------------------------+   |
|  |                    Analysis Pipeline                         |   |
|  |                                                              |   |
|  |  1. INGESTION        2. PARSING          3. CLUSTERING      |   |
|  |  +--------------+    +--------------+    +--------------+   |   |
|  |  | Excel/CSV    |    | PDF/DOCX/TXT |    | Leader Algo  |   |   |
|  |  | Reader       |--->| Parser       |--->| + Fuzzy      |   |   |
|  |  +--------------+    +--------------+    +--------------+   |   |
|  |         |                  |                   |             |   |
|  |         v                  v                   v             |   |
|  |  4. ANALYSIS         5. MATCHING          6. EXPORT         |   |
|  |  +--------------+    +--------------+    +--------------+   |   |
|  |  | Waterfall    |<---| Hybrid       |    | Excel        |   |   |
|  |  | Pipeline     |    | Similarity   |--->| Generator    |   |   |
|  |  +--------------+    +--------------+    +--------------+   |   |
|  |                                                              |   |
|  +------------------------------------------------------------+   |
|                                                                    |
|  +------------------------------------------------------------+   |
|  |                   NLP/ML COMPONENTEN                         |   |
|  |  +----------+  +----------+  +----------+  +----------+    |   |
|  |  | SpaCy    |  |  TF-IDF  |  |Embeddings|  | Synonyms |    |   |
|  |  |nl_core_md|  |sklearn   |  |  e5-large|  |  WordNet |    |   |
|  |  +----------+  +----------+  +----------+  +----------+    |   |
|  +------------------------------------------------------------+   |
|                                                                    |
+-----------------------------+--------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                       DATA LAAG                                   |
+------------------------------------------------------------------+
|                                                                    |
|  +--------------------+    +--------------------+                  |
|  |    PostgreSQL      |    |   In-Memory Cache  |                  |
|  |  +------------+    |    |  +------------+    |                  |
|  |  | jobs       |    |    |  | Embeddings |    |                  |
|  |  | audit_log  |    |    |  | TF-IDF     |    |                  |
|  |  +------------+    |    |  | Fuzzy      |    |                  |
|  +--------------------+    +--------------------+                  |
|                                                                    |
+------------------------------------------------------------------+
```

### Technologie Stack

| Laag | Technologie | Versie |
|------|-------------|--------|
| **Frontend** | React + TypeScript | 18.3 |
| | Vite (bundler) | 5.4 |
| | shadcn-ui + Tailwind | 3.4 |
| | TanStack Query | 5.x |
| **Backend** | FastAPI | 0.115+ |
| | Python | 3.10+ |
| | Uvicorn (ASGI) | 0.30+ |
| **NLP** | SpaCy (nl_core_news_md) | 3.7+ |
| | sentence-transformers | 3.0+ |
| | scikit-learn (TF-IDF) | 1.3+ |
| | RapidFuzz | 3.0+ |
| **Database** | PostgreSQL | 16+ |
| | SQLAlchemy | 2.0+ |
| | Alembic (migrations) | 1.13+ |
| **Document Parsing** | PyMuPDF | 1.23+ |
| | pdfplumber | 0.10+ |
| | python-docx | 0.8+ |

---

## Component Beschrijvingen

### Frontend (src/)

```
src/
+-- pages/
|   +-- Index.tsx              # Hoofdpagina met upload/analyse flow
+-- components/
|   +-- upload/
|   |   +-- FileUpload.tsx     # Drag-drop bestand upload
|   |   +-- FileList.tsx       # Lijst van geuploade bestanden
|   +-- analysis/
|   |   +-- ProgressTracker.tsx # 4-staps voortgang indicator
|   |   +-- SettingsPanel.tsx   # Analyse configuratie
|   +-- results/
|   |   +-- ResultsTable.tsx    # Resultaten tabel
|   |   +-- ExportButton.tsx    # Excel download
|   +-- ui/                     # shadcn-ui componenten
+-- lib/
|   +-- api.ts                  # API client (fetch wrapper)
|   +-- utils.ts                # Helper functies
+-- types/
    +-- analysis.ts             # TypeScript interfaces
```

**Key Components:**

| Component | Verantwoordelijkheid |
|-----------|---------------------|
| `Index.tsx` | State management, orchestratie |
| `FileUpload.tsx` | File handling, validatie |
| `ProgressTracker.tsx` | Real-time status polling |
| `ResultsTable.tsx` | Resultaten weergave, filtering |

### Backend API (hienfeld_api/)

```
hienfeld_api/
+-- app.py                      # FastAPI applicatie entry point
+-- auth.py                     # JWT authenticatie
+-- middleware.py               # Security headers, rate limiting
+-- validation.py               # Pydantic request/response models
+-- routes/
|   +-- auth.py                 # Login/logout endpoints
+-- orchestrators/
|   +-- analysis_orchestrator.py # Coordineert analyse pipeline
+-- repositories/
|   +-- job_repository.py       # Abstract repository interface
|   +-- memory_job_repository.py # In-memory implementatie
|   +-- sql_job_repository.py   # PostgreSQL implementatie
+-- factories/
    +-- service_factory.py      # Dependency injection
```

### Analysis Pipeline (hienfeld/)

```
hienfeld/
+-- domain/                     # Domain models (POJOs)
|   +-- clause.py               # Clause, SimplifiedClause
|   +-- cluster.py              # Cluster (leader + members)
|   +-- analysis.py             # AnalysisAdvice, AnalysisResult
|   +-- policy.py               # PolicyDocumentSection
+-- services/
|   +-- ingestion_service.py    # Excel/CSV inlezen
|   +-- policy_parser_service.py # PDF/DOCX parsing
|   +-- clustering_service.py   # Leader algorithm
|   +-- analysis_service.py     # Waterfall analyse
|   +-- hybrid_similarity_service.py # 5-method matching
|   +-- export_service.py       # Excel generatie
|   +-- ai/
|       +-- embeddings_service.py    # Sentence embeddings
|       +-- rag_service.py           # Vector retrieval
|       +-- policy_embeddings_cache.py # Embedding cache
+-- config.py                   # Configuratie dataclasses
+-- data/
    +-- insurance_synonyms.json # Domein-specifieke synoniemen
```

---

## Data Flow

### Analyse Pipeline Flow

```
+---------------+     +----------------+     +----------------+
|   STAP 1      |     |    STAP 2      |     |    STAP 3      |
|   INGESTION   |---->|    PARSING     |---->|   CLUSTERING   |
+---------------+     +----------------+     +----------------+
| Input:        |     | Input:         |     | Input:         |
| - Excel/CSV   |     | - PDF files    |     | - List[Clause] |
|               |     | - DOCX files   |     |                |
| Output:       |     | Output:        |     | Output:        |
| - List[Clause]|     | - List[Section]|     | - List[Cluster]|
+---------------+     +----------------+     +----------------+
        |                    |                      |
        v                    v                      v
+------------------------------------------------------------------+
|                        STAP 4: ANALYSIS                           |
+------------------------------------------------------------------+
| Waterfall Pipeline:                                               |
|                                                                   |
| +------------------+                                              |
| | Step 0: Hygiene  |  Leeg? Placeholder? Alleen datum?            |
| +--------+---------+                                              |
|          | niet-admin                                             |
|          v                                                        |
| +------------------+                                              |
| | Step 0.5: Custom |  Match met gebruiker instructies?            |
| | Instructions     |                                              |
| +--------+---------+                                              |
|          | geen match                                             |
|          v                                                        |
| +------------------+                                              |
| | Step 1: Library  |  Match met standaard clausules? (>95%)       |
| +--------+---------+                                              |
|          | geen match                                             |
|          v                                                        |
| +------------------+                                              |
| | Step 2: Conditions| Match met polisvoorwaarden?                 |
| | (Hybrid Match)   |  Gebruikt alle 5 similarity methods          |
| +--------+---------+                                              |
|          | geen match                                             |
|          v                                                        |
| +------------------+                                              |
| | Step 3: Fallback |  Keywords? Frequentie? Lengte?               |
| +------------------+                                              |
|                                                                   |
+------------------------------------------------------------------+
        |
        v
+---------------+
|   STAP 5      |
|    EXPORT     |
+---------------+
| Output:       |
| - Excel file  |
| - JSON data   |
+---------------+
```

### Hybrid Similarity Matching

```
+------------------------------------------------------------------+
|                    HYBRID SIMILARITY ENGINE                       |
+------------------------------------------------------------------+
|                                                                    |
|  Input: (clause_text, condition_text)                             |
|                                                                    |
|  +----------------+                                                |
|  | 1. RapidFuzz   |  Fast fuzzy string matching                   |
|  |    (30%)       |  Token set ratio algorithm                    |
|  +----------------+                                                |
|          |                                                         |
|          v                                                         |
|  +----------------+                                                |
|  | 2. Lemmatized  |  SpaCy lemmatization + fuzzy                  |
|  |    (25%)       |  "verzekering" == "verzekeringen"             |
|  +----------------+                                                |
|          |                                                         |
|          v                                                         |
|  +----------------+  +-- Skip if RapidFuzz > 0.92 (BALANCED)      |
|  | 3. Embeddings  |  |   Skip if RapidFuzz > 0.90 (ACCURATE)      |
|  |    (15%)       |<-+                                            |
|  +----------------+  Uses: multilingual-e5-large                  |
|          |                                                         |
|          v                                                         |
|  +----------------+                                                |
|  | 4. TF-IDF      |  Document term frequency matching             |
|  |    (15%)       |  scikit-learn vectorizer                      |
|  +----------------+                                                |
|          |                                                         |
|          v                                                         |
|  +----------------+                                                |
|  | 5. Synonyms    |  Domain-specific synonym expansion            |
|  |    (15%)       |  insurance_synonyms.json (50+ groups)         |
|  +----------------+                                                |
|          |                                                         |
|          v                                                         |
|  +----------------+                                                |
|  | WEIGHTED SUM   |  final_score = sum(weight_i * score_i)        |
|  +----------------+                                                |
|          |                                                         |
|          v                                                         |
|  Output: similarity_score (0.0 - 1.0)                             |
|                                                                    |
+------------------------------------------------------------------+
```

### API Request Flow

```
+--------+      +-----------+      +------------+      +----------+
| Client |      |  FastAPI  |      | Middleware |      | Handler  |
+---+----+      +-----+-----+      +-----+------+      +----+-----+
    |                 |                  |                  |
    | POST /analyze   |                  |                  |
    |---------------->|                  |                  |
    |                 | Security check   |                  |
    |                 |----------------->|                  |
    |                 |    rate limit    |                  |
    |                 |<-----------------|                  |
    |                 |                  |                  |
    |                 | Route to handler |                  |
    |                 |---------------------------------->|
    |                 |                                    |
    |                 |   Create job, start background     |
    |                 |<----------------------------------|
    | {"job_id": x}   |                  |                  |
    |<----------------|                  |                  |
    |                 |                  |                  |
    | GET /status/x   |                  |                  |
    |---------------->|                  |                  |
    | (polling...)    |                  |                  |
    |                 |                  |                  |
    | GET /results/x  |                  |                  |
    |---------------->|                  |                  |
    | [results]       |                  |                  |
    |<----------------|                  |                  |
```

---

## API Endpoints

### Overzicht

| Methode | Endpoint | Beschrijving | Auth |
|---------|----------|--------------|------|
| `POST` | `/api/analyze` | Start analyse job | Ja |
| `GET` | `/api/status/{job_id}` | Job status opvragen | Ja |
| `GET` | `/api/results/{job_id}` | Resultaten ophalen | Ja |
| `GET` | `/api/report/{job_id}` | Excel download | Ja |
| `GET` | `/api/health` | Health check | Nee |
| `GET` | `/api/health/ready` | Readiness check | Nee |
| `POST` | `/api/auth/login` | JWT token verkrijgen | Nee |
| `POST` | `/api/auth/refresh` | Token vernieuwen | Ja |
| `GET` | `/api/cache/embeddings/stats` | Cache statistieken | Nee |
| `POST` | `/api/cache/embeddings/clear` | Cache legen | Ja |

### Request/Response Voorbeelden

#### POST /api/analyze

**Request:**
```http
POST /api/analyze HTTP/1.1
Content-Type: multipart/form-data
Authorization: Bearer <jwt_token>

--boundary
Content-Disposition: form-data; name="policy_file"; filename="polissen.xlsx"
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
<binary data>
--boundary
Content-Disposition: form-data; name="conditions_files"; filename="voorwaarden.pdf"
Content-Type: application/pdf
<binary data>
--boundary
Content-Disposition: form-data; name="cluster_accuracy"
80
--boundary
Content-Disposition: form-data; name="analysis_mode"
BALANCED
--boundary--
```

**Response:**
```json
{
  "job_id": "abc123-def456",
  "status": "pending",
  "message": "Analyse gestart"
}
```

#### GET /api/status/{job_id}

**Response:**
```json
{
  "job_id": "abc123-def456",
  "status": "processing",
  "progress": 45,
  "stats": {
    "total_rows": 1660,
    "clusters": 234,
    "processed": 750
  }
}
```

#### GET /api/results/{job_id}

**Response:**
```json
{
  "results": [
    {
      "cluster_id": 1,
      "cluster_naam": "Aansprakelijkheid algemeen",
      "frequentie": 45,
      "tekst": "De verzekering dekt...",
      "advies": "VERWIJDEREN",
      "vertrouwen": "Hoog",
      "reden": "Komt overeen met voorwaarden Art. 3.1 (96%)",
      "referentie": "Art. 3.1 - Dekking aansprakelijkheid"
    }
  ],
  "stats": {
    "total_clusters": 234,
    "verwijderen": 89,
    "behouden": 45,
    "handmatig": 100
  }
}
```

---

## Database Schema

### Entity Relationship Diagram

```
+------------------+          +------------------+
|      jobs        |          |    audit_log     |
+------------------+          +------------------+
| PK id (UUID)     |<-------->| PK id (SERIAL)   |
|    user_id       |          |    job_id (FK)   |
|    created_at    |          |    user_id       |
|    completed_at  |          |    timestamp     |
|    ttl_until     |          |    action        |
|    status        |          |    details (JSON)|
|    progress      |          +------------------+
|    results (JSON)|
|    config (JSON) |
|    error_message |
+------------------+
```

### Tabel Definities

```sql
-- Jobs tabel: Analyse taken en resultaten
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE NULL,
    ttl_until TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '24 hours',
    status VARCHAR(50) DEFAULT 'pending',
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    results JSONB NULL,
    config JSONB NOT NULL,
    error_message TEXT NULL,

    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')
    )
);

-- Indexes voor snelle queries
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_ttl ON jobs(ttl_until);

-- Audit log: Compliance en debugging
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    details JSONB,
    ip_address INET,
    user_agent TEXT
);

-- Indexes voor audit queries
CREATE INDEX idx_audit_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_job_id ON audit_log(job_id);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_action ON audit_log(action);

-- Automatic cleanup van verlopen jobs (GDPR)
CREATE OR REPLACE FUNCTION cleanup_expired_jobs()
RETURNS void AS $$
BEGIN
    DELETE FROM jobs WHERE ttl_until < NOW();
END;
$$ LANGUAGE plpgsql;

-- Schedule elke uur (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-jobs', '0 * * * *', 'SELECT cleanup_expired_jobs()');
```

### SQLAlchemy Models

```python
# hienfeld_api/models/job.py
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID, INET
from datetime import datetime, timedelta
import uuid

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    ttl_until = Column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow() + timedelta(hours=24)
    )
    status = Column(String(50), default="pending")
    progress = Column(Integer, default=0)
    results = Column(JSON, nullable=True)
    config = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    user_id = Column(String(255), index=True)
    action = Column(String(100), nullable=False)
    job_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSON)
    ip_address = Column(INET)
    user_agent = Column(Text)
```

---

## Deployment Architectuur

### Development

```
+-------------------+     +-------------------+
|  Frontend (Vite)  |     |  Backend (Uvicorn)|
|  localhost:5173   |---->|  localhost:8000   |
+-------------------+     +-------------------+
         ^                        |
         |                        v
     Browser              +-------------------+
                          |  In-Memory Store  |
                          +-------------------+
```

### Production (Docker)

```
                          +------------------+
                          |     NGINX        |
                          |  (Reverse Proxy) |
                          |   Port 443/80    |
                          +--------+---------+
                                   |
              +--------------------+--------------------+
              |                                         |
              v                                         v
    +-------------------+                    +-------------------+
    |    Frontend       |                    |    Backend        |
    |  (Nginx Static)   |                    |   (Uvicorn x4)    |
    |    Port 3000      |                    |    Port 8000      |
    +-------------------+                    +--------+----------+
                                                      |
                                 +--------------------+--------------------+
                                 |                                         |
                                 v                                         v
                      +-------------------+                    +-------------------+
                      |   PostgreSQL      |                    |   Redis (Cache)   |
                      |    Port 5432      |                    |    Port 6379      |
                      +-------------------+                    +-------------------+
```

### Docker Compose Services

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    environment:
      - VITE_API_URL=/api

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/vb_converter
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: vb_converter
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## Configuratie Referentie

### Analyse Modes

| Mode | Snelheid | Kwaliteit | Use Case |
|------|----------|-----------|----------|
| **FAST** | ~4 sec/1000 rows | Basis | Quick scan, <1000 rows |
| **BALANCED** | ~10 min/1000 rows | Goed | Standaard productie |
| **ACCURATE** | ~25 min/1000 rows | Maximaal | Complexe datasets |

### Similarity Thresholds

| Threshold | Waarde | Actie |
|-----------|--------|-------|
| `exact_match_threshold` | 0.95 | VERWIJDEREN |
| `high_similarity_threshold` | 0.85 | VERWIJDEREN (check) |
| `medium_similarity_threshold` | 0.75 | HANDMATIG CHECKEN |
| `low_threshold` | < 0.75 | BEHOUDEN / Fallback |

### Clustering Parameters

| Parameter | Default | Beschrijving |
|-----------|---------|--------------|
| `similarity_threshold` | 0.90 | Min. similarity voor cluster |
| `leader_window_size` | 100 | Max. clusters om te vergelijken |
| `length_tolerance` | 0.20 | Max. lengte verschil (20%) |

---

## Zie Ook

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [RUNBOOK.md](RUNBOOK.md) - Operations handleiding
- [SECURITY.md](SECURITY.md) - Security procedures
- [ONBOARDING.md](ONBOARDING.md) - Developer onboarding
