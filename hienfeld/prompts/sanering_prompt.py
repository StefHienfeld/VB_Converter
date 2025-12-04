# hienfeld/prompts/sanering_prompt.py
"""
Prompt A: Sanering (Redundancy Check)

Determines if a free text clause is redundant because it's already 
covered by the policy conditions.
"""
from dataclasses import dataclass
from typing import Optional
import json
import re


@dataclass
class SaneringResult:
    """
    Result of the sanering/redundancy analysis.
    
    Attributes:
        is_redundant: True if the text is already covered by conditions
        reason: Explanation of why it is/isn't redundant
        matching_article: The article that covers this text (if redundant)
        confidence: How confident the LLM is (0.0 - 1.0)
        raw_response: The raw LLM response for debugging
    """
    is_redundant: bool
    reason: str
    matching_article: Optional[str] = None
    confidence: float = 0.0
    raw_response: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'SaneringResult':
        """
        Parse a SaneringResult from JSON string.
        
        Expected format:
        {"is_redundant": true/false, "reason": "...", "matching_article": "..."}
        
        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging
            
        Returns:
            SaneringResult instance
        """
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^{}]*\}', json_str, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(json_str)
            
            return cls(
                is_redundant=bool(data.get('is_redundant', False)),
                reason=str(data.get('reason', 'Geen reden opgegeven')),
                matching_article=data.get('matching_article'),
                confidence=float(data.get('confidence', 0.8)),
                raw_response=raw_response
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Fallback: try to interpret the response
            is_redundant = 'redundant' in json_str.lower() and 'niet redundant' not in json_str.lower()
            return cls(
                is_redundant=is_redundant,
                reason=f"Kon JSON niet parsen: {json_str[:200]}",
                matching_article=None,
                confidence=0.3,
                raw_response=raw_response
            )
    
    @classmethod
    def fallback(cls, error_message: str) -> 'SaneringResult':
        """Create a fallback result when analysis fails."""
        return cls(
            is_redundant=False,
            reason=f"Analyse mislukt: {error_message}",
            matching_article=None,
            confidence=0.0,
            raw_response=None
        )


class SaneringPrompt:
    """
    Prompt builder for sanering/redundancy analysis.
    
    This prompt asks the LLM to determine if a free text clause
    is already covered by the policy conditions.
    """
    
    SYSTEM_PROMPT = """Je bent een expert verzekeringsanalist gespecialiseerd in polisvoorwaarden.
Je taak is om te bepalen of een vrije tekst clausule REDUNDANT is omdat deze al gedekt wordt door de standaard polisvoorwaarden.

BELANGRIJK:
- Een tekst is REDUNDANT als de voorwaarden dezelfde dekking/uitsluiting al bevatten
- Een tekst is NIET REDUNDANT als deze iets specifieks toevoegt, wijzigt of beperkt
- Wees conservatief: bij twijfel is het NIET redundant

Antwoord ALTIJD in JSON formaat."""

    USER_PROMPT_TEMPLATE = """Context (Relevante voorwaarden):
{policy_chunks}

---

Input (Vrije tekst clausule):
"{input_text}"

---

Taak: Bepaal of de Input redundant is ten opzichte van de Context.

Regels:
1. Als de Input exact hetzelfde zegt als de Context (maar in andere woorden) -> REDUNDANT
2. Als de Input een specifieke uitbreiding toevoegt die NIET in de Context staat -> NIET REDUNDANT
3. Als de Input een beperking toevoegt die NIET in de Context staat -> NIET REDUNDANT
4. Als de Input specifieke bedragen, percentages of voorwaarden noemt die afwijken -> NIET REDUNDANT

Output JSON (alleen dit formaat):
{{"is_redundant": true/false, "reason": "korte uitleg", "matching_article": "artikel nummer of null"}}"""

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
        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            input_text=input_text[:2000],  # Limit input length
            policy_chunks=policy_chunks[:4000]  # Limit context length
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

