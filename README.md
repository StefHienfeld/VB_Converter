# 🛡️ Hienfeld VB Converter

**Automatisch vrije teksten analyseren en standaardiseren.**

Deze applicatie helpt business analisten bij het analyseren, clusteren en opschonen van duizenden vrije polisteksten. Met behulp van slimme algoritmes worden teksten gegroepeerd en getoetst aan de nieuwe polisvoorwaarden.

---

## 🚀 Snel Starten

### 1. Vereisten
Zorg dat **Python 3.10+** geïnstalleerd is op je computer.

### 2. Installatie

```bash
# Navigeer naar het project
cd "pad/naar/Vb agent"

# Installeer dependencies
pip install -r requirements.txt
```

### 3. Starten

```bash
python -m reflex run
```

De app opent automatisch in je webbrowser op **http://localhost:3000/**

---

## 📖 Hoe werkt het?

### Stap 1: Upload Polisbestand
Sleep je Excel- of CSV-export met vrije teksten in het eerste vak. De tool herkent automatisch kolommen zoals 'Tekst' of 'Vrije Tekst'.

### Stap 2: Upload Voorwaarden & Clausules ⚠️ **KRITIEK!**

> **Dit is de belangrijkste stap!** De tool vergelijkt elke vrije tekst tegen de geüploade voorwaarden om te bepalen of de tekst al gedekt is.

*   Sleep de polisvoorwaarden (PDF, Word of TXT) in het tweede vak
*   Je kunt ook clausulebladen/aanhangsels apart uploaden
*   **Hoe completer de voorwaarden, hoe beter de analyse!**

⚠️ **Zonder voorwaarden kan de tool niet bepalen welke teksten verwijderd kunnen worden!**

### Stap 3: Instellingen & Instructie
*   **Cluster Nauwkeurigheid:** Via het menu links kun je instellen hoe streng de clustering moet zijn (80-100%).
*   **Min. Frequentie:** Bepaal wanneer een tekst als "standaard" wordt gezien.
*   **Window Size:** Beperk het aantal clusters waartegen vergeleken wordt (voor snelheid).

### Stap 4: Analyse & Resultaat
Klik op **START ANALYSE**. De tool gaat nu aan het werk:

1.  **Clustering:** Teksten die op elkaar lijken worden samengevoegd
2.  **Voorwaarden Check:** ✅ **Elke tekst wordt vergeleken met de voorwaarden!**
    - Exacte match? → **VERWIJDEREN**
    - Zeer vergelijkbaar (>85%)? → **VERWIJDEREN** (met controle-advies)
    - Vergelijkbaar (>75%)? → **HANDMATIG CHECKEN**
3.  **Multi-Clausule Detectie:** Herkent teksten met meerdere clausules → **SPLITSEN**
4.  **Frequentie Check:** Vaak voorkomende teksten → **STANDAARDISEREN**

### Stap 5: Download
Als de analyse klaar is, verschijnt er een tabel. Klik op **Download Rapport (Excel)** om de resultaten als Excel-bestand te krijgen.

---

## 💡 Tips voor de Analist

| Advies | Betekenis | Actie |
|--------|-----------|-------|
| **VERWIJDEREN** | Tekst komt (bijna) letterlijk voor in de voorwaarden | ✅ Verwijderen na steekproef |
| **⚠️ SPLITSEN** | Tekst bevat meerdere clausulecodes (bijv. 9NX3 én 9NY3) | ✂️ Handmatig splitsen |
| **🛠️ STANDAARDISEREN** | Tekst komt vaak voor (>20x) | 📋 Standaard clausulecode maken |
| **BEHOUDEN (CLAUSULE)** | Specifieke afwijking van voorwaarden (bijv. molest meeverzekerd) | ✋ Behouden als maatwerk |
| **HANDMATIG CHECKEN** | Geen automatische match gevonden | 👁️ Handmatig beoordelen |

### Vertrouwensniveaus

| Niveau | Betekenis |
|--------|-----------|
| **Hoog** | Sterke match (>95%), veilig om te verwijderen |
| **Midden** | Vergelijkbaar (85-95%), controleer voor verwijderen |
| **Laag** | Mogelijk gerelateerd, handmatige beoordeling nodig |

---

## 🏗️ Architectuur

De applicatie volgt een **MVC-achtige architectuur** met domeingedreven OOP:

```
Vb agent/
├── hienfeld_app/       # Reflex UI applicatie
│   ├── components/    # UI componenten
│   ├── state.py       # State management
│   └── styles.py      # Hienfeld Design System
├── hienfeld/          # Backend package
│   ├── domain/        # Domeinmodellen (Clause, Cluster, AnalysisAdvice)
│   ├── services/      # Business logic services
│   │   ├── ai/        # AI-extensies (optioneel)
│   │   └── ...
│   ├── utils/         # Hulpfuncties
│   └── config.py      # Configuratie
├── assets/            # Static files (logo, etc.)
└── clausulebibliotheek/ # Helper scripts
```

### Componenten

| Component | Verantwoordelijkheid |
|-----------|---------------------|
| **HienfeldState** (`hienfeld_app/state.py`) | Application state & async processing |
| **Components** (`hienfeld_app/components/`) | Reflex UI components |
| **IngestionService** | CSV/Excel inlezen |
| **PreprocessingService** | Tekstnormalisatie |
| **PolicyParserService** | PDF/DOCX/TXT parsing |
| **ClusteringService** | Leader algorithm clustering |
| **AnalysisService** | Regelgebaseerde analyse |
| **ExportService** | Excel export |

---

## 🔧 Configuratie

Alle instellingen zijn configureerbaar via `hienfeld/config.py`:

```python
# Voorbeeld: Clustering instellingen aanpassen
from hienfeld.config import load_config

config = load_config()
config.clustering.similarity_threshold = 0.85  # Minder streng
config.clustering.leader_window_size = 200     # Grotere window
```

### Belangrijke configuratie-opties

| Instelling | Default | Beschrijving |
|------------|---------|--------------|
| `similarity_threshold` | 0.90 | Minimale gelijkenis voor clustering |
| `leader_window_size` | 100 | Aantal clusters om te vergelijken |
| `frequency_standardize_threshold` | 20 | Min. frequentie voor STANDAARDISEREN |
| `max_text_length` | 1000 | Lengte waarboven SPLITSEN advies |

---

## 🤖 AI-Extensies (Optioneel)

De tool is voorbereid voor AI-integratie:

### Embeddings & Vector Search
```bash
pip install sentence-transformers faiss-cpu
```

### LLM Analyse
```bash
pip install openai  # of anthropic
```

Configureer in `config.py`:
```python
config.ai.enabled = True
config.ai.embedding_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

---

## 🛠️ Ontwikkeling

### Project structuur
```
Vb agent/
├── rxconfig.py           # Reflex configuratie
├── requirements.txt      # Dependencies
├── hienfeld_app/         # Reflex UI applicatie
│   ├── hienfeld_app.py   # Main app entry
│   ├── state.py          # State management
│   └── components/      # UI componenten
├── hienfeld/             # Backend package
│   ├── domain/           # Domeinmodellen
│   ├── services/         # Business logic
│   └── utils/           # Hulpfuncties
└── assets/              # Static files
```

---

## 📊 Technische Info

*   **Framework:** Reflex (Python full-stack)
*   **Architectuur:** MVC + Domain-Driven Design
*   **Algoritmes:** Leader Clustering, Fuzzy Matching (RapidFuzz)
*   **Veiligheid:** De tool draait lokaal. Geen data verlaat de Hienfeld-omgeving.

---

## 📜 Changelog

### v3.0.0 (2025) - Reflex Migration
- 🎨 **Migratie naar Reflex framework**
  - Moderne full-stack Python framework
  - Async processing voor responsieve UI
  - Persistent state management
  - Hienfeld Design System volledig behouden
- ⚡ Verbeterde performance tijdens lange analyses
- 🎯 Betere UX met real-time progress updates

### v2.1.0 (2025) - ⚠️ KRITIEKE UPDATE
- 🔥 **FIX: Voorwaarden worden nu DAADWERKELIJK gebruikt!**
  - Exacte substring matching in voorwaarden
  - Fuzzy matching per artikel/sectie (RapidFuzz)
  - Fragment-gebaseerde matching voor langere teksten
- 📊 Nieuwe metrics: "Te Verwijderen" count in dashboard
- ⚠️ Waarschuwing als geen voorwaarden zijn geüpload
- 📈 Configureerbare similarity thresholds (95%/85%/75%)

### v2.0.0 (2025)
- ✨ Complete architectuur refactoring naar OOP + MVC
- 🏗️ Domeinmodellen: Clause, Cluster, PolicyDocumentSection, AnalysisAdvice
- 🔧 Configureerbare services met dependency injection
- 📄 Echte PDF-parsing (PyMuPDF/pdfplumber)
- 🤖 AI-ready interfaces voor embeddings en LLM
- 📊 Verbeterde statistieken en export

### v1.0.0 (2024)
- 🚀 Eerste versie met basis clustering en analyse

---

*Versie 3.0 - Hienfeld - 2025*
