<!-- REVISED PLAN - GEFASEERDE AANPAK -->
# Semantic Enhancement Plan - Focus op Quick Wins

## 🎯 Management Samenvatting

**Doel**: Verhoog automatische match-rate van 60% naar 80-85% zonder externe API's

**Strategie**: 
- **Fase 1-2**: Focus op Quick Wins met hoogste ROI (2-3 weken)
- **Fase 3+**: Evaluatie na Fase 2, mogelijk niet nodig

**Verwachte Impact**:
- Fase 1: +15-20% betere matches (embeddings activeren)
- Fase 2: +10-15% betere matches (synoniemen database)
- **Totaal**: ~60% → 80-85% automatische matches

---

## 📊 Kritische Analyse Huidige Situatie

### ✅ Wat ER AL IS (maar niet gebruikt):

| Feature | Status | Locatie | Actie Nodig |
|---------|--------|---------|-------------|
| **Sentence Embeddings** | ✅ Code ready, ⚠️ INACTIEF | `similarity_service.py:270-510` | Activeer in API |
| **Semantic Similarity Service** | ✅ Volledig werkend | `embeddings_service.py` | Koppel aan Analysis |
| **Synonym mapping support** | ✅ Interface ready | `text_normalization.py:58-94` | Vul database |
| **Multilingual model** | ✅ In config | `config.py:253` | Gebruik als default |

### ❌ Wat ONTBREEKT:

| Probleem | Impact | Effort | ROI | Prioriteit |
|----------|--------|--------|-----|-----------|
| Embeddings niet actief | -20% matches | 2u | 🟢 10x | 🔴 **P0** |
| Fout model (Engels ipv NL) | -10% accuracy | 1u | 🟢 10x | 🔴 **P0** |
| Geen synoniemen database | -15% matches | 8u | 🟢 2x | 🔴 **P0** |
| Geen lemmatisering | -10% matches | 16u | 🟡 0.6x | 🟢 **P2** |
| Geen TF-IDF | -5% matches | 12u | 🔴 0.4x | ⚪ **P3** |

**Conclusie**: Focus op Fase 1-2 = 80% resultaat met 20% effort

### ⚠️ Real-World Failure Cases:

```
TEST 1: Synoniemen
Vrije tekst: "Dekking voor personenauto"
Voorwaarden: "Verzekering van motorvoertuig"
→ NU: RapidFuzz 15% → HANDMATIG CHECKEN ❌
→ NA FASE 1: Semantic 75% → VERWIJDEREN (Midden) ✅
→ NA FASE 2: Semantic 88% (na synonym expansion) → VERWIJDEREN (Hoog) ✅

TEST 2: Parafrasen
Vrije tekst: "Bij gedwongen evacuatie"
Voorwaarden: "Wanneer u verplicht bent te evacueren"
→ NU: RapidFuzz 25% → HANDMATIG CHECKEN ❌
→ NA FASE 1: Semantic 82% → VERWIJDEREN ✅

TEST 3: Variaties
Vrije tekst: "Auto's verzekerd tegen diefstal"
Voorwaarden: "Voertuigen gedekt voor diefstal"
→ NU: RapidFuzz 35% → HANDMATIG CHECKEN ❌
→ NA FASE 1: Semantic 68% → HANDMATIG CHECKEN (maar hogere score) ~
→ NA FASE 2: Semantic 85% → VERWIJDEREN ✅
```

---

## 🚀 FASE 1: Activeer Bestaande Features (Week 1)

**Impact**: +15-20% betere matches  
**Effort**: 4-6 uur  
**Risk**: Laag (bestaande code)

### 1.1 Activeer Semantic Similarity in API ⭐

**File**: `hienfeld_api/app.py`

**Probleem**: `SemanticSimilarityService` bestaat maar wordt niet geïnitialiseerd

**Wijziging** (rond regel 200-220):

```python
def _run_analysis_job(
    job_id: str,
    ...
) -> None:
    # ... existing code ...
    
    # NIEUW: Initialiseer semantic similarity service
    semantic_service = None
    use_semantic = settings.get("ai_enabled", False) or settings.get("semantic_enabled", True)
    
    if use_semantic:
        try:
            from hienfeld.services.similarity_service import SemanticSimilarityService
            logger.info("🧠 Initializing semantic similarity (embeddings)...")
            
            semantic_service = SemanticSimilarityService(
                threshold=0.70,
                model_name="paraphrase-multilingual-MiniLM-L12-v2"  # ✅ NL model
            )
            logger.info("✅ Semantic similarity ready")
        except Exception as e:
            logger.warning(f"⚠️ Semantic similarity not available: {e}")
            semantic_service = None
    
    # ... existing services initialization ...
    
    analysis = AnalysisService(
        config, 
        admin_check_service=admin_check,
        semantic_similarity_service=semantic_service  # ✅ Koppel semantic service
    )
```

**Verwacht Resultaat**:
- Embeddings worden geladen bij start job (~2-3 seconden extra)
- Semantic matching actief in Step 2b van analysis pipeline
- +15-20% matches voor parafrasen en synoniemen

---

### 1.2 Voeg UI Toggle toe voor Semantic Matching

**File**: `src/components/settings/SettingsDrawer.tsx`

**Toevoegen**:

```typescript
<div className="flex items-center justify-between">
  <div className="space-y-0.5">
    <Label>Semantische Analyse</Label>
    <p className="text-xs text-muted-foreground">
      Gebruik AI-embeddings voor betekenis-matching (langzamer maar nauwkeuriger)
    </p>
  </div>
  <Switch
    checked={settings.semanticEnabled ?? true}
    onCheckedChange={(checked) => updateSetting('semanticEnabled', checked)}
  />
</div>
```

**Impact**: Gebruiker kan semantic matching aan/uit zetten (standaard AAN)

---

### 1.3 Update Config voor Nederlands Model

**File**: `hienfeld/config.py`

**Wijziging** (rond regel 250-260):

```python
@dataclass
class AIConfig:
    """Configuration for AI/ML features (optional)."""
    enabled: bool = True  # ✅ Was False, nu True
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"  # ✅ Al correct
    vector_store_type: str = "faiss"
    similarity_top_k: int = 3
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    
    # Nieuwe thresholds
    semantic_threshold: float = 0.70  # Minimum voor semantic match
    semantic_high_threshold: float = 0.80  # Hoog vertrouwen zonder LLM
```

**Impact**: Defaults zijn nu geoptimaliseerd voor Nederlands

---

### 1.4 Test Fase 1

**Test Script**: `tests/test_semantic_phase1.py`

```python
"""
Test semantic similarity na Fase 1 activatie.
"""
from hienfeld.services.similarity_service import SemanticSimilarityService

def test_synonym_matching():
    service = SemanticSimilarityService(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    # Test 1: Synoniemen
    score = service.similarity(
        "Dekking voor personenauto",
        "Verzekering van motorvoertuig"
    )
    print(f"Test 1 (synoniemen): {score:.2%}")
    assert score > 0.70, f"Expected >70%, got {score:.2%}"
    
    # Test 2: Parafrasen
    score = service.similarity(
        "Bij gedwongen evacuatie",
        "Wanneer u verplicht bent te evacueren"
    )
    print(f"Test 2 (parafrasen): {score:.2%}")
    assert score > 0.75, f"Expected >75%, got {score:.2%}"
    
    # Test 3: Geen match
    score = service.similarity(
        "Dekking voor auto",
        "Molestclausule"
    )
    print(f"Test 3 (geen match): {score:.2%}")
    assert score < 0.50, f"Expected <50%, got {score:.2%}"

if __name__ == "__main__":
    test_synonym_matching()
    print("✅ Alle tests geslaagd!")
```

**Run**: `python tests/test_semantic_phase1.py`

---

### 📈 Verwachte Resultaten Fase 1

| Metric | Voor | Na Fase 1 | Verbetering |
|--------|------|-----------|-------------|
| Automatische matches | 60% | 75-80% | +15-20% |
| Synoniemen herkenning | 5% | 70-75% | +65% |
| Parafrase herkenning | 10% | 80-85% | +70% |
| Analyse tijd (500 polissen) | 2 min | 3-3.5 min | +1-1.5 min |

---

## 🎨 FASE 2: Synoniemen Database (Week 2-3)

**Impact**: +10-15% betere matches  
**Effort**: 8-12 uur  
**Risk**: Laag (pure data)

### 2.1 Bouw Insurance-Specific Synoniemen Database

**File**: `hienfeld/data/insurance_synonyms.json`

**Structuur**:

```json
{
  "metadata": {
    "version": "1.0.0",
    "last_updated": "2025-01-15",
    "total_groups": 50,
    "description": "Nederlandse verzekeringstermen synoniemen database"
  },
  "synonym_groups": {
    "voertuig": {
      "canonical": "voertuig",
      "category": "object",
      "synonyms": [
        "auto", "personenauto", "wagen", "motorvoertuig", 
        "auto's", "voertuigen", "personenwagen", "pkw"
      ],
      "context": "Gebruikt voor motorrijtuigenverzekering",
      "examples": [
        "verzekering van motorvoertuig",
        "dekking voor personenauto"
      ]
    },
    "woning": {
      "canonical": "woning",
      "category": "object",
      "synonyms": [
        "huis", "pand", "woonhuis", "gebouw", "woningen",
        "verblijf", "woonpand", "onroerend goed"
      ],
      "context": "Gebruikt voor woonhuisverzekering"
    },
    "verzekerd": {
      "canonical": "verzekerd",
      "category": "status",
      "synonyms": [
        "gedekt", "meeverzekerd", "verzekerde", "gedekte",
        "beschermd", "gegarandeerd", "ingedekt"
      ]
    },
    "dekking": {
      "canonical": "dekking",
      "category": "concept",
      "synonyms": [
        "verzekering", "bescherming", "polis", "waarborg",
        "garantie", "verzekeringsdekking"
      ]
    },
    "eigen_risico": {
      "canonical": "eigen risico",
      "category": "financial",
      "synonyms": [
        "franchise", "eigenrisico", "eigen-risico",
        "zelfbehoud", "zelfrisico"
      ],
      "context": "Bedrag dat verzekerde zelf betaalt"
    },
    "schade": {
      "canonical": "schade",
      "category": "event",
      "synonyms": [
        "beschadiging", "schades", "letsel", "verlies",
        "averij", "defect", "kapot"
      ]
    },
    "verzekerde": {
      "canonical": "verzekerde",
      "category": "actor",
      "synonyms": [
        "verzekeringnemer", "polishouder", "cliënt",
        "klant", "u", "je", "betrokkene"
      ]
    },
    "verzekeraar": {
      "canonical": "verzekeraar",
      "category": "actor",
      "synonyms": [
        "maatschappij", "verzekeringmaatschappij", "ons",
        "wij", "verzekeringsmaatschappij"
      ]
    },
    "premie": {
      "canonical": "premie",
      "category": "financial",
      "synonyms": [
        "verzekeringspremie", "bijdrage", "poliskosten",
        "kosten", "tarief"
      ]
    },
    "uitkering": {
      "canonical": "uitkering",
      "category": "financial",
      "synonyms": [
        "vergoeding", "schadevergoeding", "betaling",
        "compensatie", "restitutie", "teruggave"
      ]
    },
    "uitsluiting": {
      "canonical": "uitsluiting",
      "category": "concept",
      "synonyms": [
        "uitgesloten", "niet gedekt", "niet verzekerd",
        "niet meeverzekerd", "buiten dekking"
      ]
    },
    "voorwaarden": {
      "canonical": "voorwaarden",
      "category": "document",
      "synonyms": [
        "polisvoorwaarden", "verzekeringsvoorwaarden",
        "bepalingen", "clausules", "regels"
      ]
    },
    "aansprakelijkheid": {
      "canonical": "aansprakelijkheid",
      "category": "legal",
      "synonyms": [
        "aansprakelijk", "verantwoordelijkheid",
        "wettelijke aansprakelijkheid", "WA", "AVP"
      ]
    },
    "diefstal": {
      "canonical": "diefstal",
      "category": "event",
      "synonyms": [
        "inbraak", "braak", "gestolen", "ontvreemding",
        "roof", "weggenomen"
      ]
    },
    "brand": {
      "canonical": "brand",
      "category": "event",
      "synonyms": [
        "branddekking", "brandschade", "vuur",
        "verbrand", "in brand"
      ]
    },
    "storm": {
      "canonical": "storm",
      "category": "event",
      "synonyms": [
        "stormschade", "windschade", "noodweer",
        "orkaan", "harde wind"
      ]
    },
    "water": {
      "canonical": "water",
      "category": "event",
      "synonyms": [
        "waterschade", "lekkage", "overstroming",
        "vocht", "leiding", "natte"
      ]
    },
    "herbouwwaarde": {
      "canonical": "herbouwwaarde",
      "category": "financial",
      "synonyms": [
        "nieuwwaarde", "bouwsom", "verzekerde som",
        "waarde", "verzekerd bedrag"
      ]
    },
    "dagwaarde": {
      "canonical": "dagwaarde",
      "category": "financial",
      "synonyms": [
        "actuele waarde", "marktwaarde", "huidige waarde",
        "restwaarde"
      ]
    },
    "molest": {
      "canonical": "molest",
      "category": "event",
      "synonyms": [
        "oproer", "burgeroorlog", "rellen",
        "terrorisme", "opstanden"
      ]
    }
    // ... Continue met ~30 meer groups voor verzekeringstermen
  }
}
```

**Totaal**: ~50 synonym groups met ~200+ unieke termen

---

### 2.2 Implementeer Synonym Service

**File**: `hienfeld/services/synonym_service.py` (NIEUW)

```python
"""
Synonym expansion service for insurance-specific terminology.

Uses a curated JSON database for high-precision domain matching.
NO external API calls, NO WordNet dependency.
"""
import json
from pathlib import Path
from typing import Dict, Set, Optional, List
from dataclasses import dataclass
from functools import lru_cache

from ..logging_config import get_logger

logger = get_logger('synonym_service')


@dataclass
class SynonymGroup:
    """A group of synonymous terms with metadata."""
    canonical: str
    category: str
    synonyms: List[str]
    context: Optional[str] = None
    examples: Optional[List[str]] = None


class SynonymService:
    """
    Insurance-specific synonym expansion service.
    
    Features:
    - Fast lookup via canonical term mapping
    - Category-based filtering
    - Context-aware synonym expansion
    - Caching for performance
    
    Example:
        >>> service = SynonymService()
        >>> service.are_synonyms("auto", "voertuig")
        True
        >>> service.get_canonical("personenauto")
        "voertuig"
    """
    
    def __init__(self, synonyms_file: Optional[Path] = None):
        """
        Initialize synonym service.
        
        Args:
            synonyms_file: Path to synonyms JSON file (uses default if None)
        """
        if synonyms_file is None:
            synonyms_file = Path(__file__).parent.parent / "data" / "insurance_synonyms.json"
        
        self.synonyms_file = synonyms_file
        self.synonym_groups: Dict[str, SynonymGroup] = {}
        self.term_to_canonical: Dict[str, str] = {}  # Fast lookup: term -> canonical
        self.term_to_group: Dict[str, str] = {}  # term -> group_key
        
        self._load_synonyms()
    
    def _load_synonyms(self) -> None:
        """Load synonym database from JSON file."""
        if not self.synonyms_file.exists():
            logger.warning(f"Synonyms file not found: {self.synonyms_file}")
            logger.warning("Synonym matching will be disabled")
            return
        
        try:
            with open(self.synonyms_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            groups_data = data.get('synonym_groups', {})
            
            for group_key, group_data in groups_data.items():
                group = SynonymGroup(
                    canonical=group_data['canonical'],
                    category=group_data.get('category', 'unknown'),
                    synonyms=group_data['synonyms'],
                    context=group_data.get('context'),
                    examples=group_data.get('examples')
                )
                
                self.synonym_groups[group_key] = group
                
                # Build reverse mappings for fast lookup
                # Canonical term maps to itself
                self.term_to_canonical[group.canonical.lower()] = group.canonical
                self.term_to_group[group.canonical.lower()] = group_key
                
                # All synonyms map to canonical
                for synonym in group.synonyms:
                    self.term_to_canonical[synonym.lower()] = group.canonical
                    self.term_to_group[synonym.lower()] = group_key
            
            logger.info(f"✅ Loaded {len(self.synonym_groups)} synonym groups "
                       f"({len(self.term_to_canonical)} total terms)")
            
        except Exception as e:
            logger.error(f"Failed to load synonyms: {e}")
    
    @lru_cache(maxsize=1000)
    def get_canonical(self, term: str) -> Optional[str]:
        """
        Get canonical form of a term.
        
        Args:
            term: Input term
            
        Returns:
            Canonical form or None if not found
        """
        return self.term_to_canonical.get(term.lower())
    
    @lru_cache(maxsize=5000)
    def are_synonyms(self, term1: str, term2: str) -> bool:
        """
        Check if two terms are synonyms.
        
        Args:
            term1: First term
            term2: Second term
            
        Returns:
            True if terms are synonymous
        """
        canonical1 = self.get_canonical(term1)
        canonical2 = self.get_canonical(term2)
        
        if canonical1 is None or canonical2 is None:
            return False
        
        return canonical1 == canonical2
    
    def get_synonyms(self, term: str) -> Set[str]:
        """
        Get all synonyms for a term.
        
        Args:
            term: Input term
            
        Returns:
            Set of all synonyms (including the term itself)
        """
        group_key = self.term_to_group.get(term.lower())
        if group_key is None:
            return {term}
        
        group = self.synonym_groups[group_key]
        return {group.canonical} | set(group.synonyms)
    
    def expand_text(self, text: str, max_synonyms_per_word: int = 1) -> str:
        """
        Expand text by adding synonyms.
        
        Args:
            text: Input text
            max_synonyms_per_word: Max synonyms to add per word
            
        Returns:
            Expanded text with synonyms
        """
        words = text.lower().split()
        expanded = []
        
        for word in words:
            expanded.append(word)
            
            synonyms = self.get_synonyms(word)
            if len(synonyms) > 1:
                # Add top N synonyms (excluding the word itself)
                other_synonyms = [s for s in synonyms if s.lower() != word]
                expanded.extend(other_synonyms[:max_synonyms_per_word])
        
        return " ".join(expanded)
    
    def normalize_with_synonyms(self, text: str) -> str:
        """
        Normalize text by replacing all terms with canonical forms.
        
        Args:
            text: Input text
            
        Returns:
            Text with all synonyms replaced by canonical forms
        """
        words = text.lower().split()
        normalized = []
        
        for word in words:
            canonical = self.get_canonical(word)
            normalized.append(canonical if canonical else word)
        
        return " ".join(normalized)
    
    @property
    def is_loaded(self) -> bool:
        """Check if synonym database is loaded."""
        return len(self.synonym_groups) > 0
    
    @property
    def term_count(self) -> int:
        """Get total number of terms (including synonyms)."""
        return len(self.term_to_canonical)
```

---

### 2.3 Integreer Synoniemen in Text Normalization

**File**: `hienfeld/utils/text_normalization.py`

**Wijziging** (rond regel 58-94):

```python
# Add at top of file
from typing import Optional, Dict
from functools import lru_cache

_synonym_service = None

def get_synonym_service():
    """Lazy load synonym service."""
    global _synonym_service
    if _synonym_service is None:
        try:
            from ..services.synonym_service import SynonymService
            _synonym_service = SynonymService()
        except Exception as e:
            logger.warning(f"Could not load synonym service: {e}")
            _synonym_service = None
    return _synonym_service


def simplify_text(
    text: str, 
    synonym_map: Optional[Dict[str, str]] = None,
    use_synonyms: bool = True  # ✅ NIEUW
) -> str:
    """
    Simplify text for comparison by normalizing case, whitespace, and punctuation.
    
    This is the main text normalization function used throughout the application.
    
    Args:
        text: Input text to simplify
        synonym_map: Optional dictionary mapping terms to their canonical form
        use_synonyms: If True, use SynonymService for canonical mapping
        
    Returns:
        Simplified, normalized text suitable for comparison
    """
    if not text:
        return ""
    
    # Step 1: Unicode normalization
    text = normalize_unicode(text)
    
    # Step 2: Lowercase
    text = text.lower()
    
    # Step 3: Remove punctuation (keep alphanumeric and whitespace)
    text = remove_punctuation(text)
    
    # Step 4: Normalize whitespace
    text = normalize_whitespace(text)
    
    # Step 5: Apply synonym mapping
    if use_synonyms:
        # Try SynonymService first (most comprehensive)
        syn_service = get_synonym_service()
        if syn_service and syn_service.is_loaded:
            text = syn_service.normalize_with_synonyms(text)
        # Fallback to provided synonym_map
        elif synonym_map:
            for term, canonical in synonym_map.items():
                pattern = rf'\b{re.escape(term)}\b'
                text = re.sub(pattern, canonical, text)
    
    return text
```

---

### 2.4 Test Fase 2

**Test Script**: `tests/test_semantic_phase2.py`

```python
"""
Test synonym integration na Fase 2.
"""
from hienfeld.services.synonym_service import SynonymService
from hienfeld.utils.text_normalization import simplify_text

def test_synonym_service():
    service = SynonymService()
    
    # Test 1: Direct synonym check
    assert service.are_synonyms("auto", "voertuig")
    assert service.are_synonyms("personenauto", "motorvoertuig")
    assert service.are_synonyms("verzekerd", "gedekt")
    
    # Test 2: Canonical mapping
    assert service.get_canonical("auto") == "voertuig"
    assert service.get_canonical("franchise") == "eigen risico"
    
    # Test 3: Text normalization
    text1 = simplify_text("Dekking voor personenauto")
    text2 = simplify_text("Verzekering van motorvoertuig")
    print(f"Normalized text1: {text1}")
    print(f"Normalized text2: {text2}")
    
    # After normalization, should be more similar
    from rapidfuzz import fuzz
    original_score = fuzz.ratio(
        "dekking voor personenauto",
        "verzekering van motorvoertuig"
    ) / 100.0
    normalized_score = fuzz.ratio(text1, text2) / 100.0
    
    print(f"Original: {original_score:.2%}")
    print(f"After synonyms: {normalized_score:.2%}")
    assert normalized_score > original_score + 0.30, "Expected +30% improvement"

if __name__ == "__main__":
    test_synonym_service()
    print("✅ Alle tests geslaagd!")
```

---

### 📈 Verwachte Resultaten Fase 2

| Metric | Na Fase 1 | Na Fase 2 | Verbetering |
|--------|-----------|-----------|-------------|
| Automatische matches | 75-80% | 85-90% | +5-10% |
| Synoniemen herkenning | 70-75% | 95%+ | +20-25% |
| Domain precision | 75% | 90%+ | +15% |
| False positives | 15% | 5% | -10% |

---

## 🔮 FASE 3+: Evaluatie en Optioneel (Later)

**Evalueer ALLEEN na succesvolle Fase 1-2**

### Optie 3A: SpaCy Lemmatisering (Midden prioriteit)

**Impact**: +5-10% matches voor verbuigingen  
**Effort**: 16 uur  
**Dependency**: ~50MB SpaCy model

**Pro**:
- "verzekerd", "verzekering", "verzekeren" → zelfde lemma
- Goede Nederlandse ondersteuning

**Contra**:
- Performance overhead (~5-10ms per tekst)
- Embeddings vangen veel al op
- Extra dependency

**Beslissing criteria**:
- Als na Fase 2 nog < 85% matches → overweeg
- Als performance OK is → overweeg
- Anders → skip

---

### Optie 3B: TF-IDF met Gensim (Lage prioriteit)

**Impact**: +3-5% matches, sneller dan embeddings  
**Effort**: 12 uur  
**ROI**: 0.4x (LAAG)

**Pro**:
- Sneller dan embeddings voor keyword matching
- Geen GPU nodig

**Contra**:
- Embeddings zijn krachtiger
- Needs training corpus (waar vandaan?)
- Onnodige complexiteit

**Aanbeveling**: **SKIP** - embeddings + synonyms zijn genoeg

---

### Optie 3C: Hybrid Similarity (Alleen als nodig)

**Impact**: +2-5% door weighted combination  
**Effort**: 8 uur

**Alleen implementeren als**:
- Na Fase 2 zijn er edge cases die niet goed werken
- Je wilt fine-grained control over weights

**Anders**: Huidige approach (RapidFuzz → Semantic → Synonyms) is voldoende

---

## 📋 Implementatie Checklist

### Week 1: Fase 1

- [ ] Update `hienfeld_api/app.py` - initialiseer `SemanticSimilarityService`
- [ ] Update `hienfeld/config.py` - zet AI enabled = True
- [ ] Voeg UI toggle toe in settings drawer
- [ ] Test met test_semantic_phase1.py
- [ ] Run volledige analyse op testset
- [ ] Vergelijk metrics voor/na
- [ ] **Go/No-Go beslissing voor Fase 2**

### Week 2-3: Fase 2

- [ ] Bouw `insurance_synonyms.json` database (~50 groups)
- [ ] Implementeer `synonym_service.py`
- [ ] Integreer in `text_normalization.py`
- [ ] Test met test_semantic_phase2.py
- [ ] Run volledige analyse op testset
- [ ] Vergelijk metrics voor/na
- [ ] **Evalueer: zijn we op target (85% matches)?**

### Week 4+: Evaluatie

- [ ] Als < 85% matches: evalueer Fase 3 opties
- [ ] Als ≥ 85% matches: **KLAAR! 🎉**
- [ ] Document lessons learned
- [ ] Plan maintenance (synonym database updates)

---

## 🎯 Success Criteria

**Minimum Viable Success** (na Fase 1-2):
- ✅ Automatische matches: 60% → 85%+
- ✅ Synoniemen herkenning: 5% → 95%+
- ✅ Parafrase herkenning: 10% → 80%+
- ✅ Performance: < 5 min voor 500 polissen
- ✅ Geen externe API's of kosten

**Excellent Success** (stretch goal):
- 🌟 Automatische matches: 90%+
- 🌟 User feedback: "Veel minder handmatig werk"
- 🌟 False positives: < 5%

---

## 💰 Kosten & Dependencies

### Fase 1:
- **Dependencies**: GEEN nieuwe (reuse bestaande)
- **Model download**: ~470MB (paraphrase-multilingual-MiniLM-L12-v2)
- **Kosten**: €0,00
- **Privacy**: 100% lokaal

### Fase 2:
- **Dependencies**: GEEN nieuwe (pure JSON data)
- **Data**: ~50KB JSON file
- **Effort**: 8-12u voor database curation
- **Kosten**: €0,00
- **Maintenance**: Quarterly updates (~1u/kwartaal)

**Totaal**: €0,00 + ~20 uur development

---

## 🚫 Wat We NIET Doen (Rationaal)

| Feature | Waarom NIET | Impact Gemist |
|---------|-------------|---------------|
| **Open Dutch WordNet** | Niet insurance-specific | -5% precision |
| **Gensim TF-IDF** | Embeddings krachtiger | -3% matches |
| **SpaCy (nu)** | Evalueer later | -8% matches |
| **LLM API's** | Geen budget, privacy | -10% edge cases |
| **Custom BERT training** | Overkill, te complex | -5% matches |

**Philosophy**: 80/20 rule - 80% resultaat met 20% effort

---

## 📞 Support & Rollback

**Als Fase 1 problemen geeft**:
```python
# In settings
semantic_enabled: False  # Rollback to RapidFuzz only
```

**Als Fase 2 problemen geeft**:
```python
# In simplify_text()
use_synonyms: False  # Disable synonym normalization
```

**Monitoring**:
- Track match rates per release
- Monitor false positive rate
- Collect user feedback

---

**Last Updated**: 2025-01-15  
**Version**: 2.0 (Gefaseerde Aanpak)  
**Status**: Ready for Implementation

