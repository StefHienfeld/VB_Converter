# hienfeld/prompts/compliance_prompt.py
"""
Prompt B: Compliance (Conflict Check)

Analyzes whether a free text clause conflicts with, extends, or limits
the standard policy conditions.

Enhanced with:
- Pydantic validation for robust JSON parsing
- Chain-of-Thought (CoT) enforced reasoning
- Automatic risk score and confidence clamping
"""
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum
import json
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from ..logging_config import get_logger

logger = get_logger('compliance_prompt')


# =============================================================================
# Enums
# =============================================================================

class ComplianceCategory(Enum):
    """Categories of compliance analysis results."""
    CONFLICT = "CONFLICT"       # Clause contradicts policy conditions
    EXTENSION = "EXTENSION"     # Clause extends coverage beyond conditions
    LIMITATION = "LIMITATION"   # Clause limits coverage compared to conditions
    NEUTRAL = "NEUTRAL"         # Clause is neutral/clarifying only
    UNKNOWN = "UNKNOWN"         # Could not determine


# =============================================================================
# Pydantic Models for Validation
# =============================================================================

class ComplianceThinkingBlock(BaseModel):
    """
    Chain-of-Thought reasoning block for compliance analysis.
    Forces the LLM to analyze step-by-step before concluding.
    """
    clause_analysis: str = Field(
        default="",
        max_length=300,
        description="Wat bepaalt deze clausule precies?"
    )
    conditions_check: str = Field(
        default="",
        max_length=300,
        description="Wat zeggen de voorwaarden over dit onderwerp?"
    )
    conflict_assessment: str = Field(
        default="",
        max_length=300,
        description="Is er een conflict, uitbreiding of beperking?"
    )


class ComplianceResultModel(BaseModel):
    """
    Validated compliance result block from LLM response.
    """
    category: str = Field(default="UNKNOWN")
    risk_score: int = Field(default=5, ge=1, le=10)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    advice: str = Field(default="Geen advies beschikbaar", max_length=500)
    cited_article: Optional[str] = Field(default=None)
    legal_subject: Optional[str] = Field(default=None)

    @field_validator('category', mode='before')
    @classmethod
    def normalize_category(cls, v):
        """Normalize category string to uppercase."""
        if v is None:
            return "UNKNOWN"
        v_upper = str(v).upper().strip()
        valid = ["CONFLICT", "EXTENSION", "LIMITATION", "NEUTRAL", "UNKNOWN"]
        return v_upper if v_upper in valid else "UNKNOWN"

    @field_validator('risk_score', mode='before')
    @classmethod
    def clamp_risk_score(cls, v):
        """Ensure risk score is always between 1 and 10."""
        if v is None:
            return 5
        try:
            v = int(v)
            return max(1, min(10, v))
        except (ValueError, TypeError):
            return 5

    @field_validator('confidence', mode='before')
    @classmethod
    def clamp_confidence(cls, v):
        """Ensure confidence is always between 0.0 and 1.0."""
        if v is None:
            return 0.5
        try:
            v = float(v)
            return max(0.0, min(1.0, v))
        except (ValueError, TypeError):
            return 0.5


class ComplianceResponseModel(BaseModel):
    """
    Full LLM response with Chain-of-Thought.
    """
    thinking: Optional[ComplianceThinkingBlock] = None
    result: ComplianceResultModel

    @model_validator(mode='after')
    def check_risk_consistency(self):
        """Warn if thinking suggests conflict but category is neutral."""
        if self.thinking:
            thinking_text = f"{self.thinking.conflict_assessment}".lower()

            # Check for conflict signals in thinking
            conflict_signals = ['conflict', 'tegenstrijdig', 'niet toegestaan', 'verboden']
            has_conflict = any(signal in thinking_text for signal in conflict_signals)

            if has_conflict and self.result.category == "NEUTRAL":
                logger.warning(
                    f"CoT inconsistency: thinking mentions conflict but category is NEUTRAL. "
                    f"Risk score: {self.result.risk_score}"
                )
        return self


# =============================================================================
# Result Dataclass (Backwards Compatible)
# =============================================================================

@dataclass
class ComplianceResult:
    """
    Result of the compliance/conflict analysis.

    Attributes:
        category: The type of compliance issue found
        risk_score: Risk level from 1 (low) to 10 (high)
        advice: Specific advice for handling this clause
        cited_article: The article referenced in analysis
        legal_subject: The legal subject identified (e.g., "eigen risico")
        confidence: How confident the LLM is (0.0 - 1.0)
        thinking: Optional Chain-of-Thought reasoning (for debugging)
        raw_response: The raw LLM response for debugging
    """
    category: ComplianceCategory
    risk_score: int
    advice: str
    cited_article: Optional[str] = None
    legal_subject: Optional[str] = None
    confidence: float = 0.0
    thinking: Optional[dict] = None
    raw_response: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'ComplianceResult':
        """
        Parse a ComplianceResult from JSON string with robust handling.

        Uses Pydantic validation for:
        - Automatic category normalization
        - Risk score clamping (1-10)
        - Confidence clamping (0.0-1.0)

        Handles:
        - Markdown code blocks (```json ... ```)
        - Nested JSON objects
        - Malformed responses with fallback

        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging

        Returns:
            ComplianceResult instance
        """
        if not json_str:
            logger.warning("Empty response received")
            return cls.fallback("Lege response ontvangen")

        try:
            # Step 1: Clean markdown code blocks
            clean_json = cls._extract_json(json_str)

            # Step 2: Parse JSON
            data = json.loads(clean_json)

            # Step 3: Validate with Pydantic
            # Handle both flat and nested (with thinking) responses
            if 'result' in data:
                # New format with thinking block
                validated = ComplianceResponseModel.model_validate(data)
                thinking_dict = validated.thinking.model_dump() if validated.thinking else None
                result = validated.result
            else:
                # Legacy flat format
                result = ComplianceResultModel.model_validate(data)
                thinking_dict = None

            # Convert category string to enum
            try:
                category_enum = ComplianceCategory(result.category)
            except ValueError:
                category_enum = ComplianceCategory.UNKNOWN

            logger.debug(f"Successfully parsed compliance result: category={category_enum.value}")

            return cls(
                category=category_enum,
                risk_score=result.risk_score,
                advice=result.advice,
                cited_article=result.cited_article,
                legal_subject=result.legal_subject,
                confidence=result.confidence,
                thinking=thinking_dict,
                raw_response=raw_response
            )

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            return cls._fallback_parse(json_str, raw_response)

        except Exception as e:
            logger.warning(f"Pydantic validation error: {e}")
            return cls._fallback_parse(json_str, raw_response)

    @classmethod
    def _extract_json(cls, text: str) -> str:
        """
        Extract JSON from text, handling markdown code blocks.

        Args:
            text: Raw text that may contain JSON

        Returns:
            Cleaned JSON string
        """
        text = text.strip()

        # Handle markdown code blocks: ```json ... ``` or ``` ... ```
        code_block_match = re.search(
            r'```(?:json)?\s*(\{[\s\S]*?\})\s*```',
            text,
            re.DOTALL
        )
        if code_block_match:
            return code_block_match.group(1).strip()

        # Handle nested JSON (one level deep)
        nested_match = re.search(
            r'\{(?:[^{}]|\{[^{}]*\})*\}',
            text,
            re.DOTALL
        )
        if nested_match:
            return nested_match.group()

        # Fallback: try to find simple JSON object
        simple_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if simple_match:
            return simple_match.group()

        # Last resort: return as-is
        return text

    @classmethod
    def _fallback_parse(cls, json_str: str, raw_response: str = None) -> 'ComplianceResult':
        """
        Fallback parsing using keyword detection.

        Used when JSON parsing fails completely.
        Returns low confidence result.
        """
        logger.warning("Using fallback keyword parsing for compliance")

        text_lower = json_str.lower()

        # Try to detect category from keywords
        category = ComplianceCategory.UNKNOWN

        if any(word in text_lower for word in ['conflict', 'tegenstrijdig', 'verboden']):
            category = ComplianceCategory.CONFLICT
        elif any(word in text_lower for word in ['uitbreid', 'extension', 'extra dekking']):
            category = ComplianceCategory.EXTENSION
        elif any(word in text_lower for word in ['beperk', 'limitation', 'uitgesloten']):
            category = ComplianceCategory.LIMITATION
        elif any(word in text_lower for word in ['neutraal', 'verduidelijk']):
            category = ComplianceCategory.NEUTRAL

        # High risk if conflict detected
        risk_score = 8 if category == ComplianceCategory.CONFLICT else 5

        return cls(
            category=category,
            risk_score=risk_score,
            advice=f"Fallback parsing (JSON failed): {json_str[:200]}...",
            cited_article=None,
            legal_subject=None,
            confidence=0.3,  # Low confidence for fallback
            thinking=None,
            raw_response=raw_response
        )

    @classmethod
    def fallback(cls, error_message: str) -> 'ComplianceResult':
        """Create a fallback result when analysis fails completely."""
        return cls(
            category=ComplianceCategory.UNKNOWN,
            risk_score=5,
            advice=f"Analyse mislukt: {error_message}",
            cited_article=None,
            legal_subject=None,
            confidence=0.0,
            thinking=None,
            raw_response=None
        )

    @property
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk result."""
        return self.risk_score >= 7 or self.category == ComplianceCategory.CONFLICT

    @property
    def requires_action(self) -> bool:
        """Check if this result requires user action."""
        return self.category in [ComplianceCategory.CONFLICT, ComplianceCategory.EXTENSION]


# =============================================================================
# Prompt Builder
# =============================================================================

class CompliancePrompt:
    """
    Prompt builder for compliance/conflict analysis.

    This prompt asks the LLM to analyze whether a free text clause
    conflicts with, extends, or limits the policy conditions.

    Uses Chain-of-Thought (CoT) to enforce explicit reasoning
    before the LLM reaches a conclusion.
    """

    SYSTEM_PROMPT = """Je bent een Senior Underwriter en Compliance Officer bij een verzekeringsmaatschappij.
Je analyseert vrije tekst clausules op mogelijke conflicten met de standaard polisvoorwaarden.

BELANGRIJK - DENK EERST NA:
Je MOET eerst je analyse uitschrijven in het "thinking" blok voordat je een conclusie geeft.
Dit voorkomt overhaaste of onjuiste beoordelingen.

CATEGORIEËN:
- CONFLICT: Clausule spreekt de voorwaarden tegen (NIET toegestaan, hoog risico)
- EXTENSION: Clausule breidt de dekking uit (vereist acceptatie)
- LIMITATION: Clausule beperkt de dekking (meestal toegestaan)
- NEUTRAL: Clausule is verduidelijkend zonder inhoudelijke wijziging

RISICOSCORES:
- 1-3: Laag risico, geen actie nodig
- 4-6: Matig risico, review aanbevolen
- 7-10: Hoog risico, actie vereist

Antwoord ALTIJD in JSON formaat met het exacte schema hieronder."""

    USER_PROMPT_TEMPLATE = """Context (Polisvoorwaarden):
{policy_chunks}

---

Input (Clausule om te analyseren):
"{input_text}"

---

OPDRACHT: Analyseer deze clausule op compliance met de voorwaarden.

STAP 1: Analyseer wat de clausule precies bepaalt (vul "thinking" in)
STAP 2: Zoek het relevante artikel in de voorwaarden
STAP 3: Vergelijk en bepaal categorie + risico (vul "result" in)

Output JSON (EXACT dit format):
{{
    "thinking": {{
        "clause_analysis": "Wat bepaalt deze clausule precies? (max 2 zinnen)",
        "conditions_check": "Wat zeggen de voorwaarden hierover? (max 2 zinnen)",
        "conflict_assessment": "Is er een conflict, uitbreiding of beperking? (max 2 zinnen)"
    }},
    "result": {{
        "category": "CONFLICT|EXTENSION|LIMITATION|NEUTRAL",
        "risk_score": 1-10,
        "confidence": 0.0-1.0,
        "advice": "Kort advies voor de underwriter (max 2 zinnen)",
        "legal_subject": "Het juridische onderwerp (bijv. eigen risico, dekkingsgebied)",
        "cited_article": "Artikel nummer uit voorwaarden of null"
    }}
}}"""

    @classmethod
    def build(cls, input_text: str, policy_chunks: str) -> tuple:
        """
        Build the prompt for compliance analysis.

        Args:
            input_text: The free text clause to analyze
            policy_chunks: Relevant policy condition text (from RAG)

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Truncate inputs to prevent token overflow
        input_text = input_text[:2000] if input_text else ""
        policy_chunks = policy_chunks[:6000] if policy_chunks else ""

        if not input_text:
            logger.warning("Empty input text provided to CompliancePrompt")

        if not policy_chunks:
            logger.warning("Empty policy context provided to CompliancePrompt")

        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            input_text=input_text,
            policy_chunks=policy_chunks
        )

        return cls.SYSTEM_PROMPT, user_prompt

    @classmethod
    def build_messages(cls, input_text: str, policy_chunks: str) -> list:
        """
        Build messages list for chat completion API.

        Args:
            input_text: The free text clause to analyze
            policy_chunks: Relevant policy condition text

        Returns:
            List of message dicts for chat completion
        """
        system_prompt, user_prompt = cls.build(input_text, policy_chunks)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
