# RAG Pipeline Optimalisatie - Implementatie Specificaties

> Status: ✅ COMPLETED
> Aangemaakt: 2026-01-13
> Afgerond: 2026-01-14
> Doel: Maximale kwaliteit van AI-analyse output

---

## Overzicht

| # | Verbetering | Status | Impact | Effort |
|---|-------------|--------|--------|--------|
| 1 | JSON Parsing (Pydantic) | ✅ DONE | Hoog | Laag |
| 2 | Chain-of-Thought Enhancement | ✅ DONE | Hoog | Laag |
| 3 | Contextbewuste Preprocessing | ✅ DONE | Hoog | Midden |
| 4 | Reflection Loop | ✅ DONE | Zeer Hoog | Midden |
| 5 | Cross-Encoder Re-Ranking | ✅ DONE | Hoog | Hoog |

---

## 1. JSON Parsing met Pydantic Validation

### Doel
Elimineer parsing failures door strikte JSON validatie en automatische confidence clamping.

### Bestanden te wijzigen
- `hienfeld/prompts/sanering_prompt.py`
- `hienfeld/prompts/compliance_prompt.py`
- `hienfeld/prompts/semantic_match_prompt.py`
- `hienfeld/prompts/admin_prompt.py`
- `hienfeld/services/ai/llm_analysis_service.py`

### Specificaties

**1.1 Nieuwe dependencies (requirements.txt)**
```
pydantic>=2.0
```

**1.2 Pydantic Models (in elk prompt bestand)**

```python
# sanering_prompt.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class SaneringResultModel(BaseModel):
    """Validated sanering result."""
    is_redundant: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str = Field(max_length=500)
    matching_article: Optional[str] = None

    @field_validator('confidence', mode='before')
    @classmethod
    def clamp_confidence(cls, v):
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        return 0.5
```

```python
# compliance_prompt.py
class ComplianceResultModel(BaseModel):
    """Validated compliance result."""
    category: str = Field(pattern=r'^(CONFLICT|EXTENSION|LIMITATION|NEUTRAL|UNKNOWN)$')
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    risk_score: int = Field(ge=1, le=10, default=5)
    advice: str = Field(max_length=500)
    legal_subject: Optional[str] = None
    cited_article: Optional[str] = None

    @field_validator('risk_score', mode='before')
    @classmethod
    def clamp_risk(cls, v):
        if isinstance(v, (int, float)):
            return max(1, min(10, int(v)))
        return 5
```

```python
# semantic_match_prompt.py
class SemanticMatchResultModel(BaseModel):
    """Validated semantic match result."""
    is_match: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    match_type: str = Field(pattern=r'^(EXACT|PARAPHRASE|PARTIAL|NO_MATCH)$', default='NO_MATCH')
    explanation: str = Field(max_length=300)
    differences: Optional[str] = None
```

**1.3 JSON Mode in LLM calls**

```python
# llm_analysis_service.py - _call_llm_chat methode
def _call_llm_chat(self, messages: List[dict], force_json: bool = True) -> str:
    if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
        kwargs = {
            'model': self.model_name,
            'messages': messages,
            'temperature': self.temperature
        }
        if force_json:
            kwargs['response_format'] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
```

**1.4 Robuuste from_json methode (template)**

```python
@classmethod
def from_json(cls, json_str: str, raw_response: str = None) -> 'SaneringResult':
    """Parse JSON with Pydantic validation and fallback chain."""

    # Step 1: Try direct JSON parse
    try:
        # Strip markdown code blocks if present
        clean_json = json_str.strip()
        if clean_json.startswith('```'):
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_json, re.DOTALL)
            if match:
                clean_json = match.group(1)

        data = json.loads(clean_json)
        validated = SaneringResultModel(**data)
        return cls(
            is_redundant=validated.is_redundant,
            confidence=validated.confidence,
            reason=validated.reason,
            matching_article=validated.matching_article,
            raw_response=raw_response
        )
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"JSON parsing failed: {e}, attempting fallback")

    # Step 2: Fallback - keyword extraction (last resort)
    return cls._fallback_parse(json_str, raw_response)
```

### Acceptatiecriteria
- [ ] Alle 4 prompt bestanden gebruiken Pydantic models
- [ ] Confidence wordt altijd geclamped tussen 0.0-1.0
- [ ] Markdown codeblocks worden correct gestript
- [ ] Fallback parsing logt warnings voor monitoring
- [ ] Unit tests voor edge cases (nested JSON, malformed input)

---

## 2. Chain-of-Thought Enhancement

### Doel
Dwing expliciete reasoning af voordat de LLM een conclusie geeft.

### Bestanden te wijzigen
- `hienfeld/prompts/sanering_prompt.py`
- `hienfeld/prompts/compliance_prompt.py`

### Specificaties

**2.1 Nieuw JSON Schema met thinking block**

```python
# Sanering prompt output schema
OUTPUT_SCHEMA = """
{
    "thinking": {
        "observation": "Wat zie ik in deze clausule? (max 2 zinnen)",
        "comparison": "Hoe verhoudt dit zich tot de voorwaarden? (max 2 zinnen)",
        "reasoning": "Waarom is dit wel/niet redundant? (max 2 zinnen)"
    },
    "result": {
        "is_redundant": true/false,
        "confidence": 0.0-1.0,
        "reason": "Korte conclusie (max 1 zin)",
        "matching_article": "Art. X.Y of null"
    }
}
"""
```

```python
# Compliance prompt output schema
OUTPUT_SCHEMA = """
{
    "thinking": {
        "clause_analysis": "Wat bepaalt deze clausule? (max 2 zinnen)",
        "conditions_check": "Wat zeggen de voorwaarden hierover? (max 2 zinnen)",
        "conflict_assessment": "Is er een conflict of aanvulling? (max 2 zinnen)"
    },
    "result": {
        "category": "CONFLICT|EXTENSION|LIMITATION|NEUTRAL",
        "confidence": 0.0-1.0,
        "risk_score": 1-10,
        "advice": "Aanbeveling (max 2 zinnen)",
        "legal_subject": "Onderwerp of null",
        "cited_article": "Art. X.Y of null"
    }
}
"""
```

**2.2 Prompt Enhancement**

```python
# Toevoegen aan system prompt
COT_INSTRUCTION = """
KRITIEK: Je MOET eerst nadenken voordat je concludeert.

STAP 1: Vul het "thinking" blok volledig in met je analyse.
STAP 2: Baseer je "result" DIRECT op wat je in "thinking" hebt geschreven.
STAP 3: Controleer: is je result consistent met je thinking?

Als je thinking en result elkaar tegenspreken, is je antwoord FOUT.
Geef NOOIT een result zonder eerst thinking in te vullen.
"""
```

**2.3 Pydantic Model met thinking**

```python
class ThinkingBlock(BaseModel):
    """Reasoning steps before conclusion."""
    observation: str = Field(max_length=200)
    comparison: str = Field(max_length=200)
    reasoning: str = Field(max_length=200)

class SaneringResultWithCoT(BaseModel):
    """Sanering result with enforced chain-of-thought."""
    thinking: ThinkingBlock
    result: SaneringResultModel

    @model_validator(mode='after')
    def validate_consistency(self):
        """Check that thinking and result are consistent."""
        # Als thinking zegt "komt overeen" maar result zegt "niet redundant" -> warning
        thinking_text = f"{self.thinking.observation} {self.thinking.reasoning}".lower()

        if self.result.is_redundant and 'niet' in thinking_text and 'redundant' in thinking_text:
            logger.warning("Possible inconsistency: thinking suggests not redundant but result says redundant")

        return self
```

**2.4 Logging van thinking voor debugging**

```python
# In llm_analysis_service.py
def analyze_sanering(self, input_text: str, policy_context: str) -> SaneringResult:
    # ... existing code ...

    result = SaneringResultWithCoT.model_validate_json(response)

    # Log thinking for debugging/monitoring
    logger.debug(f"CoT Thinking: {result.thinking.model_dump_json()}")

    return result.result  # Return only the result part
```

### Acceptatiecriteria
- [ ] Sanering prompt bevat thinking block in schema
- [ ] Compliance prompt bevat thinking block in schema
- [ ] Pydantic model valideert thinking aanwezigheid
- [ ] Thinking wordt gelogd op DEBUG level
- [ ] Inconsistentie detectie geeft warnings

---

## 3. Contextbewuste Preprocessing

### Doel
Behoud juridische nuances in embeddings en LLM context.

### Bestanden te wijzigen
- `hienfeld/utils/text_normalization.py`
- `hienfeld/domain/clause.py`
- `hienfeld/services/clustering_service.py`

### Specificaties

**3.1 Nieuwe normalisatie levels**

```python
# text_normalization.py

class NormalizationLevel(Enum):
    """Levels of text normalization."""
    RAW = "raw"                    # Geen normalisatie
    LIGHT = "light"                # Alleen whitespace/encoding
    EMBEDDING = "embedding"        # Behoud bedragen/datums, normaliseer rest
    CLUSTERING = "clustering"      # Agressief: [BEDRAG], [DATUM], etc.

def normalize_text(text: str, level: NormalizationLevel) -> str:
    """Normalize text based on intended use case."""

    if level == NormalizationLevel.RAW:
        return text

    # LIGHT: Alleen encoding en whitespace
    if level == NormalizationLevel.LIGHT:
        text = fix_encoding(text)
        text = normalize_whitespace(text)
        return text

    # EMBEDDING: Behoud juridisch relevante info
    if level == NormalizationLevel.EMBEDDING:
        text = fix_encoding(text)
        text = normalize_whitespace(text)
        text = text.lower()
        # BEHOUD: bedragen, datums, artikel referenties
        # VERWIJDER: alleen overtollige punctuatie
        text = re.sub(r'[^\w\s€$.,:\-/()]', '', text)
        return text

    # CLUSTERING: Agressieve normalisatie (bestaande logica)
    if level == NormalizationLevel.CLUSTERING:
        return normalize_for_clustering(text)

    return text
```

**3.2 Legal Reference Preservation**

```python
# Patronen die NIET genormaliseerd mogen worden in EMBEDDING level
LEGAL_PATTERNS = {
    'article_ref': r'(?:Art\.?\s*\d+[:.]\d+|artikel\s+\d+[:.]\d+)',
    'law_ref': r'(?:BW|Wft|WvK|Sr|Sv)\s*\d*',
    'euro_amount': r'(?:EUR|€)\s*[\d.,]+',
    'percentage': r'\d+[.,]?\d*\s*%',
}

def preserve_legal_references(text: str) -> tuple[str, dict]:
    """Extract and preserve legal references before normalization."""
    preserved = {}

    for name, pattern in LEGAL_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        for i, match in enumerate(matches):
            placeholder = f"__LEGAL_{name.upper()}_{i}__"
            preserved[placeholder] = match
            text = text.replace(match, placeholder, 1)

    return text, preserved

def restore_legal_references(text: str, preserved: dict) -> str:
    """Restore legal references after normalization."""
    for placeholder, original in preserved.items():
        text = text.replace(placeholder, original)
    return text
```

**3.3 Clause model uitbreiding**

```python
# domain/clause.py
@dataclass
class Clause:
    """Represents a policy clause with multiple text representations."""

    id: str
    raw_text: str                  # Origineel (voor LLM)
    simplified_text: str           # LIGHT normalized (voor display)
    embedding_text: str            # EMBEDDING normalized (voor vectors)
    clusterable_text: str          # CLUSTERING normalized (voor grouping)

    # ... existing fields ...

    @classmethod
    def from_raw(cls, id: str, raw_text: str, **kwargs) -> 'Clause':
        """Create clause with all normalization levels."""
        return cls(
            id=id,
            raw_text=raw_text,
            simplified_text=normalize_text(raw_text, NormalizationLevel.LIGHT),
            embedding_text=normalize_text(raw_text, NormalizationLevel.EMBEDDING),
            clusterable_text=normalize_text(raw_text, NormalizationLevel.CLUSTERING),
            **kwargs
        )
```

### Acceptatiecriteria
- [ ] NormalizationLevel enum geïmplementeerd
- [ ] Legal reference preservation werkt correct
- [ ] Clause model heeft 4 text representaties
- [ ] Embeddings gebruiken embedding_text (niet clusterable_text)
- [ ] Unit tests voor elk normalisatie level

---

## 4. Reflection Loop (Self-Verification)

### Doel
Laat de AI zijn eigen analyse controleren voordat output naar gebruiker gaat.

### Bestanden te wijzigen
- `hienfeld/services/ai/llm_analysis_service.py`
- Nieuw: `hienfeld/prompts/reflection_prompt.py`

### Specificaties

**4.1 Nieuwe Reflection Prompt**

```python
# hienfeld/prompts/reflection_prompt.py

class ReflectionPrompt:
    """Prompt for self-verification of analysis results."""

    SYSTEM_PROMPT = """
Je bent een kritische reviewer van verzekeringsanalyses.
Je taak is om een eerdere analyse te controleren op fouten.

Je krijgt:
1. De originele clausule tekst
2. De relevante voorwaarden (context)
3. De eerste analyse met conclusie

Je moet:
1. Controleren of de conclusie logisch volgt uit de context
2. Zoeken naar gemiste nuances of fouten
3. Een oordeel geven: AKKOORD of HERZIEN

Als je twijfelt, kies dan HERZIEN.
"""

    USER_TEMPLATE = """
CLAUSULE:
{clause_text}

VOORWAARDEN CONTEXT:
{policy_context}

EERSTE ANALYSE:
- Conclusie: {conclusion}
- Reden: {reason}
- Confidence: {confidence}
- Referentie: {reference}

Controleer deze analyse. Is de conclusie correct gegeven de context?

Output JSON:
{{
    "verification": {{
        "checks_performed": ["lijst van controles"],
        "issues_found": ["lijst van problemen of []"],
        "missed_nuances": ["gemiste punten of []"]
    }},
    "verdict": {{
        "status": "AKKOORD|HERZIEN",
        "confidence": 0.0-1.0,
        "revised_conclusion": "alleen als HERZIEN, anders null",
        "revised_reason": "alleen als HERZIEN, anders null"
    }}
}}
"""
```

**4.2 Pydantic Model voor Reflection**

```python
class VerificationChecks(BaseModel):
    checks_performed: List[str]
    issues_found: List[str] = []
    missed_nuances: List[str] = []

class ReflectionVerdict(BaseModel):
    status: Literal["AKKOORD", "HERZIEN"]
    confidence: float = Field(ge=0.0, le=1.0)
    revised_conclusion: Optional[str] = None
    revised_reason: Optional[str] = None

class ReflectionResult(BaseModel):
    verification: VerificationChecks
    verdict: ReflectionVerdict
```

**4.3 Integration in LLMAnalysisService**

```python
# llm_analysis_service.py

def analyze_with_reflection(
    self,
    cluster: Cluster,
    policy_sections: List[PolicyDocumentSection],
    reflection_threshold: float = 0.7
) -> AnalysisAdvice:
    """Analyze cluster with optional reflection pass."""

    # Pass 1: Initial analysis
    initial_result = self.analyze_cluster_with_context(cluster, policy_sections)

    # Skip reflection if confidence is high enough
    if initial_result.confidence >= reflection_threshold:
        logger.debug(f"Skipping reflection: confidence {initial_result.confidence} >= {reflection_threshold}")
        return initial_result

    # Pass 2: Reflection
    logger.info(f"Running reflection pass for cluster {cluster.id}")
    reflection = self._run_reflection(cluster, policy_sections, initial_result)

    # Handle reflection result
    if reflection.verdict.status == "AKKOORD":
        return initial_result

    # Revision needed
    if reflection.verdict.status == "HERZIEN":
        logger.warning(f"Reflection revised analysis for {cluster.id}")
        return self._create_revised_advice(cluster, initial_result, reflection)

    return initial_result

def _run_reflection(
    self,
    cluster: Cluster,
    policy_sections: List[PolicyDocumentSection],
    initial_result: AnalysisAdvice
) -> ReflectionResult:
    """Run reflection prompt on initial analysis."""

    context = self._format_sections_as_context(policy_sections[:10])

    messages = ReflectionPrompt.build_messages(
        clause_text=cluster.original_text,
        policy_context=context,
        conclusion=initial_result.advice_code,
        reason=initial_result.reason,
        confidence=initial_result.confidence,
        reference=initial_result.reference_article
    )

    response = self._call_llm_chat(messages, force_json=True)
    return ReflectionResult.model_validate_json(response)
```

**4.4 Conflict Detection**

```python
def _handle_reflection_conflict(
    self,
    initial: AnalysisAdvice,
    reflection: ReflectionResult,
    cluster: Cluster
) -> AnalysisAdvice:
    """Handle conflict between initial analysis and reflection."""

    # Als reflection HERZIEN zegt met hoge confidence -> gebruik revisie
    if reflection.verdict.confidence >= 0.8:
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=reflection.verdict.revised_conclusion or initial.advice_code,
            reason=f"[GEREVISEERD] {reflection.verdict.revised_reason}",
            confidence=reflection.verdict.confidence,
            reference_article=initial.reference_article,
            category="REFLECTION_REVISED",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )

    # Als beide lage confidence -> HANDMATIG CHECKEN
    return AnalysisAdvice(
        cluster_id=cluster.id,
        advice_code="HANDMATIG CHECKEN",
        reason=f"Conflicterende analyses. Initieel: {initial.reason}. Reflectie: {reflection.verdict.revised_reason}",
        confidence=0.3,
        reference_article=initial.reference_article,
        category="REFLECTION_CONFLICT",
        cluster_name=cluster.name,
        frequency=cluster.frequency
    )
```

### Acceptatiecriteria
- [ ] ReflectionPrompt class geïmplementeerd
- [ ] Pydantic models voor reflection result
- [ ] analyze_with_reflection methode werkt
- [ ] Conflicts resulteren in HANDMATIG CHECKEN
- [ ] Reflection wordt overgeslagen bij hoge confidence
- [ ] Logging van alle reflection passes

---

## 5. Cross-Encoder Re-Ranking

### Doel
Verbeter retrieval precisie door top resultaten te her-rangschikken.

### Bestanden te wijzigen
- Nieuw: `hienfeld/services/ai/reranking_service.py`
- `hienfeld/services/ai/rag_service.py`
- `requirements.txt`

### Specificaties

**5.1 Nieuwe dependency**

```
# requirements.txt
sentence-transformers>=2.2.0  # Already present
# Cross-encoder model will be downloaded on first use
```

**5.2 ReRankingService class**

```python
# hienfeld/services/ai/reranking_service.py

from typing import List, Optional, Tuple
from sentence_transformers import CrossEncoder
from ...logging_config import get_logger

logger = get_logger('reranking_service')

class ReRankingService:
    """
    Re-ranking service using cross-encoder models.

    Cross-encoders jointly process query+document pairs for more
    accurate relevance scoring than bi-encoders (separate embeddings).
    """

    # Model options:
    # - "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1" - Multilingual, good for Dutch
    # - "cross-encoder/ms-marco-MiniLM-L-6-v2" - Fast, English-focused

    DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    def __init__(self, model_name: str = DEFAULT_MODEL):
        """Initialize re-ranking service."""
        self.model_name = model_name
        self._model: Optional[CrossEncoder] = None

    def _load_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                logger.info(f"Loading cross-encoder model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("Cross-encoder model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load cross-encoder: {e}")
                raise

    def rerank(
        self,
        query: str,
        documents: List[dict],
        top_k: int = 5,
        text_key: str = 'raw_text'
    ) -> List[dict]:
        """
        Re-rank documents by relevance to query.

        Args:
            query: The query/clause text
            documents: List of document dicts with 'metadata' containing text
            top_k: Number of top results to return
            text_key: Key in metadata containing the text to compare

        Returns:
            Re-ranked list of documents (highest relevance first)
        """
        if not documents:
            return []

        if len(documents) <= 1:
            return documents

        self._load_model()

        # Prepare query-document pairs
        pairs = []
        for doc in documents:
            text = doc.get('metadata', {}).get(text_key, '')
            if not text:
                text = str(doc)
            pairs.append([query, text])

        # Get cross-encoder scores
        scores = self._model.predict(pairs)

        # Combine scores with documents
        scored_docs = list(zip(documents, scores))

        # Sort by score (descending)
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # Log re-ranking impact
        original_order = [d.get('id', i) for i, d in enumerate(documents)]
        new_order = [d.get('id', i) for d, s in scored_docs]
        if original_order != new_order:
            logger.debug(f"Re-ranking changed order: {original_order} -> {new_order}")

        # Return top-k re-ranked documents
        return [doc for doc, score in scored_docs[:top_k]]

    def rerank_with_scores(
        self,
        query: str,
        documents: List[dict],
        top_k: int = 5
    ) -> List[Tuple[dict, float]]:
        """Re-rank and return documents with their cross-encoder scores."""
        # ... similar to rerank but returns (doc, score) tuples
        pass

    @property
    def is_available(self) -> bool:
        """Check if cross-encoder can be loaded."""
        try:
            from sentence_transformers import CrossEncoder
            return True
        except ImportError:
            return False
```

**5.3 LLM-based Re-Ranking Fallback**

```python
class LLMReRanker:
    """
    Fallback re-ranker using LLM when cross-encoder unavailable.

    Slower but doesn't require additional model download.
    """

    def __init__(self, llm_client, model_name: str = "gpt-4"):
        self.client = llm_client
        self.model_name = model_name

    def rerank(
        self,
        query: str,
        documents: List[dict],
        top_k: int = 5
    ) -> List[dict]:
        """Re-rank using LLM scoring."""

        if len(documents) <= 1:
            return documents

        # Build ranking prompt
        docs_text = "\n".join([
            f"{i+1}. {doc.get('metadata', {}).get('raw_text', '')[:200]}..."
            for i, doc in enumerate(documents[:10])  # Limit to 10
        ])

        prompt = f"""Rangschik de volgende teksten op relevantie voor de query.
Query: "{query}"

Teksten:
{docs_text}

Geef de nummers in volgorde van MEEST naar MINST relevant.
Output alleen een JSON array met nummers, bijvoorbeeld: [3, 1, 5, 2, 4]"""

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )

        # Parse ranking
        ranking = json.loads(response.choices[0].message.content)

        # Reorder documents
        reordered = []
        for idx in ranking:
            if 1 <= idx <= len(documents):
                reordered.append(documents[idx - 1])

        return reordered[:top_k]
```

**5.4 Integration in RAGService**

```python
# rag_service.py

class RAGService:
    def __init__(
        self,
        embeddings_service: EmbeddingsService,
        vector_store: VectorStore,
        reranking_service: Optional[ReRankingService] = None
    ):
        self.embeddings_service = embeddings_service
        self.vector_store = vector_store
        self.reranking_service = reranking_service
        self._indexed = False

    def get_context_for_analysis(
        self,
        clause_text: str,
        top_k: int = 20,
        min_score: float = 0.5,
        rerank: bool = True,
        rerank_top_k: int = 10
    ) -> str:
        """Get formatted context with optional re-ranking."""

        # Initial retrieval (more candidates for re-ranking)
        candidates_k = top_k * 2 if rerank and self.reranking_service else top_k
        results = self.retrieve_relevant_sections(clause_text, candidates_k)

        # Filter by score
        relevant = [r for r in results if r['score'] >= min_score]

        # Re-rank if service available
        if rerank and self.reranking_service and len(relevant) > 1:
            relevant = self.reranking_service.rerank(
                query=clause_text,
                documents=relevant,
                top_k=rerank_top_k
            )

        # Take top_k after re-ranking
        relevant = relevant[:top_k]

        if not relevant:
            return "Geen relevante voorwaarden gevonden."

        # Format as XML
        # ... existing formatting code ...
```

### Acceptatiecriteria
- [ ] ReRankingService class geïmplementeerd
- [ ] Cross-encoder model lazy loading werkt
- [ ] LLM fallback re-ranker beschikbaar
- [ ] RAGService integreert re-ranking optioneel
- [ ] Re-ranking kan worden uitgeschakeld via parameter
- [ ] Logging van re-ranking impact
- [ ] Performance benchmark: <100ms voor 20 documents

---

## Testing Checklist

### Unit Tests
- [ ] `test_pydantic_validation.py` - JSON parsing edge cases
- [ ] `test_cot_prompts.py` - Chain-of-thought schema validation
- [ ] `test_normalization_levels.py` - All 4 normalization levels
- [ ] `test_reflection.py` - Reflection prompt and conflict handling
- [ ] `test_reranking.py` - Cross-encoder and LLM reranking

### Integration Tests
- [ ] End-to-end analysis met alle verbeteringen
- [ ] Performance regression test
- [ ] Fallback scenarios (LLM unavailable, model not loaded)

### Manual Testing
- [ ] Test met 10 bekende clausules en verwachte uitkomsten
- [ ] Vergelijk output voor/na verbeteringen
- [ ] Monitor logging output voor debugging info

---

## Notes

- Pydantic v2 syntax gebruiken (field_validator, model_validator)
- Cross-encoder model (~500MB) wordt lazy geladen
- Reflection loop verdubbelt LLM calls - monitor kosten
- Legal reference preservation moet backwards compatible zijn
