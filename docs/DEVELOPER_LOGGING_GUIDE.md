# Developer Logging Guide 🔧

Comprehensive guide voor debugging en monitoring van de Hienfeld VB Converter.

## Quick Start: Developer Mode Activeren

Developer mode activeert:
- ✅ **DEBUG level logging** - Zie alle details
- ✅ **Colored console output** - Betere leesbaarheid
- ✅ **Performance timing** - Meet exact waar tijd naartoe gaat
- ✅ **Detailed phase tracking** - Zie exact welke stap actief is

### Activeren via environment variable:

```bash
# macOS/Linux
export HIENFELD_DEV_MODE=1
uvicorn hienfeld_api.app:app --reload --port 8000

# Windows PowerShell
$env:HIENFELD_DEV_MODE="1"
uvicorn hienfeld_api.app:app --reload --port 8000

# Windows CMD
set HIENFELD_DEV_MODE=1
uvicorn hienfeld_api.app:app --reload --port 8000
```

### Of: Eenmalig activeren

```bash
HIENFELD_DEV_MODE=1 uvicorn hienfeld_api.app:app --reload --port 8000
```

## Wat zie je in Developer Mode?

### 1. Enhanced Format
```
[14:23:45] INFO     | hienfeld.api                | 🚀 NEW ANALYSIS JOB: abc123
[14:23:45] DEBUG    | hienfeld.clustering_service | Processing clause 1/1660
[14:23:47] INFO     | hienfeld.timing             | ✅ DONE: Cluster 1660 clauses (2.34s)
```

Versus normale mode:
```
[2025-01-10 14:23:45] INFO - hienfeld.api - 🚀 NEW ANALYSIS JOB: abc123
```

### 2. Color Coding
- **DEBUG**: Cyan (technische details)
- **INFO**: Green (normale flow)
- **WARNING**: Yellow (let op, niet fataal)
- **ERROR**: Red (fouten)
- **🚀 Phases**: Bold Blue
- **✅ Success**: Bold Green
- **❌ Failures**: Bold Red
- **⏱️ Timing**: Magenta

### 3. Phase Tracking

Je ziet exact welke fase actief is en hoe lang elke fase duurt:

```
================================================================================
  🚀 NEW ANALYSIS JOB: abc12345
================================================================================
[14:23:45] INFO     | hienfeld.api                | 📊 Analysis mode: BALANCED
[14:23:45] INFO     | hienfeld.api                |    • Time multiplier: 1.0x
[14:23:45] INFO     | hienfeld.api                |    • Cluster threshold: 90%
[14:23:45] INFO     | hienfeld.timing             | 📍 CHECKPOINT: Analysis Job abc12345 → Configuration loaded (+0.12s, total: 0.12s)

[14:23:45] INFO     | hienfeld.api                | 📄 Loading policy file: data.xlsx (234567 bytes)
[14:23:45] INFO     | hienfeld.timing             | ⏱️  START: Load policy file
[14:23:46] INFO     | hienfeld.timing             | ✅ DONE: Load policy file (0.89s)
[14:23:46] INFO     | hienfeld.api                | ✅ Policy loaded: 1660 rows, text column: 'Vrije Tekst'
[14:23:46] INFO     | hienfeld.timing             | 📍 CHECKPOINT: Analysis Job abc12345 → Policy file loaded (1660 rows) (+1.01s, total: 1.13s)

================================================================================
  🧠 SEMANTIC SERVICES INITIALIZATION
================================================================================
[14:23:46] INFO     | hienfeld.api                | 🔤 Training TF-IDF model...
[14:23:46] INFO     | hienfeld.timing             | ⏱️  START: TF-IDF training
[14:23:47] INFO     | hienfeld.timing             | ✅ DONE: TF-IDF training (0.54s)
[14:23:47] INFO     | hienfeld.api                | ✅ TF-IDF trained on 234 documents

================================================================================
  🔗 CLUSTERING (1660 clauses)
================================================================================
[14:23:50] INFO     | hienfeld.timing             | ⏱️  START: Cluster 1660 clauses
[14:23:52] INFO     | hienfeld.timing             | ✅ DONE: Cluster 1660 clauses (2.34s)
[14:23:52] INFO     | hienfeld.api                | ✅ Clustering complete: 456 clusters from 1660 clauses
[14:23:52] INFO     | hienfeld.api                |    • Avg cluster size: 3.6
[14:23:52] INFO     | hienfeld.timing             | 📍 CHECKPOINT: Analysis Job abc12345 → Clustering (456 clusters) (+2.89s, total: 4.02s)

[14:24:15] INFO     | hienfeld.timing             | 🏁 FINISH: Analysis Job abc12345 (total: 29.45s)
[14:24:15] INFO     | hienfeld.timing             | 📊 Phase breakdown:
[14:24:15] INFO     | hienfeld.timing             |    • Configuration loaded: 0.12s (0.4%)
[14:24:15] INFO     | hienfeld.timing             |    • Policy file loaded (1660 rows): 1.01s (3.4%)
[14:24:15] INFO     | hienfeld.timing             |    • TF-IDF training: 0.54s (1.8%)
[14:24:15] INFO     | hienfeld.timing             |    • Clustering (456 clusters): 2.89s (9.8%)
[14:24:15] INFO     | hienfeld.timing             |    • Analysis: 24.89s (84.5%)

================================================================================
🎉 Analysis job abc12345 COMPLETED
   • Total clusters: 456
   • Input rows: 1660
   • Total time: 29.5s
================================================================================
```

### 4. Performance Bottleneck Detection

Met de phase breakdown zie je DIRECT waar de tijd naartoe gaat:
- 84.5% in Analysis → Dit is normaal voor grote datasets
- 10% in Clustering → Goed!
- 5% in File loading → Acceptabel

Als je bijv. ziet dat TF-IDF training 50% van de tijd kost, weet je waar te optimaliseren.

## Logging Levels: Wat log je wanneer?

### DEBUG - Voor development details
```python
logger.debug(f"Processing clause {i}/{total}: {clause.simplified_text[:50]}")
logger.debug(f"Similarity score: {score:.3f} (threshold: {threshold})")
```

**Gebruik voor:**
- Loop iteraties
- Individual item processing
- Similarity scores
- Cache hits/misses

### INFO - Voor normale flow
```python
logger.info(f"✅ Policy loaded: {len(df)} rows")
logger.info(f"🔗 Starting clustering with threshold {threshold}")
```

**Gebruik voor:**
- Phase transitions
- Successful completions
- Summary statistics
- User-relevant events

### WARNING - Voor niet-fatale issues
```python
logger.warning(f"Failed to parse {filename}: {error}")
logger.warning("⚠️ No semantic services available - using RapidFuzz only")
```

**Gebruik voor:**
- Recoverable errors
- Missing optional features
- Degraded functionality
- User should be aware but system continues

### ERROR - Voor fatale fouten
```python
logger.error(f"❌ FAILED: {operation_name} - {error}")
logger.exception("Analysis job failed")  # Includes full traceback
```

**Gebruik voor:**
- Job failures
- Unrecoverable errors
- System cannot continue

## Timing Utilities

### Timer - Voor individual operations

```python
from hienfeld.utils.timing import Timer

# Als context manager
with Timer("Load CSV file"):
    df = pd.read_csv(file_path)

# Output:
# ⏱️  START: Load CSV file
# ✅ DONE: Load CSV file (0.45s)
```

### PhaseTimer - Voor multi-step pipelines

```python
from hienfeld.utils.timing import PhaseTimer

timer = PhaseTimer("Data Processing")

# Checkpoint 1
load_data()
timer.checkpoint("Data loaded")

# Checkpoint 2
process_data()
timer.checkpoint("Data processed")

# Checkpoint 3
save_results()
timer.checkpoint("Results saved")

# Finish and get stats
stats = timer.finish()

# Output:
# 🚀 BEGIN: Data Processing
# 📍 CHECKPOINT: Data Processing → Data loaded (+1.23s, total: 1.23s)
# 📍 CHECKPOINT: Data Processing → Data processed (+5.67s, total: 6.90s)
# 📍 CHECKPOINT: Data Processing → Results saved (+0.89s, total: 7.79s)
# 🏁 FINISH: Data Processing (total: 7.79s)
# 📊 Phase breakdown:
#    • Data loaded: 1.23s (15.8%)
#    • Data processed: 5.67s (72.8%)
#    • Results saved: 0.89s (11.4%)
```

### @timed decorator

```python
from hienfeld.utils.timing import timed

@timed("My expensive function")
def process_large_dataset(data):
    # ...expensive operation...
    return result

# Or with custom log level
@timed("Critical operation", log_level="INFO")
def critical_func():
    pass
```

## Log Sections - Voor betere leesbaarheid

```python
from hienfeld.logging_config import log_section

log_section(logger, "SEMANTIC SERVICES INITIALIZATION")
# Do stuff...
log_section(logger, "CLUSTERING PHASE")
# Do more stuff...

# Output:
# ================================================================================
#   SEMANTIC SERVICES INITIALIZATION
# ================================================================================
# [logs here]
# ================================================================================
#   CLUSTERING PHASE
# ================================================================================
# [logs here]
```

## Debugging Scenarios

### Scenario 1: "Waarom duurt mijn analyse zo lang?"

**Stap 1:** Enable dev mode en run analyse

**Stap 2:** Check de phase breakdown aan het einde:
```
📊 Phase breakdown:
   • TF-IDF training: 45.23s (78.2%)  ← ⚠️ PROBLEEM!
   • Clustering: 8.12s (14.0%)
   • Analysis: 4.52s (7.8%)
```

**Diagnose:** TF-IDF training neemt 78% van de tijd!

**Oplossingen:**
- Zijn de policy sections té groot? Check aantal sections
- Is TF-IDF nodig? Overweeg FAST mode
- Kan corpus kleiner? Filter niet-relevante secties

### Scenario 2: "Welke clusters worden gemaakt?"

**Stap 1:** Check de clustering logs:
```
[14:23:52] DEBUG    | hienfeld.clustering_service | Clause 1/1660: "Deze polis dekt..."
[14:23:52] DEBUG    | hienfeld.clustering_service | Created new cluster CL001
[14:23:52] DEBUG    | hienfeld.clustering_service | Clause 2/1660: "Deze polis dekt..."
[14:23:52] DEBUG    | hienfeld.clustering_service | Added to cluster CL001 (similarity: 0.96)
```

**Stap 2:** Check clustering summary:
```
✅ Clustering complete: 456 clusters from 1660 clauses
   • Avg cluster size: 3.6
```

### Scenario 3: "Waarom matched deze tekst niet?"

**Stap 1:** Check hybrid similarity logs:
```
[14:24:05] DEBUG    | hienfeld.hybrid_similarity  | Comparing "sanctieclausule" vs "sanctiewetgeving"
[14:24:05] DEBUG    | hienfeld.hybrid_similarity  | RapidFuzz: 0.72, Lemma: 0.68, Embeddings: 0.85
[14:24:05] DEBUG    | hienfeld.hybrid_similarity  | Final score: 0.76 (threshold: 0.75) ✅ MATCH
```

**Stap 2:** Check analysis decisions:
```
[14:24:10] INFO     | hienfeld.analysis_service   | Step 2 - Conditions match for CL042
[14:24:10] INFO     | hienfeld.analysis_service   | Matched section: Art 2.8 (score: 0.94)
```

### Scenario 4: "Welke semantic services zijn actief?"

Check de initialization logs:
```
================================================================================
  🧠 SEMANTIC SERVICES INITIALIZATION
================================================================================
✅ TF-IDF trained on 234 documents
✅ Embeddings loaded: all-MiniLM-L6-v2 (90MB)
✅ RAG index opgebouwd voor semantische context
✅ Hybrid similarity actief met 4 semantische services: nlp, tfidf, synonyms, embeddings
📊 Mode weights: RapidFuzz=30%, Lemma=25%, TF-IDF=15%, Synonyms=15%, Embeddings=15%
🔗 Clustering upgraded to hybrid similarity mode: BALANCED
```

## Log naar File (Optional)

Voor persistente logs die je later kunt analyseren:

```python
# In hienfeld_api/app.py
setup_logging(log_file="hienfeld_analysis.log")
```

Dan krijg je zowel console output (colored) als file output (plain text met timestamps).

## Tips & Best Practices

### DO ✅

1. **Gebruik descriptive emoji's:**
   - 📄 File operations
   - 🔗 Clustering
   - 🧠 Semantic/AI
   - ✅ Success
   - ❌ Failure
   - ⚠️ Warning

2. **Log actionable info:**
   ```python
   logger.info(f"✅ Policy loaded: {len(df)} rows, text column: '{text_col}'")
   # Goed: Zegt hoeveel rows én welke column
   ```

3. **Use timing for slow operations:**
   ```python
   with Timer("Parse 5 PDF files"):
       for pdf in pdfs:
           parse_pdf(pdf)
   ```

4. **Log stats na grote operaties:**
   ```python
   logger.info(f"✅ Clustering complete: {len(clusters)} clusters")
   logger.info(f"   • Avg cluster size: {avg_size:.1f}")
   logger.info(f"   • Largest cluster: {largest_size} items")
   ```

### DON'T ❌

1. **Geen logs in tight loops zonder throttling:**
   ```python
   # ❌ BAD: 1660 logs!
   for clause in clauses:
       logger.info(f"Processing {clause.id}")

   # ✅ GOOD: Periodic updates
   for i, clause in enumerate(clauses):
       if i % 100 == 0:
           logger.debug(f"Processed {i}/{len(clauses)} clauses")
   ```

2. **Geen sensitive data loggen:**
   ```python
   # ❌ BAD: Might contain PII
   logger.info(f"Processing: {clause.raw_text}")

   # ✅ GOOD: Just metadata
   logger.debug(f"Processing clause {clause.id} ({len(clause.raw_text)} chars)")
   ```

3. **Geen cryptische logs:**
   ```python
   # ❌ BAD
   logger.info("Done")

   # ✅ GOOD
   logger.info(f"✅ Analysis complete: {stats['unique_clusters']} clusters generated")
   ```

## Snel Debuggen Checklist

Wanneer je een probleem hebt:

- [ ] **Enable dev mode**: `export HIENFELD_DEV_MODE=1`
- [ ] **Check backend terminal**: Zie je errors/warnings?
- [ ] **Check phase breakdown**: Waar gaat de tijd naartoe?
- [ ] **Check service initialization**: Welke services zijn actief?
- [ ] **Check specific operation**: Zoek naar de operation in de logs
- [ ] **Check similarity scores**: Bij matching problemen (DEBUG level)
- [ ] **Check progress callbacks**: Worden ze aangeroepen?

## Performance Profiling Workflow

1. **Baseline meting:** Run met dev mode en noteer total time
2. **Identify bottleneck:** Check phase breakdown - waar gaat >50% tijd naartoe?
3. **Deep dive:** Enable DEBUG level voor die specifieke service
4. **Optimize:** Maak changes
5. **Measure:** Run opnieuw en vergelijk phase breakdown
6. **Iterate:** Repeat tot performance acceptabel is

## Veelvoorkomende Log Patronen

### Pattern 1: Operation met retry logic
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        result = risky_operation()
        logger.info(f"✅ Operation succeeded (attempt {attempt+1}/{max_retries})")
        break
    except Exception as e:
        logger.warning(f"⚠️ Attempt {attempt+1}/{max_retries} failed: {e}")
        if attempt == max_retries - 1:
            logger.error(f"❌ Operation failed after {max_retries} attempts")
            raise
```

### Pattern 2: Batch processing met progress
```python
total = len(items)
batch_size = 100

with Timer(f"Process {total} items in batches"):
    for i in range(0, total, batch_size):
        batch = items[i:i+batch_size]
        process_batch(batch)

        pct = int(((i + batch_size) / total) * 100)
        logger.info(f"📊 Progress: {pct}% ({i+batch_size}/{total} items)")
```

### Pattern 3: Conditional feature logging
```python
if semantic_service:
    logger.info("✅ Semantic matching enabled")
    logger.info(f"   • Model: {semantic_service.model_name}")
    logger.info(f"   • Cache size: {semantic_service.cache_size}")
else:
    logger.info("ℹ️  Semantic matching disabled - using fuzzy only")
```

## Conclusie

Met dit logging systeem heb je:
- ✅ **Real-time insight** in wat er gebeurt
- ✅ **Performance profiling** out-of-the-box
- ✅ **Easy debugging** met colored output en sections
- ✅ **Production-ready** logging met clean output
- ✅ **Zero overhead** when dev mode is off

**Happy debugging! 🐛🔨**
