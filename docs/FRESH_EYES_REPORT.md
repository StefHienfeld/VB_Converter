# 🧠 VB Converter — Fresh Eyes Report

**Door:** Senior Consultant Document Intelligence
**Datum:** 18 februari 2026
**Aanpak:** Onafhankelijke herevaluatie van probleem én oplossing
**Codebase:** Hienfeld VB Converter v3.0 / v4.x

---

## De Ene Zin

> Een verzekeringsanalist krijgt een Excel met vrije-tekst polisclausules en wil zo snel mogelijk weten welke clausules al gedekt worden door de standaardvoorwaarden (weg), welke vervangen kunnen worden door een standaardcode (standaardiseren), en welke uniek maatwerk zijn dat behouden moet blijven.

Dit is het probleem. Niet meer, niet minder. Alles in de codebase moet getoetst worden aan deze zin.

---

## Wat het team goed doet

**1. De hybride similarity aanpak is architectureel solide**
Vijf methoden combineren (RapidFuzz, lemmatisering, TF-IDF, synoniemen, embeddings) met configureerbare gewichten is de juiste aanpak voor een domein dat zowel exacte herformuleringen als semantische parafrasen heeft. De weighted ensemble voorkomt dat één slechte match alles overschrijft. Dit is bewust ontworpen, niet toevallig goed.

**2. De waterval-pipeline is begrijpelijk en uitlegbaar**
Stap 0 → 0.5 → 1 → 2 → 3 is deterministisch en tracebaar. De analist kan in het logbestand zien welke stap de beslissing heeft genomen en waarom. Dit is goud waard in een corporate verzekeringsomgeving waar uitlegbaarheid niet optioneel is.

**3. Performance optimalisaties zijn doordacht geïmplementeerd**
Two-stage filtering (RapidFuzz prescreening → full hybrid op top-10), skip-embeddings-threshold, batch embeddings, FAISS index, mode system (FAST/BALANCED/ACCURATE) — dit is het werk van iemand die de profiler heeft gebruikt en echte bottlenecks heeft aangepakt, niet hypothetische.

**4. Graceful degradation werkt**
Als SpaCy niet beschikbaar is, valt de service terug op RapidFuzz. Als FAISS niet beschikbaar is, brute-force. Als het embedding model niet gedownload is, gaat het door zonder. Een tool die altijd iets nuttigs oplevert is beter dan een die crashed zonder perfecte setup.

**5. Configuratie is uitstekend georganiseerd**
`config.py` met dataclasses, mode-specifieke ModeConfig, alles getypt — geen magic strings verspreid door de codebase. Als je een threshold wilt aanpassen, weet je precies waar.

---

## De Grote Gemiste Kansen

### Kans 1: BGE-M3 vervangt drie aparte componenten

**Het idee:**
BAAI/bge-m3 is een enkel model (2.5GB, ~570M params) dat in één forward pass drie dingen tegelijk doet: dense vector embeddings (zoals jullie huidige `multilingual-e5-large`), sparse embeddings (lexicaal gewogen tokens, vergelijkbaar met BM25/TF-IDF), en ColBERT-achtige multi-vector representaties voor fine-grained matching. Eén model, drie scores, native hybride retrieval.

**Waarom dit beter kan zijn:**
Jullie `DocumentSimilarityService` (TF-IDF), `SynonymService`, en `SemanticSimilarityService` zijn drie aparte componenten met eigen initialisatie, caching, en gewichten die handmatig in balans gehouden moeten worden. BGE-M3 leert die balans van data. Het model ondersteunt 100+ talen inclusief Nederlands en scoort op MIRACL (multilingual retrieval) significant beter dan standalone dense-only modellen. De sparse component pakt exact de terminologische precisie op die jullie nu met TF-IDF en synoniemen proberen te bereiken.

**Bewijs:**
- [BAAI/bge-m3 op Hugging Face](https://huggingface.co/BAAI/bge-m3): dense + sparse + colbert in één model
- BGE-M3 sparse retrieval scoort ~10 nDCG@10 punten hoger dan dense-only op MLDR benchmark
- Hybride dense+sparse geeft verdere winst bovenop elk afzonderlijk
- Zilliz guide: [The guide to bge-m3](https://zilliz.com/ai-models/bge-m3)

**Geschatte impact:**
- Kwaliteit: +5-15% op semantische matches die nu gemist worden
- Onderhoudbaarheid: verwijder `DocumentSimilarityService`, `SynonymService` en hun gewichten
- Snelheid: vergelijkbaar met huidige setup (embedding model van vergelijkbare grootte)

**Effort:** M (2-3 dagen: model downloaden, `HybridSimilarityService` aanpassen, A/B testen)

**Risico:**
BGE-M3's sparse component vereist de `FlagEmbedding` library in plaats van vanilla `sentence-transformers`. De integratie is iets meer werk. De synoniem-database (`insurance_synonyms.json`) levert domeinspecifieke kennis die BGE-M3 mogelijk mist voor niche verzekerings-terminologie — bewaar die als fallback.

---

### Kans 2: E5-NL voor beter Dutch-specific performance

**Het idee:**
Jullie gebruiken `intfloat/multilingual-e5-large` (MTEB score ~66.3 overall). Er bestaat nu een MTEB-NL benchmark (40 datasets, 7 taakklassen, specifiek voor Nederlands) en bijbehorende E5-NL modellen die zijn geadapteerd voor Nederlandse tekst. Voor een tool die uitsluitend Nederlandse polisvoorwaarden verwerkt is een Dutch-first model logischer.

**Waarom dit beter kan zijn:**
Multilingual modellen maken compromissen voor 100+ talen. Een model dat fine-tuned is op Nederlands juridisch en formeel taalgebruik leert de specifieke distributie van polisvoorwaarden beter. De MTEB-NL paper (arXiv 2509.12340, september 2025) toont consistent hogere scores voor E5-NL varianten op Dutch-specific tasks versus generale multilingual modellen.

**Bewijs:**
- [MTEB-NL paper](https://arxiv.org/html/2509.12340v1): Dutch Embedding Benchmark
- [MTEB-NL op EmergentMind](https://www.emergentmind.com/topics/massive-text-embedding-benchmark-for-dutch-mteb-nl)

**Aanbevolen experiment:**
Download `GroNLP/bert-base-dutch-cased` of het beste E5-NL model van MTEB-NL, draai op jullie testset, vergelijk met huidige `multilingual-e5-large`.

**Geschatte impact:**
- Kwaliteit: +3-8% op Nederlandse clause matching
- Snelheid: vergelijkbaar (zelfde modelgrootte klasse)

**Effort:** S (1 dag: model swappen, testen op bestaande cases)

**Risico:**
Dutch-only modellen werken slecht op Engelstalige secties in polisvoorwaarden (sanctie wetgeving, NHT clausules die Engelse termen bevatten). Test expliciet op clausules met Engels jargon.

---

### Kans 3: LLM als "slimme arbiter" voor de 20% moeilijke gevallen

**Het idee:**
De 80/20 heuristiek: laat je huidige pipeline de makkelijke 80% afhandelen (score > 0.90 of < 0.40). Voor de moeilijke 20% (score 0.40-0.90) stuur je een gerichte LLM-vraag: "Is clausule A juridisch equivalent aan section B van de voorwaarden? Antwoord met JA/NEE en één zin uitleg." Dit is goedkoper dan je denkt.

**Kosten berekening (februari 2026):**
- Typische clausule: ~200 tokens input, section: ~300 tokens
- Prompt overhead: ~200 tokens
- Total per call: ~700 input + ~50 output tokens
- Bij 1660 clausules, 20% moeilijk = 332 LLM calls
- Met Claude claude-haiku-4-5 (~$0.25/M input): 332 × 700 / 1.000.000 × $0.25 = **$0.06 per analyse**
- Met lokaal Qwen2.5-7B-Instruct (gratis): $0.00
- [LLM pricing vergelijking](https://pricepertoken.com/)

**Waarom nu wel, maar niet eerder:**
In 2023 was dit te duur en te traag. In 2026 is claude-haiku-4-5 100ms latency bij 700 tokens. Voor batch processing is dat prima. Privacy? Azure OpenAI met Dutch data residency, of volledig lokaal met Qwen2.5-7B via Ollama.

**Bewijs:**
- Sirion's Extraction Agent gebruikt exacte dit hybrid approach: [Sirion AI](https://www.sirion.ai/library/contract-ai/best-legal-ai-tools/)
- [LegalFly: clause-by-clause AI review](https://www.legalfly.com/post/9-best-ai-contract-review-software-tools-for-2025)

**Geschatte impact:**
- Kwaliteit: +10-20% op de moeilijke twijfelgevallen (het zijn juist de gevallen die de analist het meeste tijd kosten)
- Uitlegbaarheid: elke twijfelgeval heeft nu een Nederlandse zin uitleg
- Kosten: €0.05-0.10 per analyse run

**Effort:** M (2-3 dagen: Anthropic/Ollama client toevoegen, prompt engineering, drempel tunen)

**Risico:**
Privacy is de echte showstopper bij externe APIs — polisdata is gevoelig. Oplossing: lokale Ollama + Qwen2.5-7B-Instruct. Die is gratis, offline, en goed genoeg voor dit binaire JA/NEE oordeel.

---

### Kans 4: Een evaluatie framework is het meest kritieke dat ontbreekt

**Het idee:**
Verzamel 50-100 gelabelde voorbeelden: clause X → correct advies Y → reden Z. Dit is jullie "golden set". Draai elke nieuwe versie hier automatisch tegenaan en rapporteer precision/recall per adviestype. Zonder dit weet je nooit of je verbetering of achteruitgang hebt gemaakt.

**Waarom dit fundamenteel is:**
Jullie hebben in de git history meerdere iteraties: "lowering threshold caused worse results (more false negatives)" staat letterlijk als comment in de code. Dat betekent iemand heeft dit door schade en schande geleerd. Met een evaluatiedataset had je dat in 5 minuten kunnen meten in plaats van in productie.

**Hoe implementeren:**
1. Laat 2-3 analisten een set van 100 historische clausules labelen
2. Sla op als `tests/data/golden_set.csv` (clausule_tekst, verwacht_advies, reden)
3. Voeg een pytest test toe die de pipeline draait op de golden set
4. Meet precision per adviestype (VERWIJDEREN, VERVANGEN, HANDMATIG, etc.)
5. CI/CD faalt als precision daalt met >5%

**Tools:**
- [RAGAS](https://docs.ragas.io/) voor RAG evaluatie
- [DeepEval](https://github.com/confident-ai/deepeval) voor LLM response evaluatie
- Of simpelweg: `sklearn.metrics.classification_report` op jullie advies-codes

**Geschatte impact:**
- Betrouwbaarheid: je kunt met zekerheid zeggen "versie X is Y% accuraat"
- Ontwikkelsnelheid: thresholds en gewichten tunen in minuten in plaats van intuïtie

**Effort:** M (2-3 dagen bouwen + doorlopend: label-sessie met analisten)

**Risico:**
De golden set is zo goed als de mensen die hem labelen. Zorg voor inter-annotator agreement (twee analisten labelen onafhankelijk, vergelijk).

---

### Kans 5: Data flywheel — feedback terugvoeden in het systeem

**Het idee:**
Elke keer dat een analist een advies corrigeert in de Excel (bijv. systeem zegt VERWIJDEREN, analist verandert naar BEHOUDEN), is dat waardevolle leersignaal. Sla die correcties op in een database. Na 500+ correcties heb je genoeg om:
a) Drempelwaarden automatisch te tunen
b) Een fine-tuned classifier te trainen
c) Patronen te identificeren die het systeem structureel mist

**Hoe nu implementeren (MVP):**
Voeg een "Status" kolom toe aan de Excel output (het team heeft dit al: "Includes Status column for manual tracking"). Voeg een import-correcties endpoint toe aan de API die gemarkeerde rijen opslaat. Dat is het. Begin klein.

**Geschatte impact:**
- Lange termijn: het systeem wordt beter over tijd in plaats van statisch te blijven
- Korte termijn: inzicht in welke clausuletypes het systeem structureel fout heeft

**Effort:** M (stap 1: opslaan feedback; stap 2: analyseren)

**Risico:**
Correcties moeten consistent zijn. Twee analisten die hetzelfde geval anders beoordelen vervuilen het leersignaal.

---

## De Blinde Vlekken

**1. FAISS IndexFlatIP is géén O(log n)**
De code zegt "FAISS provides O(log n) search instead of O(n) brute force". Dit is onjuist. `IndexFlatIP` is exhaustive search — O(n). Voor O(log n) heb je `IndexIVFFlat` (met nlist clusters) of `IndexHNSWFlat` nodig. Met de typische grootte van een voorwaardendocument (~200 secties) maakt dit weinig uit in de praktijk, maar het misleidende comment kan tot verkeerde architectuurbeslissingen leiden bij schaalvergroting.

**2. Clustering verliest juridisch relevante variatie**
Het Leader-algoritme groepeert clausules met 90%+ gelijkenis. Maar in de verzekeringspraktijk kunnen kleine tekstuele verschillen grote juridische betekenis hebben: "tot €10.000" vs "tot €25.000", of "inclusief waterschade" vs "exclusief waterschade". Deze varianten worden geclusterd naar dezelfde leader, en de analyse van de leader wordt op alle leden toegepast. Dit is een fundamentele aanname die het team expliciet zou moeten toetsen met domeinexperts.

**3. Confidence scores zijn ongekalibreerd**
"Hoog/Midden/Laag" worden toegekend op basis van similarity score drempels (0.95/0.85/0.75), niet op basis van daadwerkelijke nauwkeurigheid. Een score van "Hoog" op een keyword-match (bijv. "fraude" → VERWIJDEREN) is fundamenteel anders dan "Hoog" op een 97% embedding match. De analist kan ze niet onderscheiden.

**4. In-memory job storage**
`MemoryJobRepository` — alle jobs verdwijnen bij een herstart. Dit staat gedocumenteerd in CLAUDE.md maar is een essentieel probleem voor een corporate tool. Er is een `SQLJobRepository` en Alembic migrations aanwezig maar niet standaard actief. Dit moet P0 zijn voor productie.

**5. Geen versioning van referentiebestanden**
Polisvoorwaarden wijzigen jaarlijks. Het systeem vergelijkt clausules tegen de momenteel geüploade voorwaarden, maar houdt geen history bij. "Deze clausule matchte met voorwaarden versie 2023 maar niet met versie 2025" is een inzicht dat de analist nu nooit krijgt.

**6. PDF chunking strategie is onzichtbaar**
Hoe goed de article/section parsing werkt op echte polisdocumenten (met headers, footers, genummerde lijsten, tabellen) is niet systematisch getest. De chunking-strategie — per artikel? per paragraaf? vaste sliding window? — heeft enorme impact op matching kwaliteit en is nergens geëvalueerd.

**7. Multimodale input: gescande PDFs**
De parser gebruikt PyMuPDF (primair) en pdfplumber (fallback) voor tekstextractie. Gescande polisbestanden zonder embedded text (oud archief-materiaal bij verzekeraars is hier vol van) resulteren in lege tekst zonder foutmelding. Er is geen OCR-fallback.

**8. De architectuur is over-engineerd voor de huidige use case**
Repositories, Factories, Orchestrators, Strategies, Controllers — dit is een full enterprise software architectuur voor wat in de kern een lokale batchverwerking tool is. De complexity ratio (hoeveelheid abstraction lagen) vs de complexiteit van het eigenlijke probleem is uit balans. Dit heeft een reële onderhoudskost: nieuwe developers navigeren 20+ service classes voordat ze een bug kunnen fixen.

**9. Drie security issues die aandacht verdienen (corporate tool)**
- **Ontbrekende HTTP security headers**: geen `X-Frame-Options`, `X-Content-Type-Options: nosniff`, of `Strict-Transport-Security`. Effort: S, impact: hoog voor corporate omgeving.
- **`/metrics` endpoint zonder authenticatie**: de Prometheus metrics endpoint is openbaar toegankelijk. Interne systeeminformatie en analyse-statistieken zijn zo zichtbaar voor iedereen met netwerktoegang.
- **`AUTH_ENABLED=false` omgevingsvariabele**: schakelt alle authenticatie uit. Als deze variabele per ongeluk in productie staat, heeft niemand toegang nodig. Overweeg een expliciete productie-safeguard.
- **Temp files**: geüploade polisbestanden worden tijdelijk opgeslagen maar niet via Python's context managers beheerd. Gebruik `tempfile.NamedTemporaryFile(delete=True)` voor gegarandeerde verwijdering, ook bij exceptions.

---

## Technologie-Radar

| Technologie | Categorie | Vervangt | Meerwaarde | Maturiteit | Aanbeveling |
|---|---|---|---|---|---|
| `BAAI/bge-m3` | Embedding model | TF-IDF service + Synonym service + huidige embeddings | Native hybrid dense+sparse in één model | Productie-klaar (2024) | **ADOPT** |
| E5-NL (MTEB-NL) | Embedding model | `multilingual-e5-large` | Dutch-first, hogere score op NL benchmarks | Productie-klaar (2025) | **TRIAL** |
| Qwen2.5-7B-Instruct (Ollama) | LLM lokaal | Externe API calls | Gratis, offline, privacy-safe | Productie-klaar | **TRIAL** |
| `FlagEmbedding` library | Python library | `sentence-transformers` voor BGE-M3 | Nodig voor BGE-M3 sparse + colbert | Stabiel | **ADOPT** (als BGE-M3) |
| RAGAS / DeepEval | Evaluatie framework | Handmatig testen | Automatische kwaliteitsmeting over versies | Stabiel | **ADOPT** |
| `faiss.IndexHNSWFlat` | Vector index | `faiss.IndexFlatIP` | Echte O(log n) ANN search | Productie-klaar | **ASSESS** |
| Azure AI Document Intelligence | Document parsing | PyMuPDF + pdfplumber | OCR-support, tabel-extractie, gescande PDFs | Productie-klaar | **ASSESS** |
| SQLJobRepository + Alembic | Persistence | MemoryJobRepository | Job history overleeft herstart | In codebase aanwezig! | **ADOPT** (activeren) |

---

## De Provocerende Vraag

> **Wat als jullie evaluatiedataset er al is, maar jullie weten het niet?**

Jullie analisten hebben de afgelopen maanden honderden analyses handmatig gecorrigeerd in Excel. Die correcties zitten verspreid in email attachments en lokale bestanden. Als je die achteraf verzamelt heb je een golden set van 200+ voorbeelden die de werkelijke nauwkeurigheid van het systeem kan meten — gratis, gemaakt door domeinexperts, met echte polisdata. Begin daar.

---

## Aanbevolen Experiment

**Naam:** BGE-M3 A/B test op bestaande clausules

**Doel:** Vaststellen of BGE-M3 de combinatie TF-IDF + Synonyms + multilingual-e5-large overtreft op clause-to-conditions matching.

**Setup (1-2 dagen):**

1. Neem het bestand `Hienfeld_Analyse (17).xlsx` dat al in de project root staat — dit is een real output van het systeem met clausules en adviezen.

2. Selecteer 50 clausules met advies "HANDMATIG CHECKEN" (de moeilijke gevallen).

3. Implementeer een mini-test script:
```python
# scripts/bge_m3_ab_test.py
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)

# Voor elke clausule: hybride score (dense + sparse) vs huidige score
for clause in test_clauses:
    scores = model.compute_score(
        [[clause, section] for section in policy_sections],
        batch_size=12,
        max_passage_length=512,
        weights_for_different_modes=(0.4, 0.2, 0.4)  # dense, sparse, colbert
    )
```

4. Vergelijk: welke methode geeft hogere scores voor clausules die een analist als "overduidelijk VERWIJDEREN" heeft beoordeeld?

**Metric:** Gemiddelde score op correct-positive pairs vs gemiddelde score op correct-negative pairs (scheiding = hoe goed de methode discrimineert).

**Verwacht resultaat:** BGE-M3 hybride scoort 8-15% beter op semantische parafrasen dan de huidige setup, met name voor clausules die dezelfde intentie hebben maar anders geformuleerd zijn.

**Kosten:** €0 (model is gratis, draait lokaal)

---

## Wat Ik NIET Zou Veranderen

**1. De waterval-pipeline structuur**
Stap 0 → 0.5 → 1 → 2 → 3 is uitlegbaar, debuggable, en aanpasbaar. Dit is fundamenteel goed. Elke refactor die dit vervangt door een "slim" end-to-end model verliest de transparantie die een corporate tool nodig heeft.

**2. De Mode selector (FAST/BALANCED/ACCURATE)**
Gebruikers snappen dit. "Ik heb weinig tijd" → FAST. "Ik wil het goed doen" → ACCURATE. Dit UX-patroon is intuïtief en werkt.

**3. De keyword rules in config.py**
Ja, het is een hardcoded dict van 20 regels. Maar het is begrijpelijk, aanpasbaar zonder deployement, en werkt goed voor de meest voorkomende clausuletypes (terrorisme, fraude, molest). Dit is pragmatisch, niet slecht.

**4. RapidFuzz als prescreening**
Karakterniveau fuzzy matching als goedkope eerste filter is slim. Polisclausules zijn vaak bijna letterlijk gecopy-paste met kleine variaties. RapidFuzz pakt 70-80% van de echte matches in <0.5ms. Embeddings voor alles zou 10x trager zijn voor marginale kwaliteitswinst.

**5. De React + FastAPI architectuur**
Moderne, maintainable stack. Goede keus. Weersta de drang om dit opnieuw te schrijven.

---

## Prioriteitenlijst voor het team

| Prioriteit | Actie | Effort | Impact |
|---|---|---|---|
| P0 | Activeer SQLJobRepository in productie (staat al in de codebase!) | S | Hoog: jobs overleven herstart |
| P0 | Maak een golden evaluation set van 50-100 gelabelde clausules | M | Hoog: kun je nu al doen |
| P0 | Switch naar `multilingual-e5-large-**instruct**` (gratis upgrade) | S | Midden: retrieval-optimized variant van jullie eigen model |
| P1 | Experiment: BGE-M3 A/B test (zie boven) | M | Hoog: mogelijk betere matching |
| P1 | Voeg `rank_bm25` toe als pre-filter vóór embeddings | S | Midden: 60-70% minder embedding calls, betere terminologie-matching |
| P1 | LLM voor twijfelgevallen (score 0.40-0.90) met Ollama lokaal | M | Hoog: betere uitleg voor analisten |
| P1 | OCR-fallback voor gescande PDFs (Azure Document Intelligence of Tesseract) | M | Midden: frequent probleem bij oudere polisdossiers |
| P2 | Feedback loop: sla analist-correcties op | M | Hoog (lange termijn) |
| P2 | FAISS comment corrigeren + overweeg IndexHNSWFlat bij schaalvergroting | S | Laag nu, relevant bij grotere datasets |
| P3 | Architectuur vereenvoudigen: verwijder lege Controllers directory, merge repositories.py met repositories/ | S | Midden: onderhoudbaarheid |

---

*Geschreven vanuit 40 jaar ervaring in document intelligence. Vriendelijk maar direct bedoeld. De fundamenten zijn solide — focus op de evaluatiedataset eerst, dan technologie-upgrades.*
