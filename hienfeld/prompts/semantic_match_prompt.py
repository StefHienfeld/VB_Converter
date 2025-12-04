# hienfeld/prompts/semantic_match_prompt.py
"""
Prompt for Semantic Match Verification.

Verifies if two texts have the same meaning, even when written differently.
Used after embedding-based similarity finds a potential match.
"""
from dataclasses import dataclass
from typing import Optional
import json
import re


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
        raw_response: Original LLM response for debugging
    """
    is_same_meaning: bool
    explanation: str
    matching_article: Optional[str] = None
    confidence: float = 0.0
    differences: Optional[str] = None
    raw_response: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'SemanticMatchResult':
        """
        Parse a SemanticMatchResult from JSON string.
        
        Expected format:
        {
            "is_same_meaning": true/false,
            "explanation": "...",
            "matching_article": "...",
            "confidence": 0.9,
            "differences": "..." (optional)
        }
        
        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging
            
        Returns:
            SemanticMatchResult instance
        """
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^{}]*\}', json_str, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(json_str)
            
            return cls(
                is_same_meaning=bool(data.get('is_same_meaning', False)),
                explanation=str(data.get('explanation', 'Geen uitleg beschikbaar')),
                matching_article=data.get('matching_article'),
                confidence=float(data.get('confidence', 0.8)),
                differences=data.get('differences'),
                raw_response=raw_response
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Fallback: try to interpret the response
            is_match = any(word in json_str.lower() for word in ['zelfde', 'same', 'identiek', 'equivalent'])
            is_match = is_match and not any(word in json_str.lower() for word in ['niet zelfde', 'not same', 'verschillend'])
            
            return cls(
                is_same_meaning=is_match,
                explanation=f"Kon JSON niet parsen: {json_str[:200]}",
                matching_article=None,
                confidence=0.3,
                differences=None,
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
            raw_response=None
        )


class SemanticMatchPrompt:
    """
    Prompt builder for semantic match verification.
    
    This prompt asks the LLM to verify if two texts have the same meaning,
    even when they are written differently. Used after embedding-based
    similarity finds a potential match.
    """
    
    SYSTEM_PROMPT = """Je bent een expert verzekeringsanalist die teksten vergelijkt op BETEKENIS.

Je taak is om te bepalen of twee teksten dezelfde BETEKENIS hebben, ook als ze anders zijn geformuleerd.

BELANGRIJK:
- Vergelijk de INHOUD en BETEKENIS, niet de exacte woorden
- Kleine verschillen in formulering zijn acceptabel als de betekenis hetzelfde is
- Let op: uitbreidingen, beperkingen of afwijkende voorwaarden maken het NIET dezelfde betekenis
- Een tekst die MEER of MINDER dekt dan de andere heeft NIET dezelfde betekenis

Antwoord ALTIJD in JSON formaat."""

    USER_PROMPT_TEMPLATE = """Vergelijk de volgende twee teksten:

TEKST A (uit de voorwaarden):
---
{text_a}
---

TEKST B (vrije tekst op de polis):
---
{text_b}
---

VRAAG: Hebben deze twee teksten dezelfde BETEKENIS?

Criteria voor "zelfde betekenis":
1. Ze beschrijven dezelfde dekking/uitsluiting/voorwaarde
2. Ze gelden voor dezelfde situaties
3. Er zijn geen belangrijke uitbreidingen of beperkingen in één van beide
4. Eventuele bedragen/percentages zijn gelijk of niet gespecificeerd in één van beide

Output JSON (alleen dit formaat):
{{
    "is_same_meaning": true/false,
    "explanation": "korte uitleg waarom wel/niet dezelfde betekenis",
    "matching_article": "{article_ref}",
    "confidence": 0.0-1.0,
    "differences": "belangrijkste verschillen (indien van toepassing)"
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
        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            text_a=text_a[:2000],  # Limit input length
            text_b=text_b[:2000],  # Limit input length
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

