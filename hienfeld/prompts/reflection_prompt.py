# hienfeld/prompts/reflection_prompt.py
"""
Prompt for Reflection/Self-Verification Loop.

Implements a dual-pass verification architecture where the LLM
reviews its own initial analysis and flags inconsistencies.

Research shows 15-30% improvement in accuracy through self-reflection.
"""
from dataclasses import dataclass
from typing import Optional, Literal
import json
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from ..logging_config import get_logger

logger = get_logger('reflection_prompt')


# =============================================================================
# Pydantic Models for Validation
# =============================================================================

class ReflectionThinkingBlock(BaseModel):
    """
    Chain-of-Thought reasoning for reflection.
    Forces the LLM to systematically review the initial analysis.
    """
    initial_conclusion_review: str = Field(
        default="",
        max_length=300,
        description="Wat was de oorspronkelijke conclusie en klopt dit?"
    )
    evidence_check: str = Field(
        default="",
        max_length=300,
        description="Zijn er belangrijke punten gemist of verkeerd geinterpreteerd?"
    )
    confidence_assessment: str = Field(
        default="",
        max_length=300,
        description="Hoe zeker ben ik van deze conclusie?"
    )


class ReflectionResultModel(BaseModel):
    """
    Validated reflection result block from LLM response.
    """
    agrees_with_initial: bool = Field(default=True)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    issues_found: Optional[str] = Field(default=None, max_length=500)
    revised_conclusion: Optional[str] = Field(default=None, max_length=300)
    recommendation: Literal["ACCEPT", "REVISE", "MANUAL_CHECK"] = Field(default="ACCEPT")

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

    @field_validator('recommendation', mode='before')
    @classmethod
    def normalize_recommendation(cls, v):
        """Normalize recommendation string."""
        if v is None:
            return "ACCEPT"
        v_upper = str(v).upper().strip()
        valid = ["ACCEPT", "REVISE", "MANUAL_CHECK"]
        return v_upper if v_upper in valid else "ACCEPT"


class ReflectionResponseModel(BaseModel):
    """
    Full LLM response with Chain-of-Thought.
    """
    thinking: Optional[ReflectionThinkingBlock] = None
    result: ReflectionResultModel

    @model_validator(mode='after')
    def check_consistency(self):
        """Warn if thinking disagrees but result accepts."""
        if self.thinking:
            thinking_text = f"{self.thinking.evidence_check} {self.thinking.confidence_assessment}".lower()

            # Check for disagreement signals in thinking
            disagreement_signals = ['gemist', 'fout', 'incorrect', 'verkeerd', 'niet correct', 'onjuist']
            has_disagreement = any(signal in thinking_text for signal in disagreement_signals)

            if has_disagreement and self.result.agrees_with_initial and self.result.recommendation == "ACCEPT":
                logger.warning(
                    f"Reflection CoT inconsistency: thinking mentions issues but result accepts. "
                    f"Confidence: {self.result.confidence}"
                )
        return self


# =============================================================================
# Result Dataclass (Backwards Compatible)
# =============================================================================

@dataclass
class ReflectionResult:
    """
    Result of the reflection/self-verification analysis.

    Attributes:
        agrees_with_initial: True if reflection agrees with initial analysis
        confidence: How confident the reflection is (0.0 - 1.0)
        issues_found: Description of any issues found
        revised_conclusion: Alternative conclusion if disagreement
        recommendation: ACCEPT, REVISE, or MANUAL_CHECK
        thinking: Optional Chain-of-Thought reasoning (for debugging)
        raw_response: Original LLM response for debugging
    """
    agrees_with_initial: bool
    confidence: float
    issues_found: Optional[str] = None
    revised_conclusion: Optional[str] = None
    recommendation: str = "ACCEPT"
    thinking: Optional[dict] = None
    raw_response: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'ReflectionResult':
        """
        Parse a ReflectionResult from JSON string with robust handling.

        Uses Pydantic validation for:
        - Automatic confidence clamping (0.0-1.0)
        - Recommendation normalization
        - Missing field defaults

        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging

        Returns:
            ReflectionResult instance
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
            if 'result' in data:
                validated = ReflectionResponseModel.model_validate(data)
                thinking_dict = validated.thinking.model_dump() if validated.thinking else None
                result = validated.result
            else:
                result = ReflectionResultModel.model_validate(data)
                thinking_dict = None

            logger.debug(f"Successfully parsed reflection: agrees={result.agrees_with_initial}")

            return cls(
                agrees_with_initial=result.agrees_with_initial,
                confidence=result.confidence,
                issues_found=result.issues_found,
                revised_conclusion=result.revised_conclusion,
                recommendation=result.recommendation,
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

        # Handle markdown code blocks
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

        return text

    @classmethod
    def _fallback_parse(cls, json_str: str, raw_response: str = None) -> 'ReflectionResult':
        """
        Fallback parsing using keyword detection.

        Used when JSON parsing fails completely.
        Always recommends manual check for safety.
        """
        logger.warning("Using fallback keyword parsing for reflection")

        text_lower = json_str.lower()

        # Check for disagreement signals
        disagree_signals = ['niet correct', 'fout', 'onjuist', 'gemist', 'verkeerd']
        agree_signals = ['correct', 'akkoord', 'bevestig', 'juist']

        has_disagree = any(signal in text_lower for signal in disagree_signals)
        has_agree = any(signal in text_lower for signal in agree_signals)

        # Disagree signals override agree signals
        agrees = has_agree and not has_disagree

        return cls(
            agrees_with_initial=agrees,
            confidence=0.3,  # Low confidence for fallback
            issues_found="Fallback parsing (JSON failed)" if not agrees else None,
            revised_conclusion=None,
            recommendation="MANUAL_CHECK",  # Always recommend manual check on fallback
            thinking=None,
            raw_response=raw_response
        )

    @classmethod
    def fallback(cls, error_message: str) -> 'ReflectionResult':
        """Create a fallback result when reflection fails completely."""
        return cls(
            agrees_with_initial=False,
            confidence=0.0,
            issues_found=f"Reflectie mislukt: {error_message}",
            revised_conclusion=None,
            recommendation="MANUAL_CHECK",
            thinking=None,
            raw_response=None
        )

    @property
    def needs_manual_review(self) -> bool:
        """Check if this result needs manual review."""
        return (
            self.recommendation == "MANUAL_CHECK" or
            not self.agrees_with_initial or
            self.confidence < 0.7
        )

    @property
    def is_confident(self) -> bool:
        """Check if the reflection is confident."""
        return self.confidence >= 0.7 and self.agrees_with_initial


# =============================================================================
# Prompt Builder
# =============================================================================

class ReflectionPrompt:
    """
    Prompt builder for reflection/self-verification.

    This prompt asks the LLM to critically review an initial analysis
    and flag any inconsistencies, missed points, or errors.

    Uses Chain-of-Thought (CoT) to enforce systematic review.
    """

    SYSTEM_PROMPT = """Je bent een kritische reviewer die een eerdere analyse controleert op fouten.

Je taak is om de initiële analyse KRITISCH te beoordelen en eventuele fouten of gemiste punten te identificeren.

BELANGRIJK - WEES KRITISCH:
- Neem NIET automatisch aan dat de eerste analyse correct is
- Zoek actief naar fouten, gemiste punten, of onjuiste conclusies
- Controleer of de redenering logisch en volledig is
- Wees extra kritisch bij hoge risico's (conflicten, uitbreidingen)

REGELS:
1. Lees de initiële analyse zorgvuldig
2. Vergelijk met de originele clausule en voorwaarden
3. Identificeer eventuele inconsistenties of fouten
4. Geef een eerlijk oordeel over de betrouwbaarheid

Antwoord ALTIJD in JSON formaat met het exacte schema hieronder."""

    USER_PROMPT_TEMPLATE = """ORIGINELE CLAUSULE:
---
{clause_text}
---

RELEVANTE VOORWAARDEN:
---
{context}
---

INITIËLE ANALYSE:
---
Conclusie: {initial_conclusion}
Reden: {initial_reason}
Vertrouwen: {initial_confidence}
Artikel: {initial_article}
---

OPDRACHT: Controleer deze analyse kritisch.

STAP 1: Was de conclusie correct? (vul "thinking" in)
STAP 2: Zijn er punten gemist of verkeerd geïnterpreteerd?
STAP 3: Geef je uiteindelijke oordeel (vul "result" in)

Aanbevelingen:
- ACCEPT: Initiële analyse is correct en compleet
- REVISE: Er zijn fouten gevonden, herziene conclusie nodig
- MANUAL_CHECK: Te complex of onzeker, handmatige review nodig

Output JSON (EXACT dit format):
{{
    "thinking": {{
        "initial_conclusion_review": "Is de conclusie '{initial_conclusion}' correct? (max 2 zinnen)",
        "evidence_check": "Zijn er punten gemist of verkeerd geïnterpreteerd? (max 2 zinnen)",
        "confidence_assessment": "Hoe zeker ben ik van mijn oordeel? (max 2 zinnen)"
    }},
    "result": {{
        "agrees_with_initial": true of false,
        "confidence": 0.0-1.0,
        "issues_found": "Beschrijving van gevonden problemen (of null)",
        "revised_conclusion": "Herziene conclusie als nodig (of null)",
        "recommendation": "ACCEPT|REVISE|MANUAL_CHECK"
    }}
}}"""

    @classmethod
    def build(
        cls,
        clause_text: str,
        context: str,
        initial_conclusion: str,
        initial_reason: str,
        initial_confidence: str = "0.5",
        initial_article: str = "-"
    ) -> tuple:
        """
        Build the prompt for reflection.

        Args:
            clause_text: Original clause being analyzed
            context: Relevant policy conditions
            initial_conclusion: The initial analysis conclusion
            initial_reason: Reasoning from initial analysis
            initial_confidence: Confidence from initial analysis
            initial_article: Article reference from initial analysis

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Truncate inputs to prevent token overflow
        clause_text = clause_text[:2000] if clause_text else ""
        context = context[:4000] if context else ""
        initial_conclusion = initial_conclusion[:200] if initial_conclusion else ""
        initial_reason = initial_reason[:500] if initial_reason else ""
        initial_article = initial_article or "-"

        if not clause_text:
            logger.warning("Empty clause text provided to ReflectionPrompt")

        if not context:
            logger.warning("Empty context provided to ReflectionPrompt")

        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            clause_text=clause_text,
            context=context,
            initial_conclusion=initial_conclusion,
            initial_reason=initial_reason,
            initial_confidence=initial_confidence,
            initial_article=initial_article
        )

        return cls.SYSTEM_PROMPT, user_prompt

    @classmethod
    def build_messages(
        cls,
        clause_text: str,
        context: str,
        initial_conclusion: str,
        initial_reason: str,
        initial_confidence: str = "0.5",
        initial_article: str = "-"
    ) -> list:
        """
        Build messages list for chat completion API.

        Args:
            clause_text: Original clause being analyzed
            context: Relevant policy conditions
            initial_conclusion: The initial analysis conclusion
            initial_reason: Reasoning from initial analysis
            initial_confidence: Confidence from initial analysis
            initial_article: Article reference from initial analysis

        Returns:
            List of message dicts for chat completion
        """
        system_prompt, user_prompt = cls.build(
            clause_text,
            context,
            initial_conclusion,
            initial_reason,
            initial_confidence,
            initial_article
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
