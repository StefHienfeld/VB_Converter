# hienfeld/prompts/__init__.py
"""
Prompt templates for LLM-based analysis.

This module contains structured prompts for:
- Sanering (redundancy check): Is a free text redundant given the policy conditions?
- Compliance (conflict check): Does a free text conflict with policy conditions?
- Admin (hygiene check): Does a free text have administrative issues?
"""

from .sanering_prompt import SaneringPrompt, SaneringResult
from .compliance_prompt import CompliancePrompt, ComplianceResult
from .admin_prompt import AdminPrompt, AdminPromptResult, AdminCategory

__all__ = [
    'SaneringPrompt',
    'SaneringResult', 
    'CompliancePrompt',
    'ComplianceResult',
    'AdminPrompt',
    'AdminPromptResult',
    'AdminCategory'
]

