# Hienfeld VB Converter — Verbeterpunten (Audit februari 2026)

> Status: 🔲 OPEN
> Aangemaakt: 2026-02-18
> Context: Volledige app-audit — kwaliteitsverbetering analyse-pipeline

---

## Overzicht

| Prioriteit | Taak | Type | Vereist goedkeuring? | Status |
|---|---|---|---|---|
| **P0** | Golden evaluation set | Domeinwerk (geen code) | Nee — vereist analist | 🔲 Open |
| **P1** | BGE-M3 A/B test | Experiment | Nee — makkelijk terug te draaien | 🔲 Open |
| **P1** | LLM voor twijfelgevallen (Ollama) | Architectuurkeuze | **Ja** | ✅ Gedocumenteerd |
| **P1** | OCR-fallback gescande PDF's | Architectuurkeuze | **Ja** | ✅ Tesseract geïmplementeerd |
| **P2** | Feedback loop (analist-correcties) | Nieuwe feature | **Ja** | 🔲 Open |
| **P3A** | Dode code verwijderen | Refactor | Nee | ✅ Reflex verwijderd |
| **P3B** | Caching samenvoegen | Refactor | Nee | ✅ CacheManager |
| **P3C** | ServiceFactory splitsen | Refactor | Nee | ✅ SemanticStackFactory |
| **P3D** | AnalysisService refactoren | Refactor | **Ja** | ✅ Pipeline actief

> **Afhankelijkheid:** P1-experimenten (BGE-M3, Ollama) kunnen pas objectief worden
> beoordeeld als P0 (de Golden Set) beschikbaar is. Begin dus met P0.

---

## P0 — Golden Evaluation Set

**Wat is het?**
Een set van 50–100 clausules waarbij het correcte advies handmatig is vastgesteld
door een domeinexpert. Dit wordt de meetlat voor alle verdere verbeteringen.

**Waarom essentieel?**
Momenteel weet niemand hoe goed de tool het doet. Zonder dit kun je niet meten
of een verbetering (BGE-M3, Ollama) daadwerkelijk beter is.

**Wat moet er gebeuren?**
- [ ] Domeinexpert of analist labelt 50–100 representatieve clausules handmatig
- [ ] Output: CSV/Excel met kolommen: `clausule_tekst | correct_advies | toelichting`
- [ ] Adviezen: `VERWIJDEREN / VERVANGEN / BEHOUDEN / HANDMATIG CHECKEN`
- [ ] Kies clausules die alle categorieën vertegenwoordigen (niet alleen makkelijke)

**Effort:** S (1–2 dagdelen analytisch werk)
**Risico:** Geen technisch risico. Risico: bias als set niet representatief is.

**Valkuil:**
Als de set te klein is (<30) of te eenzijdig (alleen duidelijke gevallen), meet
je niets nuttigs. Zorg voor minimaal 10–15 "twijfelgevallen" (grensscores).

---

## P1 — BGE-M3 A/B Test

**Wat is het?**
Vergelijk het huidige embedding-model (`intfloat/multilingual-e5-large-instruct`,
~2,2 GB) met het nieuwere `BAAI/bge-m3` model op deze codebase.

**Huidig model:** `hienfeld/services/ai/embeddings_service.py:97`

**Wat houdt het in?**
- [ ] BGE-M3 model installeren en configureren in `embeddings_service.py`
- [ ] Beide modellen draaien op dezelfde set clausules
- [ ] Scores vergelijken met Golden Set (P0)
- [ ] Snelheid en geheugengebruik meten (BGE-M3 is ~2,7 GB)

**Effort:** M (modelwissel is klein; evaluatie kost de meeste tijd)
**Risico:** Laag. De modelwissel is één regelwijziging; makkelijk terug te draaien.

**Valkuil:**
BGE-M3 gebruikt een andere query-prefix conventie dan de huidige e5 modellen.
Als je de prefix niet aanpast, zijn de resultaten misleidend slecht. Check
`embeddings_service.py` regels 85–93 (query/passage prefix logica).

**Afhankelijkheid:** Vereist P0 (Golden Set) voor objectieve vergelijking.

---

## P1 — LLM voor twijfelgevallen (Ollama)

**Wat is het?**
Bij twijfelgevallen (similarity score 70–85%) geeft het systeem nu automatisch
"HANDMATIG CHECKEN". Met een lokale LLM kan het vragen: *"Betekenen deze twee
clausules hetzelfde?"* voor een beter onderbouwd advies.

**Huidige staat:**
De LLM-infrastructuur bestaat al (`hienfeld/services/ai/llm_analysis_service.py`)
maar de `client` parameter staat standaard op `None` — er wordt niets verstuurd.

**De keuze die gemaakt moet worden:**

| Optie | Pro | Con |
|---|---|---|
| **Ollama lokaal** | Geen API-kosten, GDPR-proof, offline | ≥16 GB RAM vereist voor Llama 3 8B |
| **OpenAI API** | Geen hardware, sneller, beter model | Kosten per call; clausules gaan naar externe server |
| **Geen LLM** | Niets te installeren | Twijfelgevallen blijven "HANDMATIG CHECKEN" |

**Acties na goedkeuring:**
- [ ] Beslissing vastleggen (Ollama / OpenAI / geen)
- [ ] Bij Ollama: installatie op server/laptop documenteren
- [ ] `llm_analysis_service.py` client activeren met gekozen provider
- [ ] Drempelwaarden bepalen: bij welke score schakel je LLM in?
- [ ] Testen met Golden Set: verbetert het daadwerkelijk?

**Effort:** M (infrastructuur bestaat al; configuratie + testen is het werk)
**Risico:** Middel. LLM-aanroepen vertragen de analyse (~2–5s per cluster).

**Valkuil:**
Als de LLM wordt ingezet op te veel clusters (bijv. alles onder 90%), wordt de
analyse onacceptabel traag. Stel een nauwe drempel in (bijv. 70–82% only).
Test ook: wat doet de LLM als de context leeg is (geen voorwaarden geladen)?

---

## P1 — OCR-fallback voor gescande PDF's

**Wat is het?**
De huidige PDF-parser (PyMuPDF + pdfplumber) kan geen tekst extraheren uit
gescande/gefotografeerde PDF's. Die retourneren een lege string of ruis.

**Huidige staat:**
`hienfeld/services/policy_parser_service.py` — na pdfplumber geen verdere fallback.

**De keuze die gemaakt moet worden:**

| Optie | Pro | Con |
|---|---|---|
| **Tesseract (open-source)** | Gratis, lokaal, GDPR-proof | Lagere nauwkeurigheid op complexe layouts; systeeminstallatie vereist |
| **Azure Form Recognizer** | Hoge nauwkeurigheid, begrijpt tabelstructuren | Kosten (~€0,015/pagina); data gaat naar Azure; internetafhankelijkheid |

**Acties na goedkeuring:**
- [ ] Beslissing vastleggen (Tesseract / Azure / uitgesteld)
- [ ] Bij Tesseract: `pytesseract` + `Pillow` toevoegen aan `requirements.txt`
- [ ] Bij Azure: SDK installeren, API-sleutel beheer regelen
- [ ] OCR als derde fallback toevoegen in `policy_parser_service.py` (~na regel 329)
- [ ] Test met 2–3 bekende gescande PDF's

**Effort:** M (Tesseract) / L (Azure — configuratie + credential beheer)
**Risico:** Laag voor Tesseract; Middel voor Azure (externe afhankelijkheid).

**Valkuil:**
Tesseract heeft standaard een slechte nauwkeurigheid op Dutch legalese zonder
taalmodel. Installeer het Nederlandse taalpakket: `tesseract-ocr-nld`.
Zonder dat pakket zijn de resultaten waarschijnlijk onbruikbaar.

---

## P2 — Feedback Loop (analist-correcties opslaan)

**Wat is het?**
Analisten corrigeren adviezen nu in het geëxporteerde Excel-bestand. Die
correcties verdwijnen — ze komen nooit terug naar het systeem.

**Wat zou de feature doen?**
1. In de UI: correctieveld per rij (origineel advies aanpassen)
2. In de backend: opslaan in database: `{clausule_hash, origineel, gecorrigeerd, tijdstip}`
3. Later (optioneel): correcties hergebruiken als custom instructions of drempel-tuning

**Vragen die beantwoord moeten worden vóór implementatie:**
- [ ] Wie mag correcties zien? Alleen de uploaders, of alle gebruikers?
- [ ] Worden correcties gebruikt om toekomstige analyses te beïnvloeden? Zo ja, hoe?
- [ ] Is een eenvoudige log voldoende, of is er een review-workflow nodig?

**Acties na goedkeuring:**
- [ ] Nieuwe database-tabel: `feedback_corrections`
- [ ] Nieuw API-endpoint: `POST /api/feedback`
- [ ] UI-uitbreiding: correctieveld in resultatentabel
- [ ] Optioneel: koppeling met custom instructions pipeline

**Effort:** L (nieuwe feature raakt frontend + backend + database)
**Risico:** Laag voor de opslag zelf; Middel als correcties de analyse gaan beïnvloeden.

**Valkuil:**
Als correcties automatisch worden teruggevoerd in de analyse (bijv. als custom
instructions), kan slechte invoer van één analist de tool voor iedereen degraderen.
Begin met alleen opslaan (logging), nog niet terugkoppelen.

---

## P3 — Architectuur vereenvoudigen

**Wat is het?**
De codebase heeft ~3.050 regels kernlogica en ~500 regels dode code.
Complexiteitsscore: 8.5/10 — boven wat gebruikelijk is voor een corporate tool.

**Geïdentificeerde problemen:**

| Probleem | Locatie | LOC | Risico verwijdering |
|---|---|---|---|
| Dode Reflex-code | `legacy/`, `requirements.txt` | ~200 | Geen |
| ~~Ongebruikte Pipeline (strategies/)~~ | `hienfeld/services/analysis/` | ~300 | ✅ Gewired (feature flag) |
| God-object ServiceFactory | `hienfeld_api/factories/service_factory.py` | 350 | Laag |
| 7 losse caches zonder centrale invalidatie | Verspreid | — | Laag |
| AnalysisService: 4 matchers in 1 methode | `analysis_service.py` (~900r) | ~400 | Middel |

**Voorgestelde aanpak in fases:**

**Fase A — Dode code verwijderen** *(geen risico)* ✅ AFGEROND
- [x] `legacy/` directory verwijderen
- [x] Ongebruikte `analysis/strategies/` folder verwijderen (~300 LOC weg)
- [x] `reflex>=0.6.0` uit `requirements.txt` verwijderen

**Fase B — Caching samenvoegen** *(laag risico)* ✅ AFGEROND
- [x] Één `CacheManager` klasse introduceren
- [x] Één `/api/cache/clear` endpoint dat alles raakt
- [x] Bestaande cache-logica consolideren

**Fase C — ServiceFactory vereenvoudigen** *(laag risico)* ✅ AFGEROND
- [x] 12 methoden → 2 klassen met duidelijke verantwoordelijkheid
- [x] `SemanticStackFactory` geëxtraheerd (~280 LOC)
- [x] `ServiceFactory` vereenvoudigd (~250 LOC)

**Fase D — AnalysisService refactoren** *(middel risico — vereist testplan)* ✅ AFGEROND
- [x] 5 strategieën gesynchroniseerd met AnalysisService (Admin, Custom, Library, Conditions, Fallback)
- [x] AnalysisPipeline en AnalysisContextBuilder geïmplementeerd
- [x] PRE-CHECK logica (korte/lange teksten) in AdminCheckStrategy
- [x] Feature flag `_use_pipeline` ingeschakeld (pipeline actief)
- [x] Alle 897 tests slagen met pipeline

**Effort:** Fase A+B = S+M; Fase C+D = M+L
**Risico:** Fase A+B: geen/laag. Fase D: middel (kernlogica analyse-pipeline).

**Valkuil:**
Fase D is verleidelijk als eerste stap omdat het de grootste winst geeft, maar
het is ook het riskantste. Begin altijd met Fase A (dode code) — die levert
direct resultaat zonder enig risico. Doe Fase D pas na goedkeuring én testplan.

---

## Aanbevolen volgorde

```
1. P0  → Analist labelt Golden Set (geen code)
2. P3A → Dode code verwijderen (veilig, direct)
3. P1  → BGE-M3 A/B test (na Golden Set)
4. P1  → OCR beslissing + implementatie
5. P1  → Ollama beslissing + implementatie
6. P2  → Feedback loop (na beslissing scope)
7. P3B → Caching samenvoegen
8. P3C+D → Architectuur kern (laatste, vereist testplan)
```

---

## Beslissingen die nog open staan

| # | Beslissing | Opties | Status |
|---|---|---|---|
| 1 | LLM provider voor twijfelgevallen | Ollama / OpenAI / Geen | ❓ Open |
| 2 | OCR provider voor gescande PDF's | Tesseract / Azure / Uitgesteld | ❓ Open |
| 3 | Scope feedback loop | Alleen log / Terugkoppelen naar analyse | ❓ Open |
| 4 | Prioriteit architectuur refactor | Fases A+B nu / Alles later | ❓ Open |
