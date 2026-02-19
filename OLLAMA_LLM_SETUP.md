# LLM voor Twijfelgevallen - Ollama Setup Gids

## Overzicht

De Hienfeld VB Converter heeft built-in LLM-ondersteuning voor twijfelgevallen (similarity score 70-85%). 
Standaard is deze functionaliteit **uitgeschakeld** (`client=None`).

## Opties

| Optie | Pro | Con |
|-------|-----|-----|
| **Ollama (lokaal)** | Geen API-kosten, GDPR-proof, offline | ≥16 GB RAM vereist |
| **OpenAI API** | Geen hardware, sneller, beter model | Kosten per call, data naar externe server |
| **Uitgeschakeld** | Niets te installeren | Twijfelgevallen blijven "HANDMATIG CHECKEN" |

## Aanbeveling: Ollama Lokaal

Voor enterprise/GDPR-gebruik wordt **Ollama** aanbevolen.

### 1. Installeer Ollama

**Linux/Mac:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download van https://ollama.com/download

### 2. Download een model

```bash
# Llama 3.1 8B (aanbevolen - goede balans tussen snelheid en kwaliteit)
ollama pull llama3.1:8b

# Of Llama 3.1 70B (hogere kwaliteit, langzamer, vereist >32GB RAM)
ollama pull llama3.1:70b
```

### 3. Start Ollama server

```bash
ollama serve
```

Dit start de server op `http://localhost:11434`

### 4. Configureer de app

**Optie A: Via environment variabele**
```bash
export OLLAMA_LLM_ENABLED=true
export OLLAMA_MODEL=llama3.1:8b
export OLLAMA_BASE_URL=http://localhost:11434
```

**Optie B: In code (hienfeld_api/factories/service_factory.py)**

Zoek de regel:
```python
llm_client = None  # LLM disabled by default
```

Vervang door:
```python
# Enable Ollama
try:
    from openai import OpenAI
    llm_client = OpenAI(
        base_url="http://localhost:11434/v1",  # Ollama endpoint
        api_key="ollama"  # Dummy key (Ollama requires this but doesn't use it)
    )
    model_name = "llama3.1:8b"
    logger.info("✅ Ollama LLM enabled")
except Exception as e:
    logger.warning(f"Ollama not available: {e}")
    llm_client = None
```

### 5. Drempelwaarden instellen

In `hienfeld/config.py`, stel de LLM trigger thresholds in:

```python
class AIConfig:
    llm_enabled: bool = True
    llm_uncertainty_min: float = 0.70  # Activeer LLM voor scores ≥70%
    llm_uncertainty_max: float = 0.85  # Activeer LLM voor scores ≤85%
```

**Aanbeveling**: Begin met **70-82%** range om LLM-calls beperkt te houden.

## Alternatief: OpenAI API

Voor wie geen lokale hardware heeft:

### 1. API key verkrijgen

Ga naar https://platform.openai.com/api-keys

### 2. Configureer

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_LLM_ENABLED=true
```

Of in code:
```python
from openai import OpenAI
llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
model_name = "gpt-4o-mini"  # Goedkoper dan gpt-4
```

**Let op**: 
- Kosten ~$0.15 per 1M tokens input, ~$0.60 per 1M tokens output
- Voor 1000 clausules ~$2-5
- Data gaat naar OpenAI servers (GDPR overwegingen!)

## Testen

Na configuratie, test met een analyse:

```bash
# Start backend
uvicorn hienfeld_api.app:app --reload --port 8000

# Check logs voor "✅ Ollama LLM enabled"
```

Bij analyse van clausules met similarity 70-85%, zie je in de logs:
```
🤖 LLM verification for uncertain match (score=0.78)
✅ LLM enhanced confidence to 0.92
```

## Performance Impact

| Setting | Analysis tijd (1000 clausules) | LLM calls |
|---------|-------------------------------|-----------|
| LLM disabled | ~10 min | 0 |
| LLM 70-82% | ~15-20 min | ~50-150 |
| LLM 60-90% | ~30+ min | ~300+ |

**Aanbeveling**: Start met **70-82%** range en verhoog alleen als nodig.

## Troubleshooting

### "Ollama not found"
```bash
# Check of Ollama draait
curl http://localhost:11434/v1/models
```

### "Model not found"
```bash
# Lijst beschikbare modellen
ollama list

# Download model
ollama pull llama3.1:8b
```

### "Out of memory"
Llama 3.1 8B vereist ~8GB RAM. Als je minder hebt:
```bash
# Kleinere variant
ollama pull llama3.1:3b
```

### LLM calls te traag
- Gebruik `llama3.1:8b` in plaats van `70b`
- Verklein drempel range (70-75% in plaats van 70-85%)
- Overweeg GPU acceleration (Ollama ondersteunt CUDA/Metal)

## Beslissing Audit: Ollama Aanbevolen

✅ **Voordelen**:
- Geen doorlopende kosten
- GDPR-compliant (lokaal)
- Goede prestaties met 8B model
- Makkelijk uitschakelbaar voor snellere analyses

⚠️ **Nadelen**:
- Vereist installatie
- RAM requirements (8-16GB)
- Langzamere analyses

**Status**: Ready to use - LLM infrastructuur volledig aanwezig in code, alleen client activeren.
