# hienfeld/prompts/sanering_prompt.py
"""
Prompt A: Sanering (Redundancy Check)

Determines if a free text clause is redundant because it's already
covered by the policy conditions.

Enhanced with:
- Pydantic validation for robust JSON parsing
- Chain-of-Thought (CoT) enforced reasoning
- Automatic confidence clamping
"""
from dataclasses import dataclass
from typing import Optional, List
import json
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from ..logging_config import get_logger

logger = get_logger('sanering_prompt')


# =============================================================================
# Pydantic Models for Validation
# =============================================================================

class ThinkingBlock(BaseModel):
    """
    Chain-of-Thought reasoning block.
    Forces the LLM to think before concluding.
    """
    observation: str = Field(
        default="",
        max_length=300,
        description="Wat zie ik in deze clausule?"
    )
    comparison: str = Field(
        default="",
        max_length=300,
        description="Hoe verhoudt dit zich tot de voorwaarden?"
    )
    reasoning: str = Field(
        default="",
        max_length=300,
        description="Waarom is dit wel/niet redundant?"
    )


class SaneringResultModel(BaseModel):
    """
    Validated result block from LLM response.
    """
    is_redundant: bool = Field(default=False)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = Field(default="Geen reden opgegeven", max_length=500)
    matching_article: Optional[str] = Field(default=None)

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


class SaneringResponseModel(BaseModel):
    """
    Full LLM response with Chain-of-Thought.
    """
    thinking: Optional[ThinkingBlock] = None
    result: SaneringResultModel

    @model_validator(mode='after')
    def check_consistency(self):
        """Warn if thinking contradicts result."""
        if self.thinking:
            thinking_text = f"{self.thinking.observation} {self.thinking.reasoning}".lower()

            # Check for contradiction signals
            has_negative = any(word in thinking_text for word in ['niet redundant', 'geen overlap', 'afwijkend'])

            if self.result.is_redundant and has_negative:
                logger.warning(
                    f"CoT inconsistency detected: thinking suggests NOT redundant "
                    f"but result says redundant. Review needed."
                )
        return self


# =============================================================================
# Result Dataclass (Backwards Compatible)
# =============================================================================

@dataclass
class SaneringResult:
    """
    Result of the sanering/redundancy analysis.

    Attributes:
        is_redundant: True if the text is already covered by conditions
        reason: Explanation of why it is/isn't redundant
        matching_article: The article that covers this text (if redundant)
        confidence: How confident the LLM is (0.0 - 1.0)
        thinking: Optional Chain-of-Thought reasoning (for debugging)
        raw_response: The raw LLM response for debugging
    """
    is_redundant: bool
    reason: str
    matching_article: Optional[str] = None
    confidence: float = 0.0
    thinking: Optional[dict] = None
    raw_response: Optional[str] = None

    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'SaneringResult':
        """
        Parse a SaneringResult from JSON string with robust handling.

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
            SaneringResult instance
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
                validated = SaneringResponseModel.model_validate(data)
                thinking_dict = validated.thinking.model_dump() if validated.thinking else None
                result = validated.result
            else:
                # Legacy flat format
                result = SaneringResultModel.model_validate(data)
                thinking_dict = None

            logger.debug(f"Successfully parsed sanering result: is_redundant={result.is_redundant}")

            return cls(
                is_redundant=result.is_redundant,
                reason=result.reason,
                matching_article=result.matching_article,
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
    def _fallback_parse(cls, json_str: str, raw_response: str = None) -> 'SaneringResult':
        """
        Fallback parsing using keyword detection.

        Used when JSON parsing fails completely.
        Returns low confidence result.
        """
        logger.warning("Using fallback keyword parsing")

        text_lower = json_str.lower()

        # Detect redundancy from keywords
        positive_signals = ['redundant', 'al gedekt', 'overbodig', 'komt overeen']
        negative_signals = ['niet redundant', 'niet overbodig', 'aanvulling', 'wijkt af']

        has_positive = any(signal in text_lower for signal in positive_signals)
        has_negative = any(signal in text_lower for signal in negative_signals)

        # Negative signals override positive
        is_redundant = has_positive and not has_negative

        return cls(
            is_redundant=is_redundant,
            reason=f"Fallback parsing (JSON failed): {json_str[:200]}...",
            matching_article=None,
            confidence=0.3,  # Low confidence for fallback
            thinking=None,
            raw_response=raw_response
        )

    @classmethod
    def fallback(cls, error_message: str) -> 'SaneringResult':
        """Create a fallback result when analysis fails completely."""
        return cls(
            is_redundant=False,
            reason=f"Analyse mislukt: {error_message}",
            matching_article=None,
            confidence=0.0,
            thinking=None,
            raw_response=None
        )


# =============================================================================
# Prompt Builder
# =============================================================================

class SaneringPrompt:
    """
    Prompt builder for sanering/redundancy analysis.

    This prompt asks the LLM to determine if a free text clause
    is already covered by the policy conditions.

    Uses Chain-of-Thought (CoT) to enforce explicit reasoning
    before the LLM reaches a conclusion.
    """

    SYSTEM_PROMPT = """Je bent een expert verzekeringsanalist gespecialiseerd in polisvoorwaarden.
Je taak is om te bepalen of een vrije tekst clausule REDUNDANT is omdat deze al gedekt wordt door de standaard polisvoorwaarden.

BELANGRIJK - DENK EERST NA:
Je MOET eerst je redenering uitschrijven in het "thinking" blok voordat je een conclusie geeft.
Dit helpt je om geen fouten te maken.

REGELS:
- Een tekst is REDUNDANT als de voorwaarden dezelfde dekking/uitsluiting al bevatten
- Een tekst is NIET REDUNDANT als deze iets specifieks toevoegt, wijzigt of beperkt
- Wees conservatief: bij twijfel is het NIET redundant
- Let op specifieke bedragen, percentages en voorwaarden - deze maken een clausule vaak NIET redundant

Antwoord ALTIJD in JSON formaat met het exacte schema hieronder."""

    USER_PROMPT_TEMPLATE = """Context (Relevante voorwaarden):
{policy_chunks}

---

Input (Vrije tekst clausule):
"{input_text}"

---

OPDRACHT: Bepaal of de Input redundant is ten opzichte van de Context.

STAP 1: Analyseer de clausule (vul "thinking" in)
STAP 2: Vergelijk met de voorwaarden
STAP 3: Trek je conclusie (vul "result" in)

Regels:
1. Als de Input exact hetzelfde zegt als de Context (maar in andere woorden) -> REDUNDANT
2. Als de Input een specifieke uitbreiding toevoegt die NIET in de Context staat -> NIET REDUNDANT
3. Als de Input een beperking toevoegt die NIET in de Context staat -> NIET REDUNDANT
4. Als de Input specifieke bedragen, percentages of voorwaarden noemt die afwijken -> NIET REDUNDANT

Output JSON (EXACT dit format):
{{
    "thinking": {{
        "observation": "Wat zie ik in deze clausule? (max 2 zinnen)",
        "comparison": "Wat zeggen de voorwaarden hierover? (max 2 zinnen)",
        "reasoning": "Waarom is dit wel/niet redundant? (max 2 zinnen)"
    }},
    "result": {{
        "is_redundant": true of false,
        "confidence": 0.0 tot 1.0,
        "reason": "Korte conclusie (max 1 zin)",
        "matching_article": "Artikel nummer of null"
    }}
}}"""

    @classmethod
    def build(cls, input_text: str, policy_chunks: str) -> tuple:
        """
        Build the prompt for sanering analysis.

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
            logger.warning("Empty input text provided to SaneringPrompt")

        if not policy_chunks:
            logger.warning("Empty policy context provided to SaneringPrompt")

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
