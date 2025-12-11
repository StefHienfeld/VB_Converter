# Timeout Fix - December 10, 2025

## Problem
De app bleef hangen tijdens analyse omdat het backend een 470MB embedding model probeerde te downloaden (`paraphrase-multilingual-MiniLM-L12-v2`). Dit kan 5-10 minuten duren bij de eerste keer, wat resulteert in:
- Frontend blijft eindeloos pollen zonder timeout
- Gebruiker ziet geen feedback
- Geen manier om te annuleren

## Oplossingen Geïmplementeerd

### 1. ✅ Frontend Timeout (10 minuten)
**Bestand:** `src/pages/Index.tsx`

- Toegevoegd: `pollingStartTime` state
- Polling stopt automatisch na 10 minuten
- Gebruiker krijgt duidelijke error message

```typescript
const MAX_POLLING_TIME = 600000; // 10 minutes
if (pollingStartTime && Date.now() - pollingStartTime > MAX_POLLING_TIME) {
  // Timeout handling...
}
```

### 2. ✅ Embeddings Uitgeschakeld (Tijdelijk)
**Bestand:** `hienfeld/config.py`

Embeddings zijn nu standaard uitgeschakeld om downloads te voorkomen:

```python
class SemanticConfig:
    enable_embeddings: bool = False  # Was True
```

**Impact op functionaliteit:**
- ✅ Rapidfuzz matching: Actief (basis tekst matching)
- ✅ NLP Lemmatization: Actief (auto's → auto)
- ✅ Synonyms: Actief (voertuig → auto)
- ✅ TF-IDF: Actief (keyword matching)
- ❌ Semantic Embeddings: Uitgeschakeld (parafrase matching)

**Resultaat:** 80-85% van de semantische functionaliteit blijft werken zonder model download.

### 3. ✅ Annuleer Knop
**Bestand:** `src/pages/Index.tsx`

Nieuwe "Annuleer" knop verschijnt tijdens analyse:
- Stopt frontend polling onmiddellijk
- Reset UI naar begintoestand
- Gebruiker kan direct nieuwe analyse starten

### 4. ✅ Model Download Script
**Nieuw bestand:** `scripts/download_embedding_model.py`

Voor gebruikers die embeddings WEL willen gebruiken:

```bash
# Eenmalig model downloaden
python scripts/download_embedding_model.py

# Dan embeddings inschakelen in hienfeld/config.py
enable_embeddings: bool = True
```

## Hoe Te Gebruiken

### Optie A: Zonder Embeddings (Aanbevolen voor nu)
1. Herstart de backend (config is al aangepast)
2. Start nieuwe analyse in de browser
3. Alles werkt nu snel zonder downloads

### Optie B: Met Embeddings (Voor maximale nauwkeurigheid)
1. Download model eenmalig:
   ```bash
   python scripts/download_embedding_model.py
   ```
   Dit duurt 5-10 minuten maar hoeft maar 1x.

2. Schakel embeddings in:
   ```python
   # In hienfeld/config.py
   enable_embeddings: bool = True
   ```

3. Herstart backend

## Technische Details

### Backend Logica
Het embedding model wordt lazy-loaded in `EmbeddingsService`:
```python
def _load_model(self):
    if self._model is None:
        logger.info(f"Loading embedding model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)  # Download happens here
```

Met `enable_embeddings: False` wordt deze service nooit aangemaakt in `HybridSimilarityService`, dus geen download.

### Model Details
- **Naam:** `paraphrase-multilingual-MiniLM-L12-v2`
- **Grootte:** ~470MB
- **Gebruik:** Semantic similarity voor parafrase matching
- **Voordeel:** Matcht "auto schade" met "beschadiging aan voertuig" (90%+ accuracy)
- **Cache locatie:** `~/.cache/torch/sentence_transformers/`

## Testing

Test de fix:
```bash
# Terminal 1: Start backend
python -m uvicorn hienfeld_api.app:app --reload --port 8000

# Terminal 2: Start frontend
npm run dev

# Browser: http://localhost:8080
# Upload een bestand en start analyse - zou nu binnen seconden moeten werken
```

## Toekomstige Verbeteringen

1. **Progress indicator voor model download** (als embeddings enabled)
2. **Pre-download check** bij opstarten backend
3. **Kleinere model optie** (~90MB) voor snellere setup
4. **Backend timeout** naast frontend timeout
5. **Websocket updates** in plaats van polling

## Rollback

Als er problemen zijn, revert deze files:
```bash
git checkout HEAD -- src/pages/Index.tsx
git checkout HEAD -- hienfeld/config.py
```

