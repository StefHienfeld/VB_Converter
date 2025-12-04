# hienfeld/prompts/compliance_prompt.py
"""
Prompt B: Compliance (Conflict Check)

Analyzes whether a free text clause conflicts with, extends, or limits
the standard policy conditions.
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import json
import re


class ComplianceCategory(Enum):
    """Categories of compliance analysis results."""
    CONFLICT = "CONFLICT"       # Clause contradicts policy conditions
    EXTENSION = "EXTENSION"     # Clause extends coverage beyond conditions
    LIMITATION = "LIMITATION"   # Clause limits coverage compared to conditions
    NEUTRAL = "NEUTRAL"         # Clause is neutral/clarifying only
    UNKNOWN = "UNKNOWN"         # Could not determine


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
        raw_response: The raw LLM response for debugging
    """
    category: ComplianceCategory
    risk_score: int
    advice: str
    cited_article: Optional[str] = None
    legal_subject: Optional[str] = None
    confidence: float = 0.0
    raw_response: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_str: str, raw_response: str = None) -> 'ComplianceResult':
        """
        Parse a ComplianceResult from JSON string.
        
        Expected format:
        {
            "category": "CONFLICT|EXTENSION|LIMITATION|NEUTRAL",
            "risk_score": 1-10,
            "advice": "...",
            "cited_article": "...",
            "legal_subject": "..."
        }
        
        Args:
            json_str: JSON string to parse
            raw_response: Original full response for debugging
            
        Returns:
            ComplianceResult instance
        """
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^{}]*\}', json_str, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(json_str)
            
            # Parse category
            category_str = str(data.get('category', 'UNKNOWN')).upper()
            try:
                category = ComplianceCategory(category_str)
            except ValueError:
                category = ComplianceCategory.UNKNOWN
            
            # Parse risk score
            risk_score = int(data.get('risk_score', 5))
            risk_score = max(1, min(10, risk_score))  # Clamp to 1-10
            
            return cls(
                category=category,
                risk_score=risk_score,
                advice=str(data.get('advice', 'Geen advies beschikbaar')),
                cited_article=data.get('cited_article'),
                legal_subject=data.get('legal_subject'),
                confidence=float(data.get('confidence', 0.8)),
                raw_response=raw_response
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Fallback: try to interpret the response
            return cls(
                category=ComplianceCategory.UNKNOWN,
                risk_score=5,
                advice=f"Kon JSON niet parsen: {json_str[:200]}",
                cited_article=None,
                legal_subject=None,
                confidence=0.3,
                raw_response=raw_response
            )
    
    @classmethod
    def fallback(cls, error_message: str) -> 'ComplianceResult':
        """Create a fallback result when analysis fails."""
        return cls(
            category=ComplianceCategory.UNKNOWN,
            risk_score=5,
            advice=f"Analyse mislukt: {error_message}",
            cited_article=None,
            legal_subject=None,
            confidence=0.0,
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


class CompliancePrompt:
    """
    Prompt builder for compliance/conflict analysis.
    
    This prompt asks the LLM to analyze whether a free text clause
    conflicts with, extends, or limits the policy conditions.
    """
    
    SYSTEM_PROMPT = """Je bent een Senior Underwriter en Compliance Officer bij een verzekeringsmaatschappij.
Je analyseert vrije tekst clausules op mogelijke conflicten met de standaard polisvoorwaarden.

ANALYSE STAPPEN:
1. Identificeer het juridische onderwerp (bijv. eigen risico, dekkingsgebied, uitsluitingen)
2. Zoek het relevante artikel in de voorwaarden
3. Vergelijk de clausule met het artikel
4. Bepaal de categorie en risicoscore

CATEGORIEËN:
- CONFLICT: Clausule spreekt de voorwaarden tegen (niet toegestaan)
- EXTENSION: Clausule breidt de dekking uit (vereist acceptatie)
- LIMITATION: Clausule beperkt de dekking (meestal toegestaan)
- NEUTRAL: Clausule is verduidelijkend zonder inhoudelijke wijziging

Antwoord ALTIJD in JSON formaat."""

    USER_PROMPT_TEMPLATE = """Context (Polisvoorwaarden):
{policy_chunks}

---

Input (Clausule om te analyseren):
"{input_text}"

---

Analyseer stap voor stap:

1. Identificeer het juridische onderwerp van de clausule
2. Citeer het relevante artikel uit de voorwaarden
3. Vergelijk de clausule met het artikel
4. Bepaal de categorie en risicoscore (1-10)

Output JSON (alleen dit formaat):
{{
    "legal_subject": "het juridische onderwerp",
    "cited_article": "artikel nummer",
    "category": "CONFLICT|EXTENSION|LIMITATION|NEUTRAL",
    "risk_score": 1-10,
    "advice": "kort advies voor de underwriter"
}}

Risicoscore richtlijnen:
- 1-3: Laag risico, geen actie nodig
- 4-6: Matig risico, review aanbevolen
- 7-10: Hoog risico, actie vereist"""

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

