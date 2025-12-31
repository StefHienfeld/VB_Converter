# Techstack Overzicht - VB Converter

**Doel:** Compliance check voor DPIA en security review
**Datum:** 2024-12-31
**Versie:** 3.1.0

---

## Samenvatting

| Aspect | Status |
|--------|--------|
| **Externe API's** | OpenAI (optioneel, uit te schakelen) |
| **Data opslag** | Alleen lokaal (geen cloud) |
| **Gebruikersdata** | Wordt niet verzameld |
| **Logging** | Alleen lokaal, geen externe telemetry |

---

## 1. Backend (Python)

### Core Framework
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| FastAPI | >=0.115.0 | REST API server | Nee | MIT |
| Uvicorn | >=0.30.0 | ASGI server | Nee | BSD-3 |
| slowapi | latest | Rate limiting | Nee | MIT |

### Data Processing
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| pandas | >=2.0.0 | Data manipulatie | Nee | BSD-3 |
| openpyxl | >=3.1.0 | Excel lezen | Nee | MIT |
| xlsxwriter | >=3.1.0 | Excel schrijven | Nee | BSD-2 |

### Document Parsing
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| python-docx | >=0.8.11 | Word documenten | Nee | MIT |
| PyMuPDF | >=1.23.0 | PDF parsing | Nee | AGPL-3.0 |
| pdfplumber | >=0.10.0 | PDF text extraction | Nee | MIT |
| pywin32 | >=306 | Windows COM (optioneel) | Nee | PSF |

### NLP & Text Matching (LOKAAL)
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| rapidfuzz | >=3.0.0 | Fuzzy string matching | Nee | MIT |
| spacy | >=3.7.0 | NLP processing | Nee | MIT |
| gensim | >=4.3.0 | Word embeddings | Nee | LGPL-2.1 |
| wn | >=0.9.0 | WordNet (synoniemen) | Nee | MIT |

### AI/ML (LOKAAL)
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| sentence-transformers | >=2.2.0 | Sentence embeddings | Nee* | Apache-2.0 |
| faiss-cpu | >=1.7.4 | Vector similarity search | Nee | MIT |

*\* Download eenmalig model van HuggingFace bij installatie, daarna volledig lokaal*

### AI/LLM (OPTIONEEL - EXTERNE API)
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| openai | >=1.0.0 | GPT API client | **JA** | MIT |

**LET OP:** De OpenAI integratie is **optioneel** en standaard **uitgeschakeld**. Indien ingeschakeld worden clausuleteksten naar OpenAI servers gestuurd voor analyse.

---

## 2. Frontend (TypeScript/React)

### Core Framework
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| React | ^18.3.1 | UI framework | Nee | MIT |
| React DOM | ^18.3.1 | DOM rendering | Nee | MIT |
| React Router DOM | ^6.30.1 | Client-side routing | Nee | MIT |
| TypeScript | ^5.8.3 | Type checking | Nee | Apache-2.0 |

### Build Tools
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| Vite | ^5.4.19 | Build tool & dev server | Nee | MIT |
| Tailwind CSS | ^3.4.17 | CSS framework | Nee | MIT |
| PostCSS | ^8.5.6 | CSS processing | Nee | MIT |
| ESLint | ^9.32.0 | Code linting | Nee | MIT |

### UI Components (Radix UI - headless)
| Library | Doel | Data extern? | Licentie |
|---------|------|--------------|----------|
| @radix-ui/react-* | Accessible UI primitives | Nee | MIT |

Gebruikte Radix componenten: accordion, alert-dialog, checkbox, dialog, dropdown-menu, label, popover, progress, radio-group, scroll-area, select, separator, slider, switch, tabs, toast, toggle, tooltip

### Utilities
| Library | Versie | Doel | Data extern? | Licentie |
|---------|--------|------|--------------|----------|
| @tanstack/react-query | ^5.83.0 | Data fetching/caching | Nee | MIT |
| react-hook-form | ^7.61.1 | Form handling | Nee | MIT |
| zod | ^3.25.76 | Schema validation | Nee | MIT |
| date-fns | ^3.6.0 | Date utilities | Nee | MIT |
| lucide-react | ^0.462.0 | Icons | Nee | ISC |
| recharts | ^2.15.4 | Charts | Nee | MIT |
| sonner | ^1.7.4 | Toast notifications | Nee | MIT |
| clsx | ^2.1.1 | Class names | Nee | MIT |
| tailwind-merge | ^2.6.0 | Tailwind class merging | Nee | MIT |

---

## 3. Data Flow

```
[Gebruiker Browser]
        |
        | HTTP (localhost)
        v
[React Frontend] <-- Geen externe verbindingen
        |
        | HTTP API calls
        v
[FastAPI Backend] <-- Geen externe verbindingen (standaard)
        |
        | Optioneel (indien OpenAI enabled)
        v
[OpenAI API] <-- ALLEEN als expliciet ingeschakeld
```

---

## 4. Privacy & Security Relevante Punten

### Geen externe data verzending (standaard)
- Alle NLP en text matching gebeurt lokaal
- Sentence embeddings draaien lokaal na eenmalige model download
- Geen telemetry of analytics

### OpenAI integratie (optioneel)
- **Standaard uitgeschakeld**
- Indien ingeschakeld: clausuleteksten worden naar OpenAI gestuurd
- Vereist API key configuratie
- Te configureren via environment variable

### Lokale data opslag
- Geüploade bestanden: tijdelijk in `uploaded_files/`
- Geen database (alle processing in-memory)
- Resultaten worden als Excel geëxporteerd

### Modellen
- spaCy Nederlands model: `nl_core_news_md` (lokaal)
- Sentence transformer: `paraphrase-multilingual-MiniLM-L12-v2` (lokaal na download)

---

## 5. Licentie Overzicht

| Licentie | Aantal packages | Commercieel gebruik |
|----------|-----------------|---------------------|
| MIT | ~45 | Ja |
| Apache-2.0 | 3 | Ja |
| BSD-2/BSD-3 | 4 | Ja |
| ISC | 1 | Ja |
| LGPL-2.1 | 1 (gensim) | Ja* |
| AGPL-3.0 | 1 (PyMuPDF) | Nee** |

*\* LGPL: Dynamisch linken toegestaan*
*\*\* AGPL: Mogelijk problematisch - alternatief beschikbaar (pdfplumber)*

---

## 6. Aanbevelingen voor DPIA

1. **OpenAI:** Documenteer of en wanneer deze feature wordt gebruikt
2. **PyMuPDF (AGPL):** Overweeg vervanging door pdfplumber (MIT) voor striktere compliance
3. **Model downloads:** Eerste installatie vereist internet voor HuggingFace model download
4. **Geen PII logging:** Applicatie logt geen persoonsgegevens

---

## 7. Contactgegevens

Voor technische vragen over deze stack: [invullen]
