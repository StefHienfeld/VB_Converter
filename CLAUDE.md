
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Hienfeld VB Converter** - A dual-stack application for analyzing and standardizing insurance policy text clauses. The system uses hybrid similarity matching (5 methods: fuzzy, lemmatization, synonyms, TF-IDF, embeddings) to cluster duplicate clauses and compare them against policy conditions.

## Technology Stack

### Frontend (Primary UI)
- **React + Vite + TypeScript** (`src/`)
- **shadcn-ui + Tailwind CSS** for UI components
- **TanStack Query** for data fetching
- Main entry: `src/pages/Index.tsx`
- API client: `src/lib/api.ts`

### Backend
- **FastAPI** (`hienfeld_api/app.py`) - REST API server
- **Python 3.10+** analysis pipeline (`hienfeld/`)
- **Domain-driven OOP architecture** with services pattern

### Key Dependencies
- **pandas** - Data processing (CSV/Excel)
- **RapidFuzz** - Fast fuzzy string matching
- **SpaCy** (nl_core_news_md) - NLP lemmatization
- **scikit-learn** - TF-IDF document similarity (v4.3: replaced gensim, 2-3x faster)
- **sentence-transformers** - Semantic embeddings
- **PyMuPDF/pdfplumber** - PDF parsing
- **python-docx** - DOCX parsing

## Development Commands

### Frontend Development
```bash
# Install dependencies
npm install

# Start dev server (http://localhost:8080)
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Backend Development
```bash
# Install Python dependencies
pip install -r requirements.txt

# Download Dutch NLP model (required for semantic features)
python -m spacy download nl_core_news_md

# Start FastAPI server (http://localhost:8000)
uvicorn hienfeld_api.app:app --reload --port 8000

# Alternative: Run legacy Reflex UI (optional)
python -m reflex run
```

### Running the Full Stack
1. Terminal 1: `uvicorn hienfeld_api.app:app --reload --port 8000`
2. Terminal 2: `npm run dev`
3. Frontend connects to backend via `http://localhost:8000/api/...`

## Architecture Overview

### Core Analysis Pipeline (hienfeld/)

The analysis flows through 6 main stages:

**1. Ingestion** (`IngestionService`)
- Reads Excel/CSV policy files
- Auto-detects encoding and text columns
- Creates `Clause` domain objects

**2. Policy Parsing** (`PolicyParserService`)
- Parses PDF/DOCX/TXT policy documents
- Extracts articles/sections into `PolicyDocumentSection` objects
- Uses PyMuPDF (primary) and pdfplumber (fallback) for PDFs

**3. Clustering** (`ClusteringService`)
- Leader algorithm with window-based comparison (default: 100 clusters)
- Three-tier matching strategy:
  1. Exact match cache on `simplified_text`
  2. Normalized match (strips amounts, dates, addresses)
  3. Fuzzy similarity with RapidFuzz (default: 90% threshold)
- Length tolerance guard (20%) to avoid false positives
- Groups similar clauses into `Cluster` objects

**4. Analysis** (`AnalysisService`)
- Waterfall pipeline with 5 steps:
  - **Step 0:** Admin hygiene checks (empty text, placeholders, dates)
  - **Step 0.5:** Custom instructions check (user-defined rules) - **NEW (v4.2)**
  - **Step 1:** Clause library matching (95%+ = REPLACE, 85-95% = CHECK)
  - **Step 2:** Policy conditions matching (uses HybridSimilarityService)
  - **Step 3:** Fallback rules (keywords, frequency, length checks)
- Produces `AnalysisAdvice` with action recommendations

**5. Length Check** (in `AnalysisService`)
- **CHANGED (v4.0):** Multi-clause detection and splitting removed
- Long texts (>800 chars, configurable via `max_text_length`) receive "HANDMATIG CHECKEN" advice
- No automatic splitting - collega handles manually

**6. Export** (`ExportService`)
- Generates single-sheet Excel reports:
  - "Analyseresultaten" - all analysis results (one row per input row)
  - Optional "Cluster Samenvatting" - summary statistics
- **CHANGED (v4.0):** No more dual-sheet architecture or PARENT/CHILD splitting
- **NEW (v4.1):** Unieke teksten groepering - singletons (freq=1) grouped by Advies+Vertrouwen
  - Reduces cluster count by 70-80% without quality loss
  - Example: UNIEK-VERWIJDEREN-Hoog (80 texts), UNIEK-HANDMATIG CHECKEN-Midden (280 texts)
  - Individual analyses preserved, only presentation grouped
  - See `UNIEKE_TEKSTEN_FEATURE.md` for details
- Includes Status column for manual tracking
- Semantic cluster names via NLP noun phrase extraction
- Article titles included in references (max 80 chars)

### Hybrid Similarity Matching (v3.1 - Performance Optimized)

Located in `hienfeld/services/hybrid_similarity_service.py`. Combines 5 methods with mode-specific weighted scoring.

**Available Analysis Modes** (configured in `hienfeld/config.py` - `SemanticConfig.mode_configs`):

1. **FAST** (~4s for 1660 rows) - `time_multiplier: 0.05`
   - RapidFuzz (60%) + Lemmatized (40%)
   - No embeddings, TF-IDF, or synonyms
   - Best for: Quick analysis, simple datasets, <1000 rows

2. **BALANCED** (~10min for 1660 rows) - `time_multiplier: 1.0` ⭐ RECOMMENDED
   - RapidFuzz (30%) + Lemmatized (25%) + Embeddings (15%) + TF-IDF (15%) + Synonyms (15%)
   - **skip_embeddings_threshold: 0.85** (v3.2 - skip embeddings if RapidFuzz >= 85%)
   - Best for: Most datasets, good quality/speed balance

3. **ACCURATE** (~25min for 1660 rows) - `time_multiplier: 2.5`
   - RapidFuzz (20%) + Lemmatized (20%) + Embeddings (30%) + TF-IDF (15%) + Synonyms (15%)
   - **skip_embeddings_threshold: 0.92** (uses embeddings more often for max accuracy)
   - Best for: Complex datasets, maximum accuracy needed

**Performance Optimization Strategy (v3.2)**:
- Embeddings are expensive (~5-10ms per comparison)
- BALANCED: Skip embeddings when RapidFuzz >= 85% (saves ~35% embedding calls)
- ACCURATE: Skip embeddings when RapidFuzz >= 92% (max quality, more embedding usage)
- Embeddings most valuable in 70-85% similarity range (catches paraphrases)
- Insurance clauses often use standard phrasing -> high RapidFuzz, embeddings less needed

**Configuration:** `hienfeld/config.py` - `SemanticConfig` dataclass

**Synonym Database:** `hienfeld/data/insurance_synonyms.json` (50+ term groups)

### Policy Embeddings Cache (v4.4 - NEW)

Located in `hienfeld/services/ai/policy_embeddings_cache.py`. Caches pre-computed embeddings for policy documents to avoid recomputation on repeated analyses.

**Impact:**
- **Time saved:** ~20-30 seconds per analysis (when using same policy documents)
- **Hit rate:** 80-95% for typical workflows (same voorwaarden PDFs)
- **Memory:** ~2-5 MB per cached document (depends on section count)

**How it works:**
1. When policy sections are indexed, a content-based hash (SHA256) is computed
2. If the hash matches a cached entry, embeddings are reused
3. If no match, embeddings are computed and cached for next time
4. Cache key includes model name (different models have separate caches)

**API Endpoints:**
- `GET /api/cache/embeddings/stats` - Get cache statistics (hits, misses, time saved)
- `POST /api/cache/embeddings/clear` - Clear the embeddings cache

**Usage:**
The cache is automatically used by `RAGService` and `SemanticSimilarityService`.
No code changes needed - just enable semantic analysis.

**Configuration:**
```python
# RAGService (enabled by default)
rag = RAGService(embeddings_service, vector_store, enable_embedding_cache=True)

# SemanticSimilarityService (enabled by default)
semantic = SemanticSimilarityService(enable_policy_cache=True)
```

### Domain Models (hienfeld/domain/)

- **Clause** - Individual policy text with raw/simplified versions
- **Cluster** - Group of similar clauses with leader + members
- **PolicyDocumentSection** - Article/section from policy documents
- **AnalysisAdvice** - Recommendation (REMOVE/REPLACE/KEEP/MANUAL/etc.)
- **StandardClause** - Reference clause from library

### Service Layer Pattern

All services follow dependency injection:
```python
service = ServiceClass(config=config, logger=logger)
```

Critical services:
- `HybridSimilarityService` - Main similarity engine (v3.0)
- `ClusteringService` - Leader algorithm implementation
- `AnalysisService` - Waterfall analysis pipeline
- `PolicyParserService` - Document parsing (PDF/DOCX/TXT)
- `ClauseLibraryService` - Standard clause matching

## Configuration

Central config in `hienfeld/config.py` using dataclasses:

**ClusteringConfig:**
- `similarity_threshold` (default: 0.90) - Minimum similarity for clustering
- `leader_window_size` (default: 100) - Max clusters to compare against
- `length_tolerance` (default: 0.20) - Length difference threshold

**SemanticConfig:**
- `enabled` - Toggle hybrid similarity (default: True)
- `weight_*` - Adjust method weights (sum must = 1.0)
- `enable_nlp/tfidf/synonyms/embeddings` - Toggle individual methods

**AnalysisRuleConfig:**
- `frequency_standardize_threshold` (default: 20) - Min frequency for standardization
- `keyword_rules` - Dict mapping keywords to advice logic
- `conditions_match.exact_match_threshold` (default: 0.95)

## API Endpoints (hienfeld_api/app.py)

**POST /api/analyze**
- Accepts: `policy_file`, `conditions_files[]`, `clause_library_files[]`, form params
- Returns: `{job_id, status}`
- Starts background analysis job

**GET /api/status/{job_id}**
- Returns: `{status, progress, stats, error?}`
- Poll every 1.5s for updates

**GET /api/results/{job_id}**
- Returns: `{results: AnalysisResultRow[], stats}`
- Available when status = "completed"

**GET /api/report/{job_id}**
- Returns: Excel file download
- Filename: "Hienfeld_Analyse.xlsx"

## Frontend State Management

Main state in `src/pages/Index.tsx`:
- `policyFile` - Required policy data
- `conditionsFiles[]` - Optional policy conditions
- `clauseLibraryFiles[]` - Optional clause library
- `settings` - Cluster accuracy, min frequency, window size, AI enabled
- `jobId` - Background job tracker
- `results` - Analysis results array
- `stats` - Summary statistics

Progress tracking:
- 4-step UI progress (Inlezen → Analyseren → Clusteren → Resultaten)
- Backend progress mapped to UI steps (0-20%, 20-60%, 60-90%, 95%+)
- 10-minute timeout protection with cancellation

## Important Patterns

### File Upload Flow
1. User uploads file → Stored in React state as `File` object
2. On "Start Analyse" → Build `FormData` with actual file objects
3. POST to `/api/analyze` → FastAPI receives `UploadFile`
4. Backend saves to temp files → Processes → Deletes temp files

### Analysis Progress Updates
- Backend updates `job.progress` (0-100) during analysis
- Frontend polls `/api/status/{job_id}` every 1.5s
- UI maps progress to step status (pending/active/completed)

### Error Handling
- Network errors: Check if backend is running at `http://localhost:8000`
- Timeout errors: 10-minute max polling time (models may download on first run)
- API errors: Extract `detail` from response JSON

### Clause Library Service
- Accepts CSV/Excel (Code, Tekst, Categorie columns) or PDF/DOCX
- Builds index of standard clauses for matching
- Used in Analysis Step 1 (before policy conditions check)

## Testing Considerations

When testing analysis:
1. First run may take 2-3 minutes (SpaCy model loading)
2. Requires policy file minimum (conditions optional but recommended)
3. Check logs in backend terminal for detailed progress
4. Large files (>5000 rows) may take 5-10 minutes

## Common Tasks

### Adjust Similarity Thresholds
Edit `hienfeld/config.py`:
```python
class ConditionsMatchConfig:
    exact_match_threshold: float = 0.95  # Very similar → REMOVE
    high_similarity_threshold: float = 0.85  # Similar → REMOVE with check
    medium_similarity_threshold: float = 0.75  # Maybe similar → MANUAL
```

### Add New Keyword Rule
Edit `hienfeld/config.py` → `AnalysisRuleConfig.keyword_rules`:
```python
'new_keyword': {
    'keywords': ['keyword1', 'keyword2'],
    'advice': 'BEHOUDEN (MAATWERK)',
    'reason': 'Explanation',
    'confidence': 'Hoog'
}
```

### Modify Hybrid Weights
Edit `hienfeld/config.py` → `SemanticConfig`:
```python
weight_rapidfuzz: float = 0.25
weight_lemmatized: float = 0.20
weight_tfidf: float = 0.15
weight_synonyms: float = 0.15
weight_embeddings: float = 0.25
# Sum must equal 1.0
```

### Debug Analysis Results
1. Check FastAPI logs: `uvicorn hienfeld_api.app:app --reload --log-level debug`
2. Inspect intermediate results in `ExportService.to_dataframe()`
3. Add breakpoints in `AnalysisService._analyze_single_cluster()`

### Custom Instructions Feature (v4.2 - Enhanced)

Users can provide custom analysis rules via the "Extra instructies" field in the UI.

**NEW (v4.2): Table-based UI**
- The UI now provides a user-friendly table editor with columns: **Tekst** (search) and **Actie** (action)
- Automatically serializes to TSV format (`zoektekst<TAB>actie`) for backend
- No need to type arrows or special syntax
- Component: `src/components/upload/ExtraInstructionInput.tsx`

**Input Formats (both supported):**

1. **TSV/Table format (recommended):**
   ```
   meeverzekerde	Vullen in partijenkaart
   sanctieclausule	Verwijderen - mag weg
   ```

2. **Arrow format (backwards compatible):**
   ```
   meeverzekerde ondernemingen
   → Vullen in partijenkaart
   
   sanctieclausule
   → Verwijderen
   ```

**Matching Strategy (v4.2 - "both" mode):**

1. **Fast contains check (first, always active):**
   - Case-insensitive substring matching
   - If search text is found in clause → perfect match (score 1.0)
   - Works in ALL analysis modes (FAST/BALANCED/ACCURATE)
   - Primary method for table-based instructions

2. **Semantic/fuzzy fallback:**
   - Hybrid similarity (if available in BALANCED/ACCURATE mode)
   - Semantic embeddings (if available)
   - Fuzzy text matching (always available)
   - Thresholds: fuzzy 0.65, semantic 0.60

**Backend Implementation:**
- Service: `hienfeld/services/custom_instructions_service.py`
- Integration: Analysis Step 0.5 (before library/conditions check)
- Works in all analysis modes (FAST uses contains + fuzzy only)
- API parameter: `extra_instruction` (string, TSV or arrow format)

**Output:**
- When matched, advice code: `📋 {action}` (e.g., `📋 Vullen in partijenkaart`)
- Reason: `Komt overeen met instructie: '{search_text}' (100% match)` for contains matches

**Logging:**
```
✅ Custom instructions loaded: 3 regels
✅ Custom instruction match (contains): '...' -> 'Vullen in partijenkaart'
Step 0.5 - Custom instructions: 12 matches
```

## File Structure Reference

```
VB_Converter/
├── src/                          # React frontend
│   ├── pages/Index.tsx          # Main UI page
│   ├── lib/api.ts               # API client
│   ├── components/              # UI components
│   └── types/analysis.ts        # TypeScript types
├── hienfeld/                     # Python analysis package
│   ├── domain/                  # Domain models
│   ├── services/                # Business logic
│   │   ├── analysis_service.py
│   │   ├── clustering_service.py
│   │   ├── hybrid_similarity_service.py
│   │   └── ai/                  # Optional AI services
│   ├── data/
│   │   └── insurance_synonyms.json
│   ├── config.py                # Configuration
│   └── utils/                   # Utilities
├── hienfeld_api/                # FastAPI server
│   └── app.py                   # API endpoints
├── package.json                 # Node dependencies
├── requirements.txt             # Python dependencies
├── vite.config.ts              # Vite configuration
└── tailwind.config.ts          # Tailwind CSS config
```

## Notes

- The codebase uses Dutch variable names and documentation (insurance domain language)
- Backend is stateless - all job state stored in-memory (restart clears jobs)
- Frontend talks to backend via REST API only (no WebSockets)
- Semantic features (v3.0) require SpaCy model: `python -m spacy download nl_core_news_md`
- All NLP/ML processing is local (no external API calls required)
- Optional OpenAI integration available but not required for core functionality

## Audit Context (februari 2026)

We voeren een volledige app-audit uit. Belangrijke richtlijnen:

### Taal
- Alle documentatie en rapporten in het Nederlands
- Technische termen mogen in het Engels
- Code comments in het Engels

### Audit conventies
- Findings altijd met severity: CRITICAL / HIGH / MEDIUM / LOW
- Aanbevelingen altijd met prioriteit: P0 (must-have) / P1 (should-have) / P2 (nice-to-have)
- Effort-schatting: S (< 1 dag) / M (1-3 dagen) / L (3-5 dagen) / XL (> 5 dagen)
- Impact-schatting: laag / midden / hoog

### Bestaande architectuur
- Backend: Python 3.10+ met Reflex + FastAPI
- Frontend: React/Vite/TypeScript (Lovable) + Reflex UI
- NLP: SpaCy, RapidFuzz, Gensim, Sentence-transformers
- Dit is een CORPORATE tool — security en compliance zijn essentieel

### Paden
- Project root: C:\Users\Stef\Desktop\Vb agent
- Backend services: hienfeld\services\
- Frontend (React): src\
- API: hienfeld_api\app.py
- Tests: tests
