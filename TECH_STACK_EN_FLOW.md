## 🧱 Technische Stack & Analyseflow - Hienfeld VB Converter

### 1. Techstack (overzicht)

- **Talen**
  - **Python** 3.10+ (backend/analysis)
  - **TypeScript** (React-frontend)

- **Frontend & UI**
  - **React + Vite + TypeScript** (`src/`) – floating-glass-converter frontend
  - **shadcn-ui / Tailwind CSS** – modern Hienfeld UI (floating glass look)
  - Single Page App – hoofdpagina in `src/pages/Index.tsx`

- **Backend & Domein**
  - **FastAPI** (`hienfeld_api/app.py`) – REST-API voor analyse, status, resultaten, rapport-download
  - **Domain & services** (`hienfeld/`) – bestaande OOP/MVC-logica:
    - `Services` → Innemen, normaliseren, clusteren, analyseren, exporteren
    - `Domain` → Domeinmodellen (`Clause`, `Cluster`, `PolicyDocumentSection`, `AnalysisAdvice`, `StandardClause`)

- **Data & bestanden**
  - **pandas** – DataFrames, CSV/Excel in- en uitlezen
  - **openpyxl** – Excel export (rapporten)
  - **xlsxwriter** – Excel export in `clausulebibliotheek/word_to_excel.py`

- **Document parsing (voorwaarden / clausules)**
  - **python-docx** – Lezen van `.docx`-documenten
  - **win32com.client** (alleen in `clausulebibliotheek/word_to_excel.py`) – Lezen van oude `.doc`-bestanden via een lokale Word-installatie (Windows-only helpertool)
  - **PyMuPDF** (`fitz`) – Primair PDF-leeswerk in `PolicyParserService`
  - **pdfplumber** – Fallback PDF-parser
  - **Eigen text-normalisatie** – `hienfeld/utils/text_normalization.py` (regex + `unicodedata` voor lowercasing, accents, spaties, etc.)

- **Similariteit, clustering & analyse**
  - **rapidfuzz** – Snelle fuzzy string matching (similarity scores)  
  - **difflib** – Fallback similarity (standaardbibliotheek)
  - **numpy** – Vector-bewerkingen, cosine similarity
  - **Leader Clustering** – Eigen implementatie in `ClusteringService`
  - **Keyword rules & thresholds** – Geconfigureerd in `hienfeld/config.py`

- **Semantische analyse (v3.0 - geen externe API's)**
  - **spacy** – NLP voor Nederlands (lemmatisering, keyword extractie)
  - **gensim** – TF-IDF voor document similarity
  - **wn** (Open Dutch WordNet) – Synoniemenexpansie
  - **HybridSimilarityService** – Combineert 5 matching-methoden met gewichten
  - **50+ verzekeringstermen** – Domein-specifieke synoniemendatabase

- **(Optionele) AI / Embeddings / Vector search**
  - **sentence-transformers** – Tekst-embeddings (SemanticSimilarityService, EmbeddingsService)
  - **faiss-cpu** – Vector store voor snelle nearest-neighbour search (FaissVectorStore)
  - **openai** – Voorbereid LLM-integratie (LLM-analyse, semantic verificatie)
  - **Eigen AI-services** – in `hienfeld/services/ai` (`embeddings_service.py`, `vector_store.py`, `rag_service.py`, `llm_analysis_service.py`)

- **Logging & utils**
  - Custom logging-config in `hienfeld/logging_config.py`
  - CSV/encoding-detectie in `hienfeld/utils/csv_utils.py`
  - Rate limiting & retries voor LLM-calls in `hienfeld/utils/rate_limiter.py`

- **Externe helpertool (clausulebibliotheek)**
  - Script `clausulebibliotheek/word_to_excel.py` om Word-clausules (DOC/DOCX) om te zetten naar een Excel-bibliotheek met kolommen `Code` / `Tekst` / `Categorie`.

---

### 2. End-to-end procesflow (van start tot eindrapport)

Onderstaande beschrijving volgt de echte code-flow van de applicatie.

#### 2.1 Start van de app

1. **Startcommando's**
   - Backend (FastAPI):
     - `uvicorn hienfeld_api.app:app --reload --port 8000`
   - Frontend (React/Vite):
     - `npm install`
     - `npm run dev` → `http://localhost:5173/`

2. **Initialisatie in backend (`hienfeld_api/app.py`)**
   - FastAPI app wordt geïnitialiseerd.
   - `load_config()` uit `hienfeld/config.py` → laad (standaard)config in een `AppConfig`-object (gebruikt door services).
   - Analysejobs worden beheerd in-memory (job_id, status, progress, resultaten, Excel-rapport).

3. **Domeinservices (ongewijzigd)**
   - `IngestionService` – CSV/Excel inlezen
   - `PreprocessingService` – teksten normaliseren + `Clause`-objecten maken
   - `PolicyParserService` – voorwaarden/clausules uit PDF/DOCX/TXT halen
   - `MultiClauseDetectionService` – detectie multi-clausules / "brei"
   - `ClusteringService` – Leader clustering met fuzzy similarity
   - `AdminCheckService` – hygiëne-checks (lege teksten, datums etc.)
   - `AnalysisService` – waterfall-analyse pipeline (Step 0–3)
   - `ExportService` – bouwt DataFrames + Excel-rapport

#### 2.2 Inputfase (linkerkolom)

4. **Upload polisbestand (verplicht)**
   - `file_upload_section()` component rendert upload zone.
   - Gebruiker kiest een **Excel/CSV** met vrije teksten.
   - `HienfeldState.handle_policy_upload()` event handler:
     - Leest bestand als base64
     - Slaat op in `HienfeldState.policy_file_name`, `policy_file_content`
     - Update status message

5. **Upload voorwaarden (optioneel, maar functioneel sterk aangeraden)**
   - `conditions_upload_section()` component met checkbox voor modus.
   - Mogelijke input:
     - Polisvoorwaarden als **PDF**, **DOCX** of **TXT**
     - Meerdere bestanden mogelijk
   - `HienfeldState.handle_conditions_upload()` event handler:
     - Slaat alle bestanden op als base64 arrays
   - Zonder voorwaarden:
     - `HienfeldState.use_conditions = False`
     - De app draait in **interne analyse modus** (geen verwijder-adviezen op basis van dekking in voorwaarden).

6. **Upload clausulebibliotheek (optioneel)**
   - `clause_library_upload_section()` component.
   - Ondersteunde formaten:
     - CSV / Excel met kolommen `Code`, `Tekst`, `Categorie`
     - PDF / Word met clausulecodes in de tekst
   - `HienfeldState.handle_clause_library_upload()` event handler:
     - Laadt bestand direct in `ClauseLibraryService`
     - Berekent stats en toont in UI

7. **Extra instructie (optioneel)**
   - `extra_instruction_section()` component.
   - Tekstveld voor bijvoorbeeld: "Let extra op asbestclausules".
   - Opgeslagen in `HienfeldState.extra_instruction`.
   - (Nu vooral UI; kan worden gebruikt voor AI/LLM-uitbreidingen.)

8. **Start-knop**
   - `start_button()` component.
   - Disabled als `HienfeldState.can_start_analysis == False` (geen policy file).
   - Triggers `HienfeldState.run_analysis()` event handler.
   - Tijdens analyse verschijnt een full-screen **loading overlay** met voortgangsbalk en **annuleer-knop** (`cancel_analysis`). Na afronden is er een prominente **“Nieuwe Analyse”**-knop om alle state te resetten.

#### 2.3 Start van de analyse (`run_analysis`)

Als de gebruiker op **Start Analyse** klikt en een polisbestand is geüpload:

9. **Async event handler met yield**
   - `HienfeldState.run_analysis()` is een `@rx.event` async functie.
   - Gebruikt `yield` statements om UI updates te triggeren tijdens lange operaties.
   - State updates:
     - `HienfeldState.is_analyzing = True`
     - `HienfeldState.analysis_progress = 0`
     - `HienfeldState.analysis_status = "Initialiseren..."`
   - Elke `yield` update de UI zonder de operatie te blokkeren.

10. **Stap 1 – Inlezen polisdata**
    - Services worden geïnstantieerd:
      - `IngestionService`, `PreprocessingService`, etc.
    - `IngestionService.load_policy_file(...)`:
      - Detecteert **filetype** (CSV vs Excel).
      - Voor CSV:
        - Detecteert **encoding** (via `detect_encoding`).
        - Detecteert **delimiter** (`,` / `;` / `\t`).
        - Leest in als `pandas.DataFrame`.
      - Voor Excel:
        - Leest in met `pd.read_excel`.
    - `IngestionService.detect_text_column(df)`:
      - Probeert kolomnamen zoals `Tekst`, `Vrije Tekst`, `Clausule`, etc.
      - Zo niet gevonden → valt terug op de laatste kolom.
    - `IngestionService.detect_policy_number_column(df)`:
      - Zoekt kolommen met namen zoals `polisnummer`, `policy`, `nummer`, `id`.
    - `PreprocessingService.dataframe_to_clauses(...)`:
      - Itereert over elke rij in de DataFrame:
        - Maakt een `Clause` met:
          - `id` → `row_{index}` of `{polisnummer}_{index}`
          - `raw_text` → originele tekst
          - `simplified_text` → genormaliseerde tekst (lowercase, accents weg, etc.)
          - `source_policy_number` en `source_file_name`
      - Filtert lege/zeer korte teksten weg.
    - Progress update: `yield` na stap 1.

11. **Stap 2 – Verwerken voorwaarden (indien aangezet)**
    - Als `HienfeldState.use_conditions` en er zijn condition files:
      - Voor elk bestand:
        - `PolicyParserService.parse_policy_file(file_bytes, filename)`:
          - `.docx`:
            - Leest met `python-docx`, pakt alle paragrafen.
            - Combineert tot één tekst en splitst in artikelen (`Artikel 1`, `Art. 1.1`, etc.) via regex.
          - `.pdf`:
            - Probeert eerst **PyMuPDF (fitz)**:
              - Leest tekst per pagina.
            - Zo nodig fallback naar **pdfplumber**.
            - Segmenteert tekst in `PolicyDocumentSection`-objecten en probeert pagina-nummers te koppelen.
          - `.txt`:
            - Probeert meerdere encodings, leest volledige tekst, splitst in artikelen via regex.
      - Uitkomst is een lijst `PolicyDocumentSection`-objecten:
        - `id` (bijv. `Art 2.8` of `DOC-1`)
        - `title`, `raw_text`, `simplified_text`, optioneel `page_number`
    - Zonder voorwaarden:
      - `policy_sections = []`
      - Analyse draait dan puur intern (clustering, frequentie, keyword-regels).
    - Progress update: `yield` na stap 2.

12. **Stap 3 – Clustering (Leader algorithm)**
    - `ClusteringService.cluster_clauses(clauses)`:
      1. Sorteert alle `Clause`-objecten op lengte (langste eerst).
      2. Loopt één keer door de lijst:
         - Sla **hele korte** teksten over (markeer als `NVT`).
         - **Exact-match cache** op `simplified_text`.
         - **Genormaliseerde-match cache** via `normalize_for_clustering()` (vangt adres/bedrag/datum-varianten, drempel iets lager dan hoofdthreshold).
         - Vergelijkt anders met de **recentste clusters** (window, configureerbaar via slider + toggle “geen limiet”):
           - RapidFuzz similarity + **length-tolerance** guard.
           - Tweede poging met genormaliseerde leader-tekst.
         - Als similarity ≥ threshold:
           - Voeg de tekst toe als member van de bestaande cluster.
         - Anders:
           - Maak een **nieuwe cluster** (`id = "CL-0001"`, `"CL-0002"`, …) met deze tekst als `leader_clause`.
      3. Uitkomst:
         - Lijst met `Cluster`-objecten (met leader + members + frequency).
         - Mapping `clause_id -> cluster_id`.
    - Progress update: `yield` na clustering.

13. **Stap 4 – Waterfall analyse-pipeline (AnalysisService)**
    - `AnalysisService.analyze_clusters(clusters, policy_sections, progress_callback=None)` voert de 4-staps "waterfall" uit:

    **Stap 0 – Admin check (hygiëne)**
    - `AdminCheckService.check_cluster(cluster)` controleert o.a.:
      - Lege teksten
      - Placeholder-teksten
      - Datumvelden (verjaard/ouddatum)
      - Overduidelijke invoerfouten
    - Als er een admin-issue is:
      - Direct een `AnalysisAdvice` met adviezen als:
        - **OPSCHONEN** / **AANVULLEN** / **VERWIJDEREN** (admin-redenen)
      - Pipeline stopt voor deze cluster (verder niet langs Step 1–3).

    **Pre-checks**
    - Te korte tekst → automatisch **HANDMATIG CHECKEN** (te weinig info).
    - Multi-clause/brei-detectie:
      - Zoekt codepatroon `\b[0-9][A-Z]{2}[0-9]\b` (bijv. `9NX3`).
      - Als:
        - Meer dan 1 unieke code én
        - Tekst langer dan `BREI_MIN_LENGTH` (800 tekens)
      - Dan advies: **SPLITSEN** (lange breitekst met meerdere clausules).

    **Stap 1 – Clausulebibliotheek-check**
    - Als een clausulebibliotheek is geladen:
      - `clause_library_service.find_match(cluster.leader_text)` zoekt de best passende standaardclausule.
      - Beslissing:
        - Score ≥ 95% → advies **"🔄 VERVANGEN"**:
          - Vervang door standaardclausule met code (bijv. `9NX3`).
        - Score tussen 85–95% → advies **"🔍 CONTROLEER GELIJKENIS"**:
          - Lijkt sterk op standaardclausule, handmatig beoordelen.
        - Lagere scores → geen advies, ga door naar Stap 2.

    **Stap 2 – Voorwaarden-check (is tekst al gedekt?)**
    - Beschikbaar wanneer voorwaarden (policy sections) zijn geladen.
    - **v3.0: Hybrid Similarity Matching** (5 gecombineerde methoden):
      1. **Exacte substring-match**:
         - Als de vereenvoudigde tekst exact voorkomt in de gecombineerde voorwaarden:
           - Advies: **VERWIJDEREN** (hoog vertrouwen, "EXACT").
      2. **Fuzzy match per artikel/sectie (RapidFuzz + gewichten)**:
         - **RapidFuzz** (25%): Letterlijke tekstgelijkenis
         - **Lemmatized** (20%): Genormaliseerde woordvormen via SpaCy
           - "auto's verzekerd" → "auto verzekeren"
         - **TF-IDF** (15%): Keyword-belangrijkheid via Gensim
         - **Synonyms** (15%): Domein-specifieke termen
           - "auto" ↔ "voertuig", "verzekerd" ↔ "gedekt"
         - **Embeddings** (25%): Semantische betekenis
         - **Weighted score** berekend per `PolicyDocumentSection`:
           - ≥ 90% → **VERWIJDEREN** (bijna letterlijk, hoog vertrouwen).
           - 80–90% → **VERWIJDEREN** met review (middel vertrouwen).
           - 70–80% → **HANDMATIG CHECKEN** (mogelijke variant).
      3. **Fragment-matching**:
         - Splitst de vrije tekst in zinnen.
         - Als meerdere zinnen letterlijk terugkomen in voorwaarden:
           - Advies: **VERWIJDEREN** (teksten redundante herhaling van voorwaarden).
      4. **Semantische matching (Step 2b, optioneel)**:
         - Embeddings indexeert alle artikelen; zoekt semantisch gelijkende secties.
         - **>=80%** zonder LLM → direct **VERWIJDEREN** (semantisch identiek).
         - **>=70%** → advies met LLM-verificatie indien geconfigureerd; anders **HANDMATIG CHECKEN** met verwijzing naar artikel.

    **Stap 3 – Fallback / interne analyse**
    - Als er geen match is in bibliotheek of voorwaarden:
      - **Lengte-check**:
        - Zeer lange teksten → **SPLITSEN_CONTROLEREN** (mogelijk meerdere onderwerpen).
      - **Keyword rules (config-gedreven)**:
        - Voorbeelden:
          - `fraude` → vaak **VERWIJDEREN** (reeds geregeld in voorwaarden).
          - `rangorde` → **VERWIJDEREN** als standaardbepaling.
          - `molest` + "inclusief/meeverzekerd" → **BEHOUDEN (CLAUSULE)** (afwijking van standaard).
      - **Frequentie-analyse**:
        - Frequentie ≥ drempel (`frequency_standardize_threshold`, default 20):
          - Advies **STANDAARDISEREN**: maak hier een standaardclausule van.
        - Lager dan drempel maar >1:
          - Diverse adviescodes rond consistentie en frequentie-info.
      - **AI-analyse (indien geconfigureerd)**:
        - `ai_analyzer.analyze_cluster_with_context(...)` kan LLM gebruiken voor extra classificatie.
      - **Multi-clause handling**:
        - Bij detectie van brei wordt de tekst gesplitst in subsegmenten; per segment wordt een eigen advies berekend.
        - Output bevat hiërarchische **PARENT** + **CHILD** rijen, waarbij de parent een samenvatting van kind-adviezen toont (bijv. “⚠️ GESPLITST – 2x VERWIJDEREN, 1x HANDMATIG”).
      - **Laatste fallback**:
        - Zonder voorwaarden:
          - Unieke of weinig voorkomende teksten → **UNIEK**, **CONSISTENTIE_CHECK** of `FREQUENTIE_INFO`.
        - Met voorwaarden:
          - Geen automatische match → **HANDMATIG CHECKEN** (mogelijke maatwerkclausule).

    - Progress updates: `yield` elke 10 clusters tijdens analyse.

14. **Stap 5 – Resultaten verzamelen en statistieken**
    - Na analyse:
      - `advice_map`: mapping `cluster_id -> AnalysisAdvice`.
      - `ExportService.get_statistics_summary(...)`:
        - Totaal aantal rijen
        - Aantal clusters
        - Reductiepercentage (hoeveel unieke clusters t.o.v. rijen)
        - Aantal multi-clause gevallen
        - Verdeling per adviescode en categorie
    - State updates:
      - `HienfeldState.results_ready = True`
      - `HienfeldState.statistics` → `StatisticsModel` object
      - `HienfeldState.results_data` → List van result dicts
    - `metrics_section()` component toont kerncijfers bovenin de resultatenkolom.
    - `advice_distribution_chart()` component toont een grafiek met de adviesverdeling.

15. **Stap 6 – Bouw van het Excel-rapport**
    - `ExportService.to_excel_bytes(...)`:
     - Bouwt DataFrame met alle resultaten (hiërarchisch PARENT/CHILD indien gesplitst).
     - Export naar Excel via `pd.ExcelWriter(engine='openpyxl')`.
     - **Dual-sheet export (v2.2)**:
       - `Analyseresultaten` → enkelvoudige clusters zonder splits-adviezen.
       - `Te Splitsen & Complex` → PARENT/CHILD rijen en alle SPLITSEN/SPLITSEN_CONTROLEREN adviezen.
     - Optioneel: `Cluster Samenvatting` sheet met kerncijfers per cluster.
    - Excel wordt opgeslagen als base64 in `HienfeldState.excel_data_base64`.
    - `results_table()` component toont download button met data URL.

16. **Stap 7 – Resultatentabel in de UI**
    - `HienfeldState.display_results` (computed var) → eerste 10 resultaten.
    - `results_table()` component:
      - Toont een compacte tabel in de rechterkolom met:
        - Cluster-ID, -naam, frequentie
        - Analyse-advies, vertrouwen, reden, artikel
        - Originele tekst (of voorbeeld)
      - Bij complexe/multi-clause-resultaten kan gebruik worden gemaakt van een parent/child-structuur.
    - Download button prominent bovenaan.

17. **State persistence**
    - Reflex State blijft behouden tijdens de sessie.
    - Geen page reloads nodig (anders dan Streamlit).
    - State wordt automatisch gesynchroniseerd tussen frontend en backend.
    - `HienfeldState.reset_analysis()` kan worden gebruikt om state te wissen voor nieuwe analyse.

---

### 3. Projectstructuur (na Reflex migratie)

```
Vb agent/
├── rxconfig.py                    # Reflex configuratie
├── requirements.txt               # Dependencies (reflex>=0.6.0)
├── README.md                      # Gebruikersdocumentatie
├── TECH_STACK_EN_FLOW.md         # Deze technische documentatie
│
├── hienfeld_app/                 # Reflex UI applicatie
│   ├── __init__.py
│   ├── hienfeld_app.py           # Main app entry (rx.App)
│   ├── state.py                  # HienfeldState (vervangt controller)
│   ├── styles.py                 # Hienfeld Design System
│   └── components/               # Modulaire UI componenten
│       ├── __init__.py
│       ├── header.py             # Header met logo en help
│       ├── sidebar.py            # Instellingen sidebar
│       ├── file_upload.py        # Upload componenten
│       ├── progress.py           # Progress indicator
│       ├── metrics.py            # Statistieken cards
│       └── results_table.py     # Resultaten tabel
│
├── hienfeld/                     # Backend package (ONGEWIJZIGD)
│   ├── __init__.py
│   ├── config.py                 # Configuratie
│   ├── logging_config.py        # Logging setup
│   ├── domain/                   # Domeinmodellen
│   │   ├── clause.py
│   │   ├── cluster.py
│   │   ├── analysis.py
│   │   ├── policy_document.py
│   │   └── standard_clause.py
│   ├── services/                 # Business logic
│   │   ├── ingestion_service.py
│   │   ├── preprocessing_service.py
│   │   ├── policy_parser_service.py
│   │   ├── clustering_service.py
│   │   ├── analysis_service.py
│   │   ├── export_service.py
│   │   ├── clause_library_service.py
│   │   ├── similarity_service.py
│   │   ├── admin_check_service.py
│   │   ├── multi_clause_service.py
│   │   ├── nlp_service.py          # NEW v3.0: SpaCy NLP
│   │   ├── synonym_service.py      # NEW v3.0: Synoniemen
│   │   ├── document_similarity_service.py  # NEW v3.0: TF-IDF
│   │   ├── hybrid_similarity_service.py    # NEW v3.0: Hybrid matching
│   │   └── ai/                   # AI extensies (optioneel)
│   │       ├── embeddings_service.py
│   │       ├── vector_store.py
│   │       ├── rag_service.py
│   │       └── llm_analysis_service.py
│   ├── data/                      # NEW v3.0: Data files
│   │   └── insurance_synonyms.json  # 50+ verzekeringstermen
│   ├── utils/                    # Hulpfuncties
│   │   ├── text_normalization.py
│   │   ├── csv_utils.py
│   │   └── rate_limiter.py
│   ├── prompts/                  # LLM prompts (optioneel)
│   │   ├── admin_prompt.py
│   │   ├── compliance_prompt.py
│   │   ├── sanering_prompt.py
│   │   └── semantic_match_prompt.py
│   └── ui/                       # Leeg (oude Streamlit code verwijderd)
│       └── __init__.py           # Migratie notities
│
├── assets/                       # Static files voor Reflex
│   └── hienfeld-logo.png
│
└── clausulebibliotheek/         # Helper scripts
    ├── word_to_excel.py
    └── [voorbeelddata bestanden]
```

---

### 4. Belangrijke wijzigingen t.o.v. Streamlit versie

#### 4.1 State Management
- **Voorheen:** `HienfeldController` met `st.session_state` caching
- **Nu:** `HienfeldState` (Reflex State class) met automatische frontend/backend sync
- **Voordelen:**
  - Geen page reloads nodig
  - State blijft behouden tijdens sessie
  - Automatische UI updates bij state changes

#### 4.2 Async Processing
- **Voorheen:** `progress_callback` functies die Streamlit UI updates triggeren
- **Nu:** `@rx.event` async functies met `yield` statements
- **Voordelen:**
  - UI blijft volledig responsief tijdens lange analyses
  - Real-time progress updates zonder blocking
  - Betere UX voor AI/LLM calls (toekomst)

#### 4.3 Component Architectuur
- **Voorheen:** Monolithische `HienfeldView` class met alle UI rendering
- **Nu:** Modulaire componenten in `hienfeld_app/components/`
- **Voordelen:**
  - Betere code organisatie
  - Herbruikbare componenten
  - Makkelijker te onderhouden en uitbreiden

#### 4.4 File Handling
- **Voorheen:** Streamlit `UploadedFile` objecten direct gebruiken
- **Nu:** Base64 encoding in state voor serialisatie
- **Voordelen:**
  - State kan worden geserialiseerd
  - Betere compatibiliteit met Reflex state management

#### 4.5 Design System
- **Voorheen:** CSS in `_apply_styles()` methode
- **Nu:** Gestructureerde styles in `hienfeld_app/styles.py`
- **Voordelen:**
  - Centrale plek voor alle styling
  - Makkelijker aan te passen
  - Consistent design door hele app

---

### 5. Samenvatting in één zin

De Hienfeld VB Converter leest eerst polis- en voorwaardenbestanden in via een moderne Reflex UI, normaliseert en clustert alle vrije teksten met een Leader-algoritme (met real-time progress updates), laat daar een meerstaps waterfall-analyse (admin-check, clausulebibliotheek, voorwaarden, keywords/frequentie/AI) op los via async event handlers, en levert tenslotte een gestructureerd Excel-rapport plus interactief dashboard waarmee analisten snel kunnen zien welke teksten verwijderd, gesplitst, gestandaardiseerd of handmatig beoordeeld moeten worden.

---

## 6. Semantic Enhancement Details (v3.0)

### 6.1 Hybrid Similarity Architecture

De nieuwe `HybridSimilarityService` combineert 5 matching-methoden:

```
┌────────────────────────────────────────────┐
│ Layer 5: Sentence Embeddings (25%)        │ ← Semantische betekenis
├────────────────────────────────────────────┤
│ Layer 4: Synoniemen Database (15%)        │ ← "auto" = "voertuig"
├────────────────────────────────────────────┤
│ Layer 3: Lemmatisering (20%)              │ ← "verzekerd" = "verzekeren"
├────────────────────────────────────────────┤
│ Layer 2: TF-IDF Document Similarity (15%) │ ← Keyword overlap
├────────────────────────────────────────────┤
│ Layer 1: RapidFuzz (25%)                  │ ← Letterlijke match
└────────────────────────────────────────────┘
                    ↓
            Weighted Score (0.0 - 1.0)
```

### 6.2 Synoniemendatabase

50+ verzekeringsterm-groepen in `hienfeld/data/insurance_synonyms.json`:
- **Voertuigen:** auto, voertuig, personenauto, wagen, motorvoertuig
- **Woningen:** huis, pand, woonhuis, gebouw, opstal
- **Verzekerd:** gedekt, meeverzekerd, verzekerde
- **Schade:** beschadiging, letsel, verlies, averij
- **Eigen risico:** franchise, eigenrisico, drempel
- En 45+ andere groepen voor complete dekking

### 6.3 Performance Impact

| Component | Extra tijd | Voordeel |
|-----------|------------|----------|
| SpaCy lemmatization | +10-15s | +10-15% betere matches |
| Synoniemen lookup | +5s | +15-20% betere matches |
| TF-IDF training | +10-20s | +5-10% snellere matching |
| Embeddings (optioneel) | +20-30s | +10-15% parafrase-herkenning |
| **Totaal** | **+30-60s** | **+15-25% automatische matches** |

### 6.4 Installatie Semantic Features

```bash
# Basis installatie (altijd)
pip install -r requirements.txt

# SpaCy Nederlands model (aanbevolen)
python -m spacy download nl_core_news_md

# Open Dutch WordNet (optioneel, auto-download)
# Wordt automatisch gedownload bij eerste gebruik
```

### 6.5 Configuratie

In `hienfeld/config.py`:

```python
@dataclass
class SemanticConfig:
    enabled: bool = True
    enable_embeddings: bool = True
    enable_nlp: bool = True
    enable_tfidf: bool = True
    enable_synonyms: bool = True
    
    # Gewichten (som = 1.0)
    weight_rapidfuzz: float = 0.25
    weight_lemmatized: float = 0.20
    weight_tfidf: float = 0.15
    weight_synonyms: float = 0.15
    weight_embeddings: float = 0.25
```

---

*Laatste update: v3.0.0 - Semantic Enhancement (2025)*
