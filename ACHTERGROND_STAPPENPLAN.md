# Hoe Werkt de VB Converter Achter de Schermen? 🔍

---

## 📋 Overzicht: Wat gebeurt er van begin tot eind?

Wanneer je op "Start Analyse" klikt, doorloopt het systeem 6 hoofdstappen:

1. **Bestanden inlezen** → Teksten begrijpelijk maken voor de computer
2. **Voorwaarden verwerken** → Artikelen uit PDF's halen
3. **Clustering** → Duplicaten en bijna-gelijke teksten groeperen
4. **Analyse** → Per groep bepalen wat je ermee moet doen
5. **Rapport maken** → Alles netjes in Excel zetten
6. **Resultaten tonen** → In de interface laten zien

Laten we elke stap precies uitleggen!

---

## STAP 1: Bestanden Inlezen 📁

### Wat gebeurt er?
Je upload een Excel of CSV bestand met duizenden polisregels. De computer moet dit eerst "begrijpen".

### Welke tools worden gebruikt?

#### **pandas** (Python bibliotheek voor data)
- **Wat doet het?** Leest Excel/CSV bestanden en zet ze om in een soort slimme tabel
- **Waarom?** Excel heeft kolommen, rijen, verschillende formaten - pandas zorgt dat de computer daar mee kan werken
- **Vergelijk het met:** Een vertaler die een stapel papieren omzet in een georganiseerde database

#### **openpyxl** (Excel lees-tool)
- **Wat doet het?** Kan Excel-bestanden (.xlsx) openen en lezen
- **Waarom?** Pandas gebruikt deze tool om Excel specifiek te kunnen lezen
- **Vergelijk het met:** De sleutel die de Excel-deur opent

### Wat gebeurt er precies?

**Stap 1.1: Bestandstype herkennen**
```
Is het een .xlsx bestand? → Gebruik openpyxl om te openen
Is het een .csv bestand? → Detecteer eerst hoe het gescheiden is (komma's of puntkomma's)
```

**Stap 1.2: Encoding detecteren (voor CSV)**
- **Wat is encoding?** Hoe de letters en tekens zijn opgeslagen (denk aan Nederlandse letters zoals é, ë, ö)
- Het systeem probeert: UTF-8, Latin-1, Windows-1252
- **Waarom?** Anders zie je rare tekens als ├ę in plaats van é

**Stap 1.3: De juiste kolom vinden**
Het systeem zoekt automatisch welke kolom de vrije teksten bevat:
- Zoekt naar namen zoals: "Tekst", "Vrije Tekst", "Clausule", "Omschrijving"
- Als het niks vindt → pakt de laatste kolom (daar staan vaak de teksten)

**Stap 1.4: Teksten normaliseren**
Voor ELKE tekst doet het systeem dit:

```
Originele tekst: "Auto's VERZEKERD tegen Brandschade"
↓
Stap 1: Hoofdletters → kleine letters
"auto's verzekerd tegen brandschade"
↓
Stap 2: Accenten verwijderen (é → e, ë → e)
"auto's verzekerd tegen brandschade"
↓
Stap 3: Extra spaties weg
"auto's verzekerd tegen brandschade"
↓
Stap 4: Speciale tekens normaliseren
"autos verzekerd tegen brandschade"
```

**Resultaat:** Een `Clause` object voor elke rij met:
- `raw_text` = originele tekst (voor in het rapport)
- `simplified_text` = genormaliseerde tekst (voor vergelijken)
- `id` = uniek nummer
- `source_policy_number` = van welke polis komt dit

---

## STAP 2: Voorwaarden Verwerken 📄

### Wat gebeurt er?
Je upload een PDF met Algemene Voorwaarden. Die moet uitgepluzen worden naar individuele artikelen.

### Welke tools worden gebruikt?

#### **PyMuPDF (fitz)** (PDF lezer)
- **Wat doet het?** Leest PDF-bestanden en haalt er tekst uit
- **Waarom?** PDF's zijn eigenlijk plaatjes met tekst eroverheen - je hebt speciale software nodig om de tekst eruit te halen
- **Vergelijk het met:** Een scanner met tekstherkenning (OCR)
- **Hoe werkt het?** Gaat pagina voor pagina door de PDF en extraheert alle tekst

#### **pdfplumber** (Backup PDF lezer)
- **Wat doet het?** Alternatieve manier om PDF's te lezen
- **Waarom?** Sommige PDF's zijn moeilijk leesbaar met PyMuPDF (oude scans, rare layouts)
- **Wanneer gebruikt?** Als PyMuPDF niks vindt of rare output geeft
- **Vergelijk het met:** Als je ene bril niet werkt, probeer je een andere

#### **python-docx** (Word lezer)
- **Wat doet het?** Leest Word documenten (.docx)
- **Waarom?** Voorwaarden kunnen ook als Word-bestand komen
- **Hoe werkt het?** Gaat paragraaf voor paragraaf door het Word-document

### Wat gebeurt er precies?

**Voor PDF's:**

```
1. Open PDF met PyMuPDF
2. Loop door elke pagina
3. Haal alle tekst van die pagina
4. Zoek naar artikelnummers:
   - "Artikel 1"
   - "Art. 2.8"
   - "Paragraaf 3"
5. Splits de tekst op per artikel
6. Sla op als lijst van artikelen met:
   - Titel (bijv. "Artikel 2.8")
   - Tekst (hele inhoud van dat artikel)
   - Paginanummer (waar staat het)
```

**Voor Word:**

```
1. Open Word document met python-docx
2. Lees alle paragrafen
3. Zoek naar artikelnummers (zelfde patronen als PDF)
4. Splits op per artikel
```

**Resultaat:** Een lijst `PolicyDocumentSection` objecten, elk een artikel uit de voorwaarden:
- `title` = "Artikel 2.8"
- `raw_text` = hele tekst van dat artikel
- `simplified_text` = genormaliseerde versie
- `page_number` = pagina 12

---

## STAP 3: Clustering - Duplicaten Vinden 🔍

### Wat gebeurt er?
Je hebt duizenden polisregels. Veel daarvan zijn hetzelfde of bijna hetzelfde. Die gaan we groeperen.

### Welke tools worden gebruikt?

#### **RapidFuzz** (Tekstgelijkenis checker)
- **Wat doet het?** Berekent hoe gelijk twee teksten zijn (als percentage)
- **Waarom?** Je wilt niet alleen exacte matches vinden, maar ook teksten die 95% hetzelfde zijn
- **Hoe werkt het?** 
  - Vergelijkt twee teksten letter voor letter
  - Geeft een score van 0% (totaal verschillend) tot 100% (exact hetzelfde)
  - **Voorbeeld:**
    ```
    Tekst 1: "Dekking voor brandschade"
    Tekst 2: "Dekking voor brand schade"
    Score: 98% (bijna hetzelfde, alleen spatie verschil)
    ```

#### **Leader Clustering** (Groeperingsalgoritme)
- **Wat doet het?** Een slim systeem om duizenden teksten in groepen te verdelen
- **Waarom?** Je kunt niet elke tekst met ALLE andere teksten vergelijken (te langzaam)
- **Hoe werkt het?**

### Het Leader Clustering Algoritme - Uitgelegd

Stel je voor: je hebt 10.000 polisregels en je wilt ze groeperen.

**Stap 1: Sorteer op lengte**
```
Langste teksten eerst → korte teksten achteraan
Waarom? Lange teksten zijn vaak "representatiever" voor een groep
```

**Stap 2: Loop door alle teksten**
```
Voor elke tekst:
  
  A) Check: Is deze tekst EXACT hetzelfde als een eerder geziene tekst?
     → JA: Voeg toe aan die groep (klaar!)
     → NEE: Ga naar B
  
  B) Check: Is deze tekst ongeveer hetzelfde (genormaliseerd)?
     → Verwijder bedragen (€500 → €XXX)
     → Verwijder datums (01-01-2024 → DD-MM-JJJJ)
     → Verwijder postcodes/adressen
     → Is het NU hetzelfde? JA: Voeg toe aan groep
     → NEE: Ga naar C
  
  C) Vergelijk met de LAATSTE 50 groepen (niet alle duizenden!)
     → Voor elke groep:
        - Bereken gelijkenis met RapidFuzz
        - Is het ≥90% gelijk? (instelbaar)
          → JA: Voeg toe aan die groep
          → NEE: Probeer volgende groep
     
  D) Geen match gevonden?
     → Maak NIEUWE groep aan met deze tekst als "leader"
```

**Waarom alleen laatste 50 groepen?**
- **Snelheid:** 10.000 teksten × 10.000 vergelijkingen = 100 miljoen berekeningen (veel te langzaam!)
- **Met 50:** 10.000 teksten × 50 vergelijkingen = 500.000 berekeningen (snel!)
- **Slim:** De meest voorkomende teksten komen vroeg in de lijst, dus die vang je alsnog

**Voorbeeld:**

```
Tekst 1: "Dekking voor brandschade tot maximaal €100.000"
→ NIEUWE GROEP: CL-0001 (leader)

Tekst 2: "Dekking voor brandschade tot maximaal €50.000"
→ Vergelijk met CL-0001 → 95% gelijk → VOEG TOE aan CL-0001

Tekst 3: "Dekking voor waterschade"
→ Vergelijk met CL-0001 → 45% gelijk → TE LAAG
→ NIEUWE GROEP: CL-0002 (leader)

Tekst 4: "Dekking voor brandschade tot maximaal €100.000"
→ EXACT MATCH met CL-0001 → VOEG TOE aan CL-0001

Tekst 5: "Dekking voor water schade"
→ Vergelijk met CL-0002 → 98% gelijk → VOEG TOE aan CL-0002
```

**Resultaat:**
```
CL-0001: "Dekking voor brandschade..." (3x)
CL-0002: "Dekking voor waterschade..." (2x)
```

---

## STAP 4: Analyse - Wat Moet Je Met Elke Groep? 🎯

Dit is de kern van het systeem! Voor ELKE cluster doorloopt het een "waterfall" van checks.

### Welke tools worden gebruikt?

#### **SpaCy** (Nederlandse taalverwerking)
- **Wat doet het?** Begrijpt Nederlandse taal op een slimme manier
- **Waarom?** Zodat de computer begrijpt dat "verzekerd", "verzekeren" en "verzekering" hetzelfde betekenen
- **Hoe werkt het?**
  - **Lemmatisering:** Zet woorden om naar hun basisvorm
    ```
    "auto's" → "auto"
    "verzekerd" → "verzekeren"
    "liep" → "lopen"
    ```
  - **Keyword extractie:** Vindt de belangrijkste woorden in een tekst
    ```
    "De auto's zijn verzekerd tegen brandschade en diefstal"
    → Belangrijke woorden: ["auto", "verzekeren", "brandschade", "diefstal"]
    ```

#### **Gensim** (Document vergelijker)
- **Wat doet het?** Berekent welke woorden belangrijk zijn in een tekst (TF-IDF)
- **Waarom?** Niet alle woorden zijn even belangrijk
- **Hoe werkt het?**
  - **TF (Term Frequency):** Hoe vaak komt een woord voor in deze tekst?
  - **IDF (Inverse Document Frequency):** Hoe zeldzaam is dit woord in ALLE teksten?
  - **Score = TF × IDF**
  - **Voorbeeld:**
    ```
    Woord "dekking" komt 5x voor in deze tekst (hoge TF)
    Maar "dekking" komt in 90% van alle teksten voor (lage IDF)
    → Lage score (niet onderscheidend)
    
    Woord "molest" komt 3x voor in deze tekst (gemiddelde TF)
    Maar "molest" komt maar in 2% van alle teksten voor (hoge IDF)
    → Hoge score (belangrijk/onderscheidend woord!)
    ```

#### **Open Dutch WordNet (wn)** (Synoniemenwoordenboek)
- **Wat doet het?** Weet welke Nederlandse woorden synoniemen zijn
- **Waarom?** "Auto" en "voertuig" betekenen hetzelfde, maar zijn anders geschreven
- **Hoe werkt het?** Groot woordenboek met relaties tussen woorden
- **Plus:** Het systeem heeft een eigen verzekeringswoordenboek met 50+ groepen:
  ```
  Groep "voertuigen": auto, voertuig, personenauto, wagen, motorvoertuig
  Groep "woning": huis, pand, woonhuis, gebouw, opstal
  Groep "verzekerd": gedekt, meeverzekerd, verzekerde, dekking
  ```

#### **sentence-transformers** (Betekenis begrijper - optioneel)
- **Wat doet het?** Zet tekst om in een "betekenisvector" (embeddings)
- **Waarom?** Begrijpt dat teksten hetzelfde kunnen betekenen zonder dezelfde woorden te gebruiken
- **Hoe werkt het?**
  - Elke tekst wordt een lijst van getallen (vector)
  - Teksten met vergelijkbare betekenis krijgen vergelijkbare getallen
  - **Voorbeeld:**
    ```
    "Bij gedwongen verhuizing" → [0.2, 0.8, 0.1, ..., 0.5]
    "Wanneer u verplicht bent te verhuizen" → [0.3, 0.7, 0.1, ..., 0.6]
    → Vectoren lijken op elkaar → Betekenis is hetzelfde!
    ```

### De Waterfall Analyse - Stap voor Stap

Het systeem loopt voor ELKE cluster door deze checks (van boven naar beneden, eerst match = klaar):

---

#### **CHECK 0: Admin Hygiëne ✋**

**Doel:** Vang technische problemen op

**Checks:**
- Is de tekst leeg? → **VERWIJDEREN**
- Bevat de tekst alleen rare tekens (####)? → **OPSCHONEN**
- Is de tekst een placeholder ("Zie artikel...")? → **AANVULLEN**
- Bevat de tekst oude datums (<2020)? → **VEROUDERD**

**Tools:** Regex patronen, datumdetectie

**Als match:** Stop hier, advies = OPSCHONEN/AANVULLEN/VERWIJDEREN (admin reden)

---

#### **PRE-CHECK: Multi-clause detectie 📦**

**Doel:** Detecteer "breitexten" met meerdere clausules in één

**Hoe:**
```
1. Zoek naar clausulecodes in de tekst (bijv. "9NX3", "VB12")
2. Tel hoeveel VERSCHILLENDE codes er zijn
3. Check de lengte van de tekst

Als:
  - Meer dan 1 unieke code ÉN
  - Tekst is langer dan 800 tekens
Dan:
  → Advies: SPLITSEN (brei met meerdere clausules)
```

**Voorbeeld:**
```
"Dekking voor brandschade 9NX3 inclusief rookschade. 
Daarnaast uitsluiting voor diefstal volgens VB12 tenzij 
aangifte is gedaan. Eigen risico bedraagt 500 euro 
conform clausule ER01."

→ 3 codes gevonden: 9NX3, VB12, ER01
→ Lengte: 950 tekens
→ Advies: SPLITSEN
```

---

#### **STAP 1: Clausulebibliotheek Check 📚**

**Doel:** Is deze tekst een standaardclausule?

**Hoe:**
```
Voor elke standaardclausule in de bibliotheek:
  1. Bereken gelijkenis met RapidFuzz
  2. Neem de hoogste score

Als score ≥95%:
  → Advies: VERVANGEN door clausulecode
  → Vertrouwen: HOOG

Als score 85-94%:
  → Advies: CONTROLEER GELIJKENIS met clausulecode
  → Vertrouwen: MIDDEN

Als score <85%:
  → Geen advies, ga door naar Stap 2
```

**Voorbeeld:**
```
Vrije tekst: "Dekking voor brandschade inclusief rookschade en bluswater"
Standaard 9NX3: "Dekking brandschade incl. rookschade en bluswaterschade"
RapidFuzz score: 96%

→ Advies: VERVANGEN door 9NX3
→ Vertrouwen: HOOG
```

---

#### **STAP 2: Voorwaarden Check - Is het al gedekt? 🔍**

Dit is de belangrijkste stap! Hier wordt de **Hybrid Similarity** gebruikt met 5 verschillende methoden.

**Doel:** Staat deze tekst al in de Algemene Voorwaarden?

---

##### **Methode 1: Exacte substring match (simpel maar krachtig)**

```
Zoek of de vereenvoudigde tekst EXACT voorkomt in de voorwaarden

Als JA:
  → Advies: VERWIJDEREN
  → Vertrouwen: HOOG (EXACT)
  → Reden: "Exact gevonden in voorwaarden"
```

**Voorbeeld:**
```
Vrije tekst: "Dekking voor brandschade"
Voorwaarden bevatten letterlijk: "...Dekking voor brandschade is..."

→ EXACT MATCH
→ Advies: VERWIJDEREN (HOOG vertrouwen)
```

---

##### **Methode 2: Hybrid Similarity (5 lagen)**

Als er geen exacte match is, wordt ELKE sectie uit de voorwaarden vergeleken met 5 verschillende methoden:

**De 5 methoden werken samen:**

```
┌────────────────────────────────────────────┐
│ Laag 5: Embeddings (25%)                  │ ← Betekenis
├────────────────────────────────────────────┤
│ Laag 4: Synoniemen (15%)                  │ ← "auto" = "voertuig"
├────────────────────────────────────────────┤
│ Laag 3: Lemmatisering (20%)               │ ← "verzekerd" = "verzekeren"
├────────────────────────────────────────────┤
│ Laag 2: TF-IDF (15%)                      │ ← Belangrijke woorden
├────────────────────────────────────────────┤
│ Laag 1: RapidFuzz (25%)                   │ ← Letterlijk
└────────────────────────────────────────────┘
                    ↓
        Totaalscore = gewogen gemiddelde
```

**Voor ELKE sectie in de voorwaarden:**

```python
# Pseudo-code om het te verduidelijken

voor elk artikel in voorwaarden:
  
  # Laag 1: RapidFuzz (letterlijke match)
  score_fuzzy = RapidFuzz(vrije_tekst, artikel_tekst)
  # Voorbeeld: 85%
  
  # Laag 2: TF-IDF (keyword overlap)
  belangrijke_woorden_vrij = ["brandschade", "dekking", "rookschade"]
  belangrijke_woorden_artikel = ["brandschade", "dekking", "bluswater"]
  score_tfidf = bereken_overlap(belangrijke_woorden_vrij, belangrijke_woorden_artikel)
  # Voorbeeld: 75% (2 van 3 woorden komen overeen)
  
  # Laag 3: Lemmatisering (woordvormen)
  vrije_tekst_lemma = ["dekking", "auto", "verzekeren"]
  artikel_tekst_lemma = ["dekking", "voertuig", "verzekeren"]
  score_lemma = RapidFuzz(vrije_tekst_lemma, artikel_tekst_lemma)
  # Voorbeeld: 88% ("auto" vs "voertuig" is enige verschil)
  
  # Laag 4: Synoniemen (vervang synoniemen)
  vrije_tekst_syn = "dekking voertuig verzekeren"  # auto→voertuig
  artikel_tekst_syn = "dekking voertuig verzekeren"
  score_syn = RapidFuzz(vrije_tekst_syn, artikel_tekst_syn)
  # Voorbeeld: 95% (na synoniemen bijna gelijk)
  
  # Laag 5: Embeddings (semantisch)
  vector_vrij = [0.2, 0.8, 0.1, ..., 0.5]
  vector_artikel = [0.3, 0.7, 0.1, ..., 0.6]
  score_embedding = cosine_similarity(vector_vrij, vector_artikel)
  # Voorbeeld: 92% (betekenis is vergelijkbaar)
  
  # TOTAALSCORE (gewogen gemiddelde)
  totaal = (
    0.25 × score_fuzzy +      # 25% gewicht
    0.15 × score_tfidf +      # 15% gewicht
    0.20 × score_lemma +      # 20% gewicht
    0.15 × score_syn +        # 15% gewicht
    0.25 × score_embedding    # 25% gewicht
  )
  
  # totaal = 0.25×85 + 0.15×75 + 0.20×88 + 0.15×95 + 0.25×92
  #        = 21.25 + 11.25 + 17.6 + 14.25 + 23
  #        = 87.35%
```

**Beslisboom op basis van totaalscore:**

```
Als score ≥90%:
  → Advies: VERWIJDEREN
  → Vertrouwen: HOOG
  → Referentie: Artikel nummer + pagina
  → Reden: "Bijna letterlijk in voorwaarden"

Als score 80-89%:
  → Advies: VERWIJDEREN
  → Vertrouwen: MIDDEN
  → Referentie: Artikel nummer
  → Reden: "Sterke overeenkomst met voorwaarden"

Als score 70-79%:
  → Advies: HANDMATIG CHECKEN
  → Vertrouwen: LAAG
  → Referentie: Artikel nummer
  → Reden: "Mogelijk variant van voorwaarden"

Als score <70%:
  → Geen match, ga door naar Stap 3
```

**Voorbeeld uitgewerkt:**

```
Vrije tekst: 
"Uw auto is verzekerd tegen brandschade"

Artikel 2.8 (pagina 5):
"Het voertuig is gedekt voor schade door brand"

Analyse:
─────────
Laag 1 - RapidFuzz: 65% (verschillende woorden)
Laag 2 - TF-IDF: 80% (brand/schade zijn belangrijke overlap)
Laag 3 - Lemma: 72% (verzekerd→verzekeren, gedekt→dekken helpt iets)
Laag 4 - Synoniemen: 95% (auto→voertuig, verzekerd→gedekt)
Laag 5 - Embeddings: 94% (betekenis is vrijwel identiek)

Totaal = 0.25×65 + 0.15×80 + 0.20×72 + 0.15×95 + 0.25×94
       = 16.25 + 12 + 14.4 + 14.25 + 23.5
       = 80.4%

→ Score 80-89% → Advies: VERWIJDEREN (MIDDEN vertrouwen)
→ Referentie: Art 2.8 (pagina 5)
```

**Zonder de nieuwe laag 3,4,5 zou de score slechts 65% zijn geweest (alleen fuzzy)!**

---

##### **Methode 3: Fragment matching (zinnen vergelijken)**

```
1. Splits de vrije tekst in zinnen
   "Dekking voor brand. Ook voor waterschade. Eigen risico 500 euro."
   → 3 zinnen

2. Check voor ELKE zin of die letterlijk in voorwaarden voorkomt

3. Tel hoeveel zinnen je gevonden hebt

Als >50% van de zinnen gevonden:
  → Advies: VERWIJDEREN
  → Reden: "Meerdere fragmenten uit voorwaarden"
```

**Voorbeeld:**
```
Vrije tekst zinnen:
1. "Dekking voor brandschade"
2. "Inclusief bluswater schade"
3. "Maximaal 50.000 euro"

Voorwaarden bevatten:
✅ "Dekking voor brandschade" → GEVONDEN
✅ "Inclusief bluswater schade" → GEVONDEN
❌ "Maximaal 50.000 euro" → NIET GEVONDEN

2 van 3 zinnen gevonden (66%)
→ Advies: VERWIJDEREN (tekst herhaalt voorwaarden)
```

---

#### **STAP 3: Fallback / Interne Analyse 🔧**

Als er geen match is in bibliotheek of voorwaarden, gebruikt het systeem intelligente regels:

##### **A) Keyword Rules (verzekeringslogica)**

```
Zoek naar specifieke keywords en pas regels toe:

Keywords "fraude" of "fraudebestrijding":
  → Standaard in voorwaarden
  → Advies: VERWIJDEREN (keyword: fraude)

Keyword "rangorde":
  → Standaardbepaling
  → Advies: VERWIJDEREN (keyword: rangorde)

Keywords "molest" + ("inclusief" of "meeverzekerd"):
  → Afwijking van standaard!
  → Advies: BEHOUDEN (CLAUSULE)
  → Reden: Molest normaal uitgesloten, dit is maatwerk

Keywords "cyber" of "cyberrisico":
  → Vaak maatwerk
  → Advies: BEHOUDEN (CLAUSULE)

En nog 20+ andere regels...
```

##### **B) Frequentie Analyse**

```
Kijk hoeveel keer deze cluster voorkomt:

Als frequentie ≥20:
  → Advies: STANDAARDISEREN
  → Reden: "Komt 25x voor - overweeg standaardclausule"

Als frequentie 2-19:
  → Advies: CONSISTENTIE_CHECK of FREQUENTIE_INFO
  → Reden: "Komt 5x voor - controleer consistentie"

Als frequentie = 1:
  → Advies: UNIEK
  → Reden: "Unieke tekst - mogelijk maatwerk"
```

##### **C) Lengte Check**

```
Als tekst >1000 tekens:
  → Advies: SPLITSEN_CONTROLEREN
  → Reden: "Zeer lange tekst - mogelijk meerdere onderwerpen"
```

##### **D) Laatste Fallback**

```
Als niks van bovenstaande matcht:

Zonder voorwaarden:
  → Advies: HANDMATIG CHECKEN
  → Reden: "Geen voorwaarden beschikbaar voor vergelijking"

Met voorwaarden:
  → Advies: HANDMATIG CHECKEN
  → Reden: "Geen automatische match - mogelijk maatwerk"
  → Vertrouwen: LAAG
```

---

## STAP 5: Excel Rapport Maken 📊

### Welke tools worden gebruikt?

#### **openpyxl** (Excel schrijver)
- **Wat doet het?** Maakt Excel bestanden (.xlsx)
- **Hoe werkt het?** Bouwt rij voor rij een Excel bestand op

### Wat gebeurt er?

```
1. Maak DataFrame (tabel) met alle resultaten:
   
   Kolommen:
   - Cluster ID
   - Advies
   - Vertrouwen
   - Reden
   - Artikel Referentie
   - Frequentie
   - Originele Tekst
   - Vereenvoudigde Tekst
   - Polisnummers

2. Splits in 2 sheets:
   
   Sheet 1: "Analyseresultaten"
   → Alle normale clusters
   → Alleen advies ≠ SPLITSEN
   
   Sheet 2: "Te Splitsen & Complex"
   → Alle SPLITSEN adviezen
   → PARENT/CHILD structuur voor breitexten

3. Voeg opmaak toe:
   - Kleuren per advies
   - Filters bovenaan
   - Kolombreedte automatisch
   - Tekst wrap voor lange teksten

4. Zet om naar bytes (voor download)
```

---

## STAP 6: Resultaten Tonen 🎨

De interface toont:

**Statistieken bovenaan:**
```
- Totaal verwerkte rijen
- Aantal clusters
- Reductie percentage (bijv. 10.000 rijen → 500 clusters = 95% reductie)
```

**Grafiek:**
```
Cirkeldiagram met verdeling:
- 40% VERWIJDEREN
- 25% VERVANGEN
- 15% HANDMATIG CHECKEN
- 10% BEHOUDEN
- 10% Overig
```

**Tabel met eerste 10 resultaten**
```
Per cluster zie je:
- ID, Advies, Frequentie, Vertrouwen
- Reden, Artikel, Originele tekst
```

**Download knop** → Laad Excel bestand

---

## 🎯 Samenvatting voor de Demo

### Simpele Uitleg (30 seconden):

> "Als je op Start drukt, leest het systeem eerst alle bestanden in en maakt de teksten 'schoon' (normaliseren). Dan groepeert het alle dubbele of bijna-gelijke teksten (clustering met RapidFuzz). Vervolgens vergelijkt het ELKE groep op 5 verschillende manieren tegen de voorwaarden (fuzzy, lemma's, synoniemen, keywords, betekenis) en bepaalt wat je ermee moet doen. Tot slot maakt het een Excel rapport met alle adviezen."

### Uitgebreide Uitleg (2 minuten):

> "Het systeem werkt in 6 stappen:
> 
> **1) Inlezen:** We gebruiken pandas om Excel/CSV te lezen en normaliseren alle teksten (kleine letters, geen accenten).
> 
> **2) Voorwaarden:** Met PyMuPDF halen we artikelen uit de PDF voorwaarden.
> 
> **3) Clustering:** Het Leader algoritme groepeert teksten - het vergelijkt elke tekst met maximaal de laatste 50 groepen met RapidFuzz (similariteit score). Eerst check het op exacte matches, dan op genormaliseerde matches (zonder bedragen/datums), en als laatste met fuzzy matching. Dit is veel sneller dan alles met alles vergelijken.
> 
> **4) Analyse - Dit is de kern:**
> - Eerst admin checks (lege teksten, placeholders)
> - Dan clausulebibliotheek check (RapidFuzz score >95% = vervangen)
> - Dan de slimme voorwaarden-check met 5 lagen:
>   * RapidFuzz voor letterlijke match
>   * SpaCy voor lemmatisering (verzekerd → verzekeren)
>   * Gensim TF-IDF voor belangrijke woorden
>   * WordNet + eigen synoniemen voor auto ↔ voertuig
>   * Embeddings voor semantische betekenis
> - Die 5 scores worden gewogen gemiddeld (25%, 20%, 15%, 15%, 25%)
> - Score >90% = VERWIJDEREN, 80-90% = VERWIJDEREN met review, 70-80% = handmatig checken
> - Als geen match: keyword rules, frequentie-analyse, lengte checks
> 
> **5) Excel:** openpyxl maakt het rapport met 2 sheets (normale + complexe gevallen)
> 
> **6) Interface:** Toont statistieken, grafiek en tabel met resultaten."

### Waarom is versie 3.0 beter?

> "De oude versie deed alleen letterlijke tekstmatching met RapidFuzz (Laag 1). Die miste veel matches omdat mensen dingen anders formuleren.
> 
> De nieuwe versie (3.0) voegt 4 lagen toe:
> - **Lemma's:** Herkent verschillende woordvormen
> - **Synoniemen:** Weet dat auto = voertuig
> - **TF-IDF:** Focust op belangrijke woorden
> - **Embeddings:** Begrijpt de betekenis
> 
> Het resultaat: 15-25% meer automatische matches, minder handmatig werk!"

---

## 🔧 Belangrijke Configuratie (voor geavanceerde vragen)

Als iemand vraagt hoe je het kunt aanpassen:

**Clustering nauwkeurigheid:**
- Standaard: 90% (zeer streng, weinig vals-positieven)
- Lager (85%): Meer clusters groeperen (meer reductie, maar kans op vals-positieven)
- Hoger (95%): Minder clusters groeperen (minder reductie, maar zekerder)

**Gewichten Hybrid Similarity:**
- Pas aan in `config.py`:
  ```
  weight_rapidfuzz: 0.25 (25%)
  weight_lemmatized: 0.20 (20%)
  weight_tfidf: 0.15 (15%)
  weight_synonyms: 0.15 (15%)
  weight_embeddings: 0.25 (25%)
  ```
- Som moet altijd 1.0 zijn (100%)

**Drempels:**
- Bibliotheek match: 95% = vervangen, 85% = controleren
- Voorwaarden exact: 90% = hoog, 80% = midden, 70% = laag
- Frequentie standaardiseren: 20x (instelbaar)
- Brei detectie: 800 tekens + >1 code

---

*Dit document is bedoeld om achter de schermen uit te leggen voor demo-doeleinden. Gebruik het om te begrijpen WAT alle componenten doen, niet hoe je ze moet gebruiken (dat staat in GEBRUIKERSSTAPPENPLAN.md).*

**Laatst bijgewerkt: v3.0.0 - Semantic Enhancement (2025)**

