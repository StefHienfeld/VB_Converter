# Uitleg Excel Output Kolommen

Dit document legt uit welke extra kolommen door het systeem worden gegenereerd in de Excel-export.

## Basis Structuur

De Excel heeft **één sheet**:
- **"Analyseresultaten"** - Alle geanalyseerde vrije teksten (één rij per input rij)

**GEWIJZIGD (v4.0):** De oude "Te Splitsen & Complex" sheet is verwijderd. Lange teksten krijgen nu het advies "HANDMATIG CHECKEN" in plaats van automatisch gesplitst te worden.

---

## Extra Gegenereerde Kolommen

### 1. **Status** (NIEUW)
- **Wat:** Lege kolom voor handmatige tracking door de gebruiker
- **Doel:** Bijhouden welke rijen al verwerkt zijn
- **Gebruik:** Vul zelf in tijdens het verwerken (bijv. "✓", "In behandeling", "Naar ICT")
- **Voorbeeld:** `✓` of `In behandeling`

### 2. **Cluster_ID**
- **Wat:** Unieke identifier voor het cluster (bijv. "cluster_1", "cluster_2")
- **Doel:** Elke groep van vergelijkbare clausules krijgt hetzelfde Cluster_ID
- **Gebruik:** Hiermee kun je zien welke clausules bij elkaar horen
- **Voorbeeld:** `cluster_42`

### 3. **Cluster_Naam** (VERBETERD)
- **Wat:** Semantische samenvatting van het cluster via NLP keyword extraction
- **Doel:** Snel overzicht krijgen van het onderwerp van het cluster
- **Gebruik:** Helpt bij het identificeren van clusters zonder de volledige tekst te lezen
- **Voorbeeld:** `"VB12 Fraudecheck Aansprakelijkheid"` of `"Premie Naverrekening"`
- **GEWIJZIGD (v4.0):** Nu gebaseerd op NLP noun phrase extraction in plaats van eerste N woorden

### 3. **Frequentie**
- **Wat:** Aantal keer dat deze clausule (of zeer vergelijkbare) voorkomt in de dataset
- **Doel:** Inzicht in duplicaten en veelvoorkomende patronen
- **Gebruik:** Hoge frequentie = veel duplicaten, mogelijk standaardiseren
- **Voorbeeld:** `15` (betekent: deze clausule komt 15x voor)

### 5. **Advies**
- **Wat:** Aanbeveling van het systeem wat te doen met deze clausule
- **Mogelijke waarden:**
  - `VERWIJDEREN` - Duplicaat gevonden, verwijderen
  - `🛠️ STANDAARDISEREN` - Tekst standaardiseren (veelvoorkomend patroon)
  - `BEHOUDEN (CLAUSULE)` - Unieke clausule, behouden
  - `HANDMATIG CHECKEN` - Systeem is onzeker of tekst te lang, handmatig beoordelen
  - `📊 FREQUENTIE INFO` - Informatie over frequentie (zonder voorwaarden)
  - `🔄 CONSISTENTIE CHECK` - Controleren op consistentie
  - `✨ UNIEK` - Unieke clausule
  - `🧹 OPSCHONEN` - Tekst heeft encoding problemen, opschonen
  - `📝 AANVULLEN` - Tekst is incompleet (placeholders, ontbrekende info)
  - `📅 VERWIJDEREN (VERLOPEN)` - Verwijst naar verleden datum, niet meer relevant
  - `⚪ LEEG` - Lege tekst
  - `❌ ONLEESBAAR` - Tekst is onleesbaar/corrupt
  - `📋 [CUSTOM ACTION]` - **NIEUW (v4.2):** Custom instructie match (bijv. `📋 Vullen in partijenkaart`)
- **Doel:** Directe actie-aanbeveling voor elke clausule
- **Gebruik:** Filter/sorteer op Advies om prioriteiten te stellen
- **GEWIJZIGD (v4.0):** SPLITSEN/GESPLITST advies verwijderd - lange teksten krijgen "HANDMATIG CHECKEN"
- **NIEUW (v4.2):** Custom instructies via tabel-interface - als zoektekst voorkomt in clausule → custom actie

### 5. **Vertrouwen**
- **Wat:** Betrouwbaarheidsniveau van de analyse (Laag/Midden/Hoog)
- **Mogelijke waarden:**
  - `Hoog` - Systeem is zeer zeker van de aanbeveling
  - `Midden` - Redelijke zekerheid, maar controle aanbevolen
  - `Laag` - Onzeker, handmatige controle vereist
- **Doel:** Inzicht in betrouwbaarheid van automatische analyse
- **Gebruik:** Focus eerst op "Hoog" vertrouwen voor snelle winst

### 6. **Reden**
- **Wat:** Uitleg waarom het systeem deze aanbeveling geeft
- **Doel:** Transparantie en begrip van de analyse
- **Gebruik:** Helpt bij het begrijpen van de logica achter het advies
- **Voorbeelden:**
  - `"Gevonden in voorwaarden: Art 2.8 (95% match)"`
  - `"Hoge frequentie (20x), standaardiseren aanbevolen"`
  - `"Gesplitst in 3 onderdelen: 2x VERWIJDEREN, 1x BEHOUDEN"`
  - `"Bevat verouderde datum: 2020-01-15"`
  - `"Komt overeen met instructie: 'meeverzekerde' (100% match)"` - **NIEUW (v4.2):** Custom instructie match

### 7. **Artikel** (VERBETERD)
- **Wat:** Referentie naar artikel/sectie in de polisvoorwaarden (indien gevonden)
- **Doel:** Directe link naar de bron in de voorwaarden
- **Gebruik:** Snel opzoeken in de voorwaarden waar deze clausule vandaan komt
- **Voorbeeld:** `"Art 2.8 - Fraude en Misleiding"`, `"Art 3.2"`, of `"Voorwaarden, pagina 5"`
- **GEWIJZIGD (v4.0):** Bevat nu de titel van het artikel wanneer beschikbaar (max 80 karakters)

### 8. **Tekst**
- **Wat:** De originele clausule tekst zoals ingelezen
- **Doel:** Volledige tekst voor referentie
- **Gebruik:** Lezen van de daadwerkelijke clausule inhoud

### 9. **[Originele Input Kolommen]**
- **Wat:** Alle kolommen uit het oorspronkelijke input bestand (bijv. Polisnummer, Vervaldatum, Product, etc.)
- **Doel:** Behoud van alle originele data voor referentie
- **Gebruik:** Context bij het verwerken van advies
- **Opmerking:** Deze kolommen staan achteraan in de Excel voor leesbaarheid

---

## Originele Kolommen

Naast de bovenstaande gegenereerde kolommen worden **alle originele kolommen** uit het inputbestand behouden. Dit kunnen zijn:
- Polisnummer
- Datum
- Categorie
- Of andere kolommen die in je input Excel/CSV stonden

Deze worden automatisch gedetecteerd en toegevoegd aan de output.

---

## Hiërarchische Structuur (PARENT/CHILD)

Voor complexe clausules die gesplitst moeten worden:

### PARENT Row
- Bevat volledige cluster informatie
- `Advies` = `⚠️ GESPLITST` of `⚠️ ZIE ONDERSTAANDE DELEN`
- `Reden` = Samenvatting van alle child adviezen (bijv. "Gesplitst in 3 onderdelen: 2x VERWIJDEREN, 1x BEHOUDEN")
- Bevat originele kolommen van het inputbestand
- Bevat `Nieuwe_Systeem_Tekst` als voorstel beschikbaar is

### CHILD Row
- Bevat alleen het gesplitste onderdeel
- `Tekst` = Ingesprongen met `"    ↳ "` om hiërarchie te tonen
- `Cluster_Naam` en `Frequentie` = Leeg (niet van toepassing)
- `Nieuwe_Systeem_Tekst` = Leeg
- Originele kolommen = Leeg (alleen parent heeft deze)
- Heeft eigen `Advies`, `Vertrouwen`, `Reden`, `Artikel` voor dat specifieke onderdeel

---

## Voorbeeld Output Structuur

```
Cluster_ID | Cluster_Naam | Frequentie | Advies | Vertrouwen | Reden | Artikel | Tekst | Nieuwe_Systeem_Tekst | [Originele kolommen...]
-----------|--------------|------------|--------|------------|-------|---------|-------|---------------------|------------------------
cluster_1  | "De verzek..." | 15 | VERWIJDEREN | Hoog | "Gevonden in voorwaarden: Art 2.8" | Art 2.8 | "De verzekerde..." | "" | [data...]
cluster_2  | "Bij schade..." | 1 | BEHOUDEN | Hoog | "Unieke clausule" | - | "Bij schade..." | "" | [data...]
cluster_3  | "Complex..." | 5 | ⚠️ GESPLITST | Midden | "Gesplitst in 2 onderdelen: 1x VERWIJDEREN, 1x BEHOUDEN" | - | "Complex clausule..." | "Voorgestelde tekst" | [data...]
  ↳ (CHILD) | "" | 0 | VERWIJDEREN | Hoog | "Gevonden in voorwaarden" | Art 3.1 | "    ↳ Eerste deel..." | "" | [leeg...]
  ↳ (CHILD) | "" | 0 | BEHOUDEN | Hoog | "Uniek onderdeel" | - | "    ↳ Tweede deel..." | "" | [leeg...]
```

---

## Tips voor Gebruik

1. **Filter op Advies** - Groepeer alle VERWIJDEREN items samen
2. **Sorteer op Frequentie** - Begin met hoogste frequentie (meeste impact)
3. **Check Vertrouwen** - Focus eerst op "Hoog" vertrouwen items
4. **Gebruik Cluster_ID** - Groepeer alle duplicaten samen
5. **Lees Reden** - Begrijp waarom het systeem deze aanbeveling geeft
6. **Check Artikel** - Verifieer tegen de voorwaarden
7. **Gebruik Nieuwe_Systeem_Tekst** - Directe implementatie van standaardisatie


