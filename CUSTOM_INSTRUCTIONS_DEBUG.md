# Custom Instructions Debugging Guide

## Probleem
Custom instructions worden niet toegepast - clausules met "medeverzekerde" krijgen "UNIEK" advies in plaats van "Vullen in partijenkaart".

## Diagnose Resultaten

### ✅ Code werkt correct
De standalone test (`test_custom_instructions.py`) toont aan dat de matching logica perfect werkt:
- TSV parsing: ✅ Werkt
- Contains matching: ✅ Werkt
- "medeverzekerde" wordt gevonden in langere teksten: ✅ Werkt

### ❓ Mogelijk probleem
De custom instructions worden waarschijnlijk **niet geladen** tijdens de echte analyse. Dit kan twee oorzaken hebben:

1. **Frontend → Backend**: De instructies worden niet meegestuurd in de API call
2. **Backend**: De instructies worden niet correct verwerkt/geladen

## Testing Stappen

### Stap 1: Check Backend Logs

Start de backend met uitgebreide logging:

```bash
cd /Users/stef/Code/dev/VB_Converter
uvicorn hienfeld_api.app:app --reload --port 8000 --log-level debug
```

Let op deze log regels tijdens analyse:

```
============================================================
CUSTOM INSTRUCTIONS LADEN
============================================================
Raw input length: X characters
Raw input (first 200 chars): medeverzekerde	Vullen in partijenkaart
✅ Parsed 1 custom instructions
  Instruction 1:
    Search text: 'medeverzekerde'
    Action: 'Vullen in partijenkaart'
============================================================
```

**Belangrijk:** 
- Zie je deze logs NIET? → Custom instructions worden niet meegegeven aan backend
- Zie je "Parsed 0 custom instructions"? → Parsing probleem
- Zie je wel instructions maar geen matches? → Check de debug logs van `find_match()`

### Stap 2: Check of Custom Instructions Match Worden Toegepast

Zoek in de logs naar:

```
Step 0.5: Checking cluster CL-XXXX (text: '...')
✅ Custom instruction match (contains): '...' -> 'Vullen in partijenkaart'
Step 0.5: ✅ MATCH for cluster CL-XXXX! (score: 1.0, action: 'Vullen in partijenkaart')
```

Als je deze ziet, werkt het! Dan zou je advies "📋 Vullen in partijenkaart" moeten zijn.

### Stap 3: Test met API Endpoint

Je kunt ook direct testen via de API zonder volledige analyse:

```bash
curl -X POST "http://localhost:8000/api/test-custom-instructions" \
  -F "instructions_text=medeverzekerde	Vullen in partijenkaart" \
  -F "test_clause=VB1 # Als medeverzekerde is aangetekend mw. M. Kersloot-Lakemond."
```

Dit zou moeten returnen:

```json
{
  "success": true,
  "matching": {
    "found_match": true,
    "match_details": {
      "action": "Vullen in partijenkaart",
      "score": 1.0
    }
  }
}
```

### Stap 4: Check Frontend

Open browser developer console (F12) en check:
1. Ga naar Network tab
2. Start een analyse met custom instructions
3. Zoek de POST naar `/api/analyze`
4. Check de Form Data - zie je `extra_instruction: medeverzekerde	Vullen in partijenkaart`?

Als je dit NIET ziet → probleem in frontend (instructies worden niet meegestuurd)

## Mogelijke Oplossingen

### Als custom instructions niet worden geladen:

**Optie 1: Frontend probleem**
- Check of `ExtraInstructionInput` component correct serialiseert
- Verifieer dat `onChange` wordt aangeroepen
- Check of de waarde in de form state zit voordat je submit

**Optie 2: Backend probleem**
- Check of `extra_instruction` parameter wordt ontvangen in `/api/analyze`
- Verifieer dat de parameter wordt doorgegeven aan `_run_analysis_job`
- Check of `CustomInstructionsService` wordt geïnitialiseerd

### Quick Fix Test

Om te testen of het een frontend of backend issue is:

1. Start backend met logs
2. Gebruik cURL direct om te testen:

```bash
# Maak een simpel test CSV
echo "Tekst" > test.csv
echo "Als medeverzekerde is aangetekend mw. M. Kersloot" >> test.csv

# Test met cURL
curl -X POST "http://localhost:8000/api/analyze" \
  -F "policy_file=@test.csv" \
  -F "extra_instruction=medeverzekerde	Vullen in partijenkaart" \
  -F "cluster_accuracy=90"
```

Check de logs:
- Zie je de custom instructions laden? → Frontend probleem
- Zie je ze niet? → Backend parameter verwerking probleem

## Next Steps

Na het uitvoeren van bovenstaande tests, rapporteer:
1. Zie je de "CUSTOM INSTRUCTIONS LADEN" logs?
2. Hoeveel instructions worden geparsed?
3. Zie je match pogingen in de logs?
4. Zie je matches succesvol?

Dan kunnen we het exacte probleem identificeren en oplossen!

