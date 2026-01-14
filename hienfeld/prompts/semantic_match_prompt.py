# hienfeld/prompts/semantic_match_prompt.py
"""
Prompt for Semantic Match Verification.

Verifies if two texts have the same meaning, even when written differently.
Used after embedding-based similarity finds a potential match.

Enhanced with:
- Pydantic validation for robust JSON parsing
- Chain-of-Thought (CoT) enforced reasoning
- Automatic confidence clamping
"""
from dataclasses import dataclass
from typing import Optional
import json
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from ..logging_config import get_logger

logger = get_logger('semantic_match_prompt')


# =============================================================================
# Pydantic Models for Validation
# =============================================================================

class SemanticThinkingBlock(BaseModel):
    """
    Chain-of-Thought reasoning block for semantic comparison.
    Forces the LLM to analyze both texts before concluding.
    """
    text_a_meaning: str = Field(
        default="",
        max_length=300,
        description="Wat betekent tekst A (voorwaarden)?"
    )
    text_b_meaning: str = Field(
        default="",
        max_length=300,
        description="Wat betekent tekst B (polis)?"
    )
    comparison: str = Field(
        default="",
        max_length=300,
        description="Zijn er belangrijke verschillen in betekenis?"
    )


class SemanticMatchResultModel(BaseModel):
    """
    Validated semantic match result from LLM response.
    """
    is_same_meaning: bool = Field(default=False)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = Field(default="Geen uitleg beschikbaar", max_length=500)
    matching_article: Optional[str] = Field(default=None)
    differences: Optional[str] = Field(default=None, max_length=500)

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


class SemanticMatchResponseModel(BaseModel):
    """
    Full LLM response with Chain-of-Thought.
    """
    thinking: Optional[SemanticThinkingBlock] = None
    result: SemanticMatchResultModel

    @model_validator(mode='after')
    def check_consistency(self):
        """Warn if thinking suggests difference but result says same meaning."""
        if self.thinking:
            comparison_text = self.thinking.comparison.lower()

            # Check for difference signals in thinking
            difference_signals = ['verschil', 'anders', 'afwijk', 'niet hetzelfde', 'uitbrei', 'beperk']
            has_difference = any(signal in comparison_text for signal in difference_signals)

            if has_difference and self.result.is_same_meaning:
                logger.warning(
                    f"CoT inconsistency: thinking mentions differences but result says same meaning. "
                    f"Confidence: {self.result.confidence}"
                )
        return self


# =============================================================================
# Result Dataclass (Backwards Compatible)
# =============================================================================

@dataclass
class SemanticMatchResult:
    """
    Result of semantic match verification.

    Attributes:
        is_same_meaning: True if both texts have the same meaning
        explanation: Why they are/aren't semantically equivalent
        matching_article: Reference to the matching article/section
        confidence: Confidence level (0.0 - 1.0)
        differences: Key differences if not a full match
        thinking: Optional Chain-of-Thought reasoning (for debugging)
        raw_response: Original LLM response for debugging
    """
    is_same_meaning: bool
    explanation: str
    matching_article: Optional[str] = None
    confidence: float = 0.0
    differences: Optional[str] = None
    thinking: Optional[dict] = None
    raw_response: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'SemanticMatchResult':
        """
        Parse a SemanticMatchResult from JSON string with robust handling.

        Uses Pydantic validation for:
        - Automatic confidence clamping (0.0-1.0)
        - Missing field defaults
        - Type coercion

        Handles:
        - Markdown code blocks (```json ... ```)
        - Nested JSON objects
        - Malformed responses with fallback

        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging

        Returns:
            SemanticMatchResult instance
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
                validated = SemanticMatchResponseModel.model_validate(data)
                thinking_dict = validated.thinking.model_dump() if validated.thinking else None
                result = validated.result
            else:
                # Legacy flat format
                result = SemanticMatchResultModel.model_validate(data)
                thinking_dict = None

            logger.debug(f"Successfully parsed semantic match: is_same_meaning={result.is_same_meaning}")

            return cls(
                is_same_meaning=result.is_same_meaning,
                explanation=result.explanation,
                matching_article=result.matching_article,
                confidence=result.confidence,
                differences=result.differences,
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
    def _fallback_parse(cls, json_str: str, raw_response: str = None) -> 'SemanticMatchResult':
        """
        Fallback parsing using keyword detection.

        Used when JSON parsing fails completely.
        Returns low confidence result.
        """
        logger.warning("Using fallback keyword parsing for semantic match")

        text_lower = json_str.lower()

        # Detect match from keywords
        positive_signals = ['zelfde', 'same', 'identiek', 'equivalent', 'overeenkom']
        negative_signals = ['niet zelfde', 'not same', 'verschillend', 'anders', 'afwijk']

        has_positive = any(signal in text_lower for signal in positive_signals)
        has_negative = any(signal in text_lower for signal in negative_signals)

        # Negative signals override positive
        is_match = has_positive and not has_negative

        return cls(
            is_same_meaning=is_match,
            explanation=f"Fallback parsing (JSON failed): {json_str[:200]}...",
            matching_article=None,
            confidence=0.3,  # Low confidence for fallback
            differences=None,
            thinking=None,
            raw_response=raw_response
        )

    @classmethod
    def fallback(cls, error_message: str) -> 'SemanticMatchResult':
        """Create a fallback result when verification fails."""
        return cls(
            is_same_meaning=False,
            explanation=f"Verificatie mislukt: {error_message}",
            matching_article=None,
            confidence=0.0,
            differences=None,
            thinking=None,
            raw_response=None
        )


# =============================================================================
# Prompt Builder
# =============================================================================

class SemanticMatchPrompt:
    """
    Prompt builder for semantic match verification.

    This prompt asks the LLM to verify if two texts have the same meaning,
    even when they are written differently. Used after embedding-based
    similarity finds a potential match.

    Uses Chain-of-Thought (CoT) to enforce explicit reasoning
    before the LLM reaches a conclusion.
    """

    SYSTEM_PROMPT = """Je bent een expert verzekeringsanalist die teksten vergelijkt op BETEKENIS.

Je taak is om te bepalen of twee teksten dezelfde BETEKENIS hebben, ook als ze anders zijn geformuleerd.

BELANGRIJK - DENK EERST NA:
Je MOET eerst beide teksten analyseren in het "thinking" blok voordat je concludeert.
Dit voorkomt dat je belangrijke verschillen mist.

REGELS:
- Vergelijk de INHOUD en BETEKENIS, niet de exacte woorden
- Kleine verschillen in formulering zijn acceptabel als de betekenis hetzelfde is
- Let op: uitbreidingen, beperkingen of afwijkende voorwaarden maken het NIET dezelfde betekenis
- Een tekst die MEER of MINDER dekt dan de andere heeft NIET dezelfde betekenis
- Wees conservatief: bij twijfel is het NIET dezelfde betekenis

Antwoord ALTIJD in JSON formaat met het exacte schema hieronder."""

    USER_PROMPT_TEMPLATE = """Vergelijk de volgende twee teksten:

TEKST A (uit de voorwaarden):
---
{text_a}
---

TEKST B (vrije tekst op de polis):
---
{text_b}
---

OPDRACHT: Bepaal of deze twee teksten dezelfde BETEKENIS hebben.

STAP 1: Analyseer wat tekst A betekent (vul "thinking" in)
STAP 2: Analyseer wat tekst B betekent
STAP 3: Vergelijk en concludeer (vul "result" in)

Criteria voor "zelfde betekenis":
1. Ze beschrijven dezelfde dekking/uitsluiting/voorwaarde
2. Ze gelden voor dezelfde situaties
3. Er zijn geen belangrijke uitbreidingen of beperkingen in een van beide
4. Eventuele bedragen/percentages zijn gelijk of niet gespecificeerd in een van beide

Output JSON (EXACT dit format):
{{
    "thinking": {{
        "text_a_meaning": "Wat betekent tekst A? (max 2 zinnen)",
        "text_b_meaning": "Wat betekent tekst B? (max 2 zinnen)",
        "comparison": "Zijn er belangrijke verschillen? (max 2 zinnen)"
    }},
    "result": {{
        "is_same_meaning": true of false,
        "confidence": 0.0-1.0,
        "explanation": "Korte uitleg waarom wel/niet dezelfde betekenis",
        "matching_article": "{article_ref}",
        "differences": "Belangrijkste verschillen (of null als zelfde betekenis)"
    }}
}}"""

    @classmethod
    def build(
        cls,
        text_a: str,
        text_b: str,
        article_ref: str = "Voorwaarden"
    ) -> tuple:
        """
        Build the prompt for semantic match verification.

        Args:
            text_a: Text from the conditions (voorwaarden)
            text_b: Free text from the policy (polis)
            article_ref: Reference to the article/section in conditions

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Truncate inputs to prevent token overflow
        text_a = text_a[:2000] if text_a else ""
        text_b = text_b[:2000] if text_b else ""
        article_ref = article_ref or "Voorwaarden"

        if not text_a:
            logger.warning("Empty text_a provided to SemanticMatchPrompt")

        if not text_b:
            logger.warning("Empty text_b provided to SemanticMatchPrompt")

        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            text_a=text_a,
            text_b=text_b,
            article_ref=article_ref
        )

        return cls.SYSTEM_PROMPT, user_prompt

    @classmethod
    def build_messages(
        cls,
        text_a: str,
        text_b: str,
        article_ref: str = "Voorwaarden"
    ) -> list:
        """
        Build messages list for chat completion API.

        Args:
            text_a: Text from the conditions
            text_b: Free text from the policy
            article_ref: Reference to the matching article

        Returns:
            List of message dicts for chat completion
        """
        system_prompt, user_prompt = cls.build(text_a, text_b, article_ref)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
