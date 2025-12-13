# VB Converter - Stappenplan voor Acceptanten

## Wat doet de tool?

De VB Converter analyseert vrije teksten op polissen en geeft advies over wat je ermee moet doen. De tool:
- **Groepeert** gelijke of bijna-gelijke teksten (clustering)
- **Vergelijkt** elke tekst tegen de Algemene Voorwaarden
- **Vergelijkt** tegen de Standaardclausulebibliotheek
- **Herkent synoniemen** zoals "auto" ↔ "voertuig" of "verzekerd" ↔ "gedekt" (v3.0)
- **Begrijpt betekenis** door semantische analyse (v3.0)
- **Geeft advies** per groep: verwijderen, vervangen, behouden, etc.

---

## Stap 1: Upload Polisbestand (verplicht)

**Wat je uploadt:**
- Een Excel- of CSV-bestand met alle vrije teksten van de polissen
- De tool zoekt automatisch de kolom met "Tekst" of "Vrije Tekst"

**Wat de tool doet:**
- Leest alle rijen in
- Normaliseert teksten (kleine letters, accenten, spaties)
- Groepeert teksten die (bijna) hetzelfde zijn

**Voorbeeld:** Als je 100 polissen hebt met dezelfde tekst "Dekking voor brandschade", worden die gegroepeerd in 1 cluster met frequentie 100.

---

## Stap 2: Upload Voorwaarden (optioneel, maar sterk aanbevolen)

**Wat je uploadt:**
- PDF, Word of TXT-bestand met de Algemene Voorwaarden
- Je kunt meerdere bestanden uploaden (bijv. verschillende productvoorwaarden)

**Wat de tool doet:**
- Leest alle artikelen uit de voorwaarden
- Vergelijkt elke vrije tekst tegen deze voorwaarden op **5 verschillende manieren** (v3.0):
  1. **Letterlijk:** Exacte tekstovereenkomst
  2. **Genormaliseerd:** "auto's" = "auto", "verzekerd" = "verzekeren"
  3. **Synoniemen:** "voertuig" = "auto", "gedekt" = "verzekerd"
  4. **Keywords:** Belangrijke woorden en termen
  5. **Betekenis:** Begrijpt parafrasen zoals "bij gedwongen verhuizing" = "wanneer u verplicht bent te verhuizen"
- **Als een tekst al in de voorwaarden staat → advies: VERWIJDEREN**

**Waarom belangrijk:**
- Zonder voorwaarden kan de tool niet bepalen of iets al gedekt is
- Met voorwaarden krijg je betere adviezen (minder onnodige teksten op de polis)
- De nieuwe semantische matching (v3.0) vindt **15-25% meer matches** dan voorheen

---

## Stap 3: Upload Clausulebibliotheek (optioneel)

**Wat je uploadt:**
- **Optie A:** Een Excel-bestand met kolommen: Code, Tekst, Categorie
- **Optie B:** Meerdere losse bestanden (PDF/Word) - elk bestand = 1 clausule

**Wat de tool doet:**
- Leest alle standaardclausules in
- Vergelijkt elke vrije tekst tegen deze bibliotheek
- **Als een tekst sterk lijkt op een standaardclausule → advies: VERVANGEN door code**

**Voorbeeld:** 
- Vrije tekst: "Dekking voor brandschade inclusief rookschade..."
- Match met standaardclausule `9NX3` (95% gelijk)
- **Advies:** Vervang door clausulecode `9NX3`

---

## Stap 4: Start Analyse

Klik op **"Start Analyse"**. De tool doorloopt nu:

1. **Clustering:** Groepeert gelijke teksten
2. **Vergelijking:** Checkt elke groep tegen voorwaarden en clausulebibliotheek
3. **Analyse:** Berekent per groep welk advies het beste is
4. **Rapport:** Genereert Excel met alle resultaten

**Duur:** Afhankelijk van aantal rijen (meestal 1-5 minuten)

---

## Stap 5: Lees de Output

### In de Web Interface

**Bovenaan zie je:**
- **Verwerkte Rijen:** Totaal aantal polisregels
- **Reductie:** Percentage unieke groepen (lager = meer duplicaten)
- **Clusters:** Aantal unieke tekstgroepen

**In de tabel zie je per cluster:**
- **Cluster naam/ID:** Unieke identifier (bijv. CL-0001)
- **Originele tekst:** Voorbeeldtekst uit deze groep
- **Frequentie:** Hoe vaak deze tekst voorkomt
- **Advies:** Wat je moet doen (zie hieronder)
- **Vertrouwen:** Hoog/Midden/Laag
- **Reden:** Waarom dit advies
- **Artikel:** Referentie naar voorwaarden (als van toepassing)

### In het Excel Rapport

Het Excel-bestand bevat:
- **Analyseresultaten sheet:** Alle clusters met adviezen
- **Te Splitsen & Complex sheet:** Complexe gevallen die handmatige aandacht nodig hebben
- **Cluster Samenvatting sheet:** Overzicht per cluster

**Kolommen in Excel:**
- `Cluster ID`: Unieke identifier
- `Advies`: Wat te doen
- `Frequentie`: Hoe vaak deze tekst voorkomt
- `Vertrouwen`: Hoog/Midden/Laag
- `Reden`: Uitleg
- `Referentie Artikel`: Waar staat dit in de voorwaarden
- `Originele Tekst`: De volledige tekst

---

## Wat betekenen de Adviezen?

### 🗑️ **VERWIJDEREN**
**Wat het betekent:** Deze tekst staat al in de Algemene Voorwaarden.

**Wat je moet doen:**
- Verwijder deze tekst van de polis
- Het is dubbelop en niet nodig

**Vertrouwen:** Meestal Hoog (exacte match) of Midden (bijna identiek)

**Voorbeeld:**
- Vrije tekst: "Dekking voor brandschade"
- Staat in: Artikel 2.1 van de voorwaarden
- **Advies:** VERWIJDEREN (Hoog vertrouwen)

---

### 🔄 **VERVANGEN** (of "CONTROLEER GELIJKENIS")
**Wat het betekent:** Deze tekst lijkt sterk op een standaardclausule uit de bibliotheek.

**Wat je moet doen:**
- Vervang de volledige tekst door de clausulecode (bijv. `9NX3`)
- Dit maakt de polis korter en consistenter

**Vertrouwen:** 
- ≥95% match → Direct vervangen
- 85-95% match → Eerst handmatig controleren of het echt hetzelfde is

**Voorbeeld:**
- Vrije tekst: "Dekking voor brandschade inclusief rookschade en waterschade door bluswater"
- Match met: Standaardclausule `9NX3` (96% gelijk)
- **Advies:** VERVANGEN door `9NX3`

---

### ⚠️ **SPLITSEN** of **SPLITSEN/CONTROLEREN**
**Wat het betekent:** Deze tekst bevat meerdere clausules in één regel (een "brei").

**Wat je moet doen:**
- Splits de tekst op in aparte clausules
- Beoordeel elk deel apart

**Hoe herken je het:**
- Lange tekst (>800 tekens)
- Bevat meerdere clausulecodes (bijv. `9NX3` en `VB12` in één tekst)

**Voorbeeld:**
- Vrije tekst: "Dekking voor brandschade 9NX3. Uitsluiting voor diefstal VB12. Eigen risico 500 euro."
- **Advies:** SPLITSEN in 3 aparte clausules

---

### 🛠️ **STANDAARDISEREN**
**Wat het betekent:** Deze tekst komt vaak voor (≥20x) maar is nog geen standaardclausule.

**Wat je moet doen:**
- Overweeg om hier een nieuwe standaardclausule van te maken
- Dit voorkomt dat je steeds dezelfde tekst moet intypen

**Voorbeeld:**
- Vrije tekst: "Dekking voor glasbreuk tot max 5000 euro"
- Frequentie: 25x
- **Advies:** STANDAARDISEREN (maak clausulecode `GL01`)

---

### ✅ **BEHOUDEN (CLAUSULE)**
**Wat het betekent:** Dit is waarschijnlijk maatwerk of een afwijking van de standaard.

**Wat je moet doen:**
- Behoud de tekst zoals hij is
- Het is specifiek voor deze polis

**Voorbeeld:**
- Vrije tekst: "Dekking voor molest inclusief cyberrisico" (afwijking van standaard)
- **Advies:** BEHOUDEN (CLAUSULE)

---

### 👁️ **HANDMATIG CHECKEN**
**Wat het betekent:** De tool is niet zeker wat je moet doen.

**Wat je moet doen:**
- Lees de tekst zelf
- Beslis handmatig: verwijderen, behouden, of aanpassen

**Wanneer krijg je dit:**
- Tekst is te kort of onduidelijk
- Match met voorwaarden is zwak (70-80%)
- Geen duidelijke match met clausulebibliotheek
- Unieke tekst die weinig voorkomt

---

### 🧹 **OPSCHONEN**, **AANVULLEN**, **LEEG**
**Wat het betekent:** Er is een technisch probleem met de tekst.

**Wat je moet doen:**
- **OPSCHONEN:** Tekst bevat vreemde karakters → opschonen
- **AANVULLEN:** Tekst is incompleet (bijv. "Zie artikel...") → aanvullen
- **LEEG:** Lege regel → verwijderen

---

## Tips voor het lezen van de output

1. **Begin met VERWIJDEREN (Hoog vertrouwen):** Deze zijn het makkelijkst - gewoon weghalen.

2. **Kijk naar Frequentie:** 
   - Hoge frequentie (bijv. 50x) = veel polissen hebben dit → prioriteit
   - Lage frequentie (1-2x) = uniek → minder urgent

3. **Let op Vertrouwen:**
   - **Hoog:** Je kunt dit advies meestal direct opvolgen
   - **Midden:** Controleer even of het klopt
   - **Laag:** Altijd handmatig checken

4. **Gebruik de Referentie Artikel kolom:**
   - Als er een artikel staat (bijv. "Art 2.8"), kijk daar even na
   - Dit helpt je begrijpen waarom het advies VERWIJDEREN is

5. **Complexe gevallen (SPLITSEN):**
   - Deze staan in het aparte sheet "Te Splitsen & Complex"
   - Neem hier de tijd voor - vaak meerdere clausules in één

6. **Download het Excel:**
   - Gebruik het Excel-bestand voor je werk
   - Je kunt filteren/sorteren op advies, frequentie, etc.

---

## Veelgestelde Vragen

**Q: Moet ik altijd Voorwaarden uploaden?**  
A: Nee, maar het is sterk aanbevolen. Zonder voorwaarden kan de tool niet bepalen of iets al gedekt is.

**Q: Wat als ik geen Clausulebibliotheek heb?**  
A: Geen probleem. De tool werkt ook zonder, maar je krijgt dan geen "VERVANGEN" adviezen.

**Q: Hoe lang duurt een analyse?**  
A: Meestal 1-5 minuten, afhankelijk van het aantal rijen. Je ziet de voortgang in de interface. De nieuwe semantische analyse (v3.0) voegt 30-60 seconden toe, maar vindt veel meer matches.

**Q: Kan ik de instellingen aanpassen?**  
A: Ja, via het tandwiel-icoon rechtsboven. Pas aan:
- **Cluster nauwkeurigheid:** Hoe streng moet de match zijn? (standaard 90%)
- **Minimum frequentie:** Vanaf hoeveel keer wordt iets "STANDAARDISEREN"? (standaard 20x)

**Q: Wat als ik het niet eens ben met een advies?**  
A: Dat kan! De tool is een hulpmiddel, geen wet. Gebruik je eigen oordeel, vooral bij "HANDMATIG CHECKEN" en "Midden" vertrouwen.

**Q: Wat is nieuw in versie 3.0?**  
A: **Slimmere matching!** De tool herkent nu:
- Synoniemen: "auto" = "voertuig", "woning" = "huis"
- Varianten: "verzekerd" = "gedekt" = "meeverzekerd"
- Betekenis: Begrijpt parafrasen en omschrijvingen
- **Resultaat:** 15-25% meer automatische matches, minder handmatig werk!

---

## Samenvatting in 3 stappen

1. **Upload:** Polisbestand + (optioneel) Voorwaarden + (optioneel) Clausulebibliotheek
2. **Start:** Klik "Start Analyse" en wacht 1-5 minuten
3. **Werk af:** Download Excel, sorteer op advies, werk cluster voor cluster af

**Prioriteit volgorde:**
1. VERWIJDEREN (Hoog) → snel weg
2. VERVANGEN (≥95%) → vervang door code
3. STANDAARDISEREN → overweeg nieuwe clausule
4. HANDMATIG CHECKEN → neem de tijd

---

## 🆕 Nieuw in v3.0: Slimmere Tekstherkenning

De tool is nu **veel beter** in het herkennen van gelijke teksten, zelfs als ze anders geschreven zijn:

### Voorbeelden van wat de tool nu herkent:

**Synoniemen:**
- "Dekking voor **auto**" = "Verzekering van **voertuig**" ✅
- "Schade is **gedekt**" = "Risico is **verzekerd**" ✅
- "Eigen **huis**" = "Eigen **woning**" ✅

**Variaties:**
- "Auto's zijn verzekerd" = "Auto is verzekerd" ✅
- "Verzekering van voertuigen" = "Voertuig verzekeren" ✅

**Parafrasen (zelfde betekenis, andere woorden):**
- "Bij gedwongen verhuizing" = "Wanneer u verplicht bent te verhuizen" ✅
- "Kosten van evacuatie" = "Dekking bij noodgedwongen evacuatie" ✅

**Impact:**
- 🎯 **+15-25% meer automatische matches**
- ⏱️ **Minder handmatig werk**
- ✅ **Betere kwaliteit adviezen**

De tool draait volledig lokaal - geen externe API's, geen extra kosten!

---

*Laatste update: v3.0.0 - Semantic Enhancement (2025)*

