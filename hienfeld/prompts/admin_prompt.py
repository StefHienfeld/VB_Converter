# hienfeld/prompts/admin_prompt.py
"""
Prompt C: Administrative / Hygiene Check

Analyzes text for administrative issues that are NOT related to content:
- Incomplete sentences
- Internally contradictory information
- References to past dates/events
- Unreadable or corrupt text
- General quality issues

This is a "lighter" prompt that doesn't need policy context.
"""
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
import json
import re
from datetime import datetime


class AdminCategory(Enum):
    """Categories of administrative issues."""
    INCOMPLEET = "INCOMPLEET"       # Incomplete sentence/missing info
    VEROUDERD = "VEROUDERD"         # References past date
    TEGENSTRIJDIG = "TEGENSTRIJDIG" # Internally contradictory
    ONLEESBAAR = "ONLEESBAAR"       # Unreadable/corrupt
    OK = "OK"                        # No issues found


@dataclass
class AdminPromptResult:
    """
    Result of the administrative/hygiene AI analysis.
    
    Attributes:
        has_issues: True if any issues were found
        issues: List of issue dictionaries with type and description
        recommendation: Recommended action
        summary: 1-sentence summary of the clause
        confidence: How confident the AI is (0.0 - 1.0)
        raw_response: The raw LLM response for debugging
    """
    has_issues: bool
    issues: List[dict]
    recommendation: str
    summary: Optional[str] = None
    confidence: float = 0.0
    raw_response: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'AdminPromptResult':
        """
        Parse an AdminPromptResult from JSON string.
        
        Expected format:
        {
            "has_issues": true/false,
            "issues": [{"type": "...", "description": "..."}],
            "recommendation": "OPSCHONEN|AANVULLEN|VERWIJDEREN|OK",
            "summary": "korte samenvatting"
        }
        
        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging
            
        Returns:
            AdminPromptResult instance
        """
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(json_str)
            
            return cls(
                has_issues=bool(data.get('has_issues', False)),
                issues=data.get('issues', []),
                recommendation=str(data.get('recommendation', 'OK')),
                summary=data.get('summary'),
                confidence=float(data.get('confidence', 0.8)),
                raw_response=raw_response
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Fallback: try to interpret the response
            has_issues = any(word in json_str.lower() for word in 
                          ['incompleet', 'verouderd', 'tegenstrijdig', 'onleesbaar', 'probleem'])
            return cls(
                has_issues=has_issues,
                issues=[{"type": "UNKNOWN", "description": f"Kon JSON niet parsen: {json_str[:200]}"}],
                recommendation="HANDMATIG CHECKEN",
                summary=None,
                confidence=0.3,
                raw_response=raw_response
            )
    
    @classmethod
    def fallback(cls, error_message: str) -> 'AdminPromptResult':
        """Create a fallback result when analysis fails."""
        return cls(
            has_issues=False,
            issues=[],
            recommendation="OK",
            summary=None,
            confidence=0.0,
            raw_response=f"Error: {error_message}"
        )
    
    @classmethod
    def ok(cls, summary: str = None) -> 'AdminPromptResult':
        """Create an OK result (no issues found)."""
        return cls(
            has_issues=False,
            issues=[],
            recommendation="OK",
            summary=summary,
            confidence=1.0
        )


class AdminPrompt:
    """
    Prompt builder for administrative/hygiene analysis.
    
    This prompt asks the LLM to check for administrative issues
    that are NOT related to the content/meaning of the clause,
    but to its quality and completeness.
    """
    
    SYSTEM_PROMPT = """Je bent een administratief medewerker die polisclausules controleert op volledigheid en actualiteit.

Je zoekt naar problemen die NIET over de inhoud gaan, maar over de KWALITEIT van de tekst zelf.

TYPEN PROBLEMEN:
1. INCOMPLEET - De zin stopt abrupt, er mist informatie, of er staan placeholders
2. VEROUDERD - De tekst verwijst naar een datum of periode in het VERLEDEN
3. TEGENSTRIJDIG - De tekst bevat intern tegenstrijdige informatie (bijv. twee verschillende bedragen)
4. ONLEESBAAR - De tekst is corrupt, bevat rare tekens, of is onbegrijpelijk

BELANGRIJK:
- Kijk ALLEEN naar administratieve kwaliteit, niet naar juridische inhoud
- Een tekst over "terrorisme" of "molest" is NIET automatisch een probleem
- Focus op: Is de tekst compleet? Actueel? Consistent? Leesbaar?

Antwoord ALTIJD in JSON formaat."""

    USER_PROMPT_TEMPLATE = """Input clausule:
"{input_text}"

Huidige datum: {current_date}

Controleer de tekst op administratieve problemen:

1. INCOMPLEET - Ontbreekt er informatie? Stopt de zin abrupt? Zijn er placeholders?
   Voorbeelden: "Dekking geldt voor...", "[INVULLEN]", "€ ___"

2. VEROUDERD - Verwijst de tekst naar een datum of periode die al voorbij is?
   Voorbeelden: "tentoonstelling op 1 januari 2015", "verbouwing in 2019"

3. TEGENSTRIJDIG - Bevat de tekst intern tegenstrijdige informatie?
   Voorbeelden: "maximaal €1000" en later "maximaal €500"

4. ONLEESBAAR - Is de tekst corrupt of onbegrijpelijk?
   Voorbeelden: "Ã©Ã«", "???", tekst die nergens op slaat

Output JSON (alleen dit formaat):
{{
    "has_issues": true/false,
    "issues": [
        {{"type": "INCOMPLEET|VEROUDERD|TEGENSTRIJDIG|ONLEESBAAR", "description": "korte beschrijving"}}
    ],
    "recommendation": "OPSCHONEN|AANVULLEN|VERWIJDEREN|OK",
    "summary": "1-zin samenvatting van wat de clausule inhoudt"
}}

Recommendation richtlijnen:
- OK: Geen problemen gevonden
- AANVULLEN: Tekst is incompleet, informatie moet worden toegevoegd
- VERWIJDEREN: Tekst is verouderd en niet meer relevant
- OPSCHONEN: Tekst heeft encoding/leesbaarheid problemen"""

    @classmethod
    def build(cls, input_text: str, current_date: str = None) -> tuple:
        """
        Build the prompt for administrative analysis.
        
        Args:
            input_text: The free text clause to analyze
            current_date: Current date string (defaults to today)
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        if current_date is None:
            current_date = datetime.now().strftime("%d-%m-%Y")
        
        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            input_text=input_text[:2000],  # Limit input length
            current_date=current_date
        )
        
        return cls.SYSTEM_PROMPT, user_prompt
    
    @classmethod
    def build_messages(cls, input_text: str, current_date: str = None) -> list:
        """
        Build messages list for chat completion API.
        
        Args:
            input_text: The free text clause to analyze
            current_date: Current date string (defaults to today)
            
        Returns:
            List of message dicts for chat completion
        """
        system_prompt, user_prompt = cls.build(input_text, current_date)
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

