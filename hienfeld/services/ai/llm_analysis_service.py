# hienfeld/services/ai/llm_analysis_service.py
"""
LLM-based analysis service for enhanced clause analysis.
"""
from typing import List, Optional, Any

from ...domain.cluster import Cluster
from ...domain.policy_document import PolicyDocumentSection
from ...domain.analysis import AnalysisAdvice, ConfidenceLevel
from .rag_service import RAGService
from ...logging_config import get_logger

logger = get_logger('llm_analysis_service')


class LLMAnalysisService:
    """
    LLM-powered analysis service.
    
    Uses retrieval-augmented generation to provide context-aware
    analysis of policy clauses.
    
    Can be integrated with various LLM providers:
    - OpenAI API
    - Azure OpenAI
    - Local models via Ollama
    - Other providers
    """
    
    def __init__(
        self,
        client: Any = None,
        rag_service: Optional[RAGService] = None,
        model_name: str = "gpt-4",
        temperature: float = 0.0
    ):
        """
        Initialize LLM analysis service.
        
        Args:
            client: LLM client (e.g., OpenAI client)
            rag_service: Optional RAG service for context retrieval
            model_name: Model to use for analysis
            temperature: Generation temperature
        """
        self.client = client
        self.rag_service = rag_service
        self.model_name = model_name
        self.temperature = temperature
    
    def analyze_cluster_with_context(
        self,
        cluster: Cluster,
        policy_sections: Optional[List[PolicyDocumentSection]] = None
    ) -> AnalysisAdvice:
        """
        Analyze a cluster using LLM with relevant context.
        
        Args:
            cluster: Cluster to analyze
            policy_sections: Optional list of relevant policy sections
            
        Returns:
            AnalysisAdvice from LLM
        """
        if self.client is None:
            logger.warning("No LLM client configured")
            return self._fallback_advice(cluster)
        
        # Get context from RAG if available
        context = ""
        if self.rag_service and self.rag_service.is_ready():
            context = self.rag_service.get_context_for_analysis(
                cluster.original_text,
                top_k=3
            )
        elif policy_sections:
            # Use provided sections as context
            context = self._format_sections_as_context(policy_sections[:3])
        
        # Build prompt
        prompt = self._build_analysis_prompt(cluster, context)
        
        try:
            # Call LLM
            response = self._call_llm(prompt)
            
            # Parse response
            return self._parse_llm_response(response, cluster)
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_advice(cluster)
    
    def _build_analysis_prompt(self, cluster: Cluster, context: str) -> str:
        """
        Build the analysis prompt for the LLM.
        
        Args:
            cluster: Cluster to analyze
            context: Retrieved context from policy documents
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Je bent een expert in verzekeringspolissen. Analyseer de volgende clausuletekst en bepaal of deze:
1. VERWIJDEREN - al gedekt is door de standaard voorwaarden
2. SPLITSEN - meerdere clausules bevat die apart moeten
3. STANDAARDISEREN - vaak voorkomt en een standaardcode verdient
4. BEHOUDEN - een specifieke afwijking/uitbreiding is die behouden moet
5. HANDMATIG CHECKEN - niet automatisch te beoordelen

## Clausuletekst
{cluster.original_text[:1500]}

## Frequentie
Deze tekst (of zeer vergelijkbare) komt {cluster.frequency}x voor in de polisdata.

## Relevante voorwaarden
{context if context else "Geen context beschikbaar."}

## Gevraagde output
Geef je analyse in het volgende formaat:
ADVIES: [een van bovenstaande opties]
REDEN: [korte uitleg]
VERTROUWEN: [Laag/Midden/Hoog]
ARTIKEL: [referentie naar artikel als relevant, anders "-"]
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM API.
        
        Args:
            prompt: The prompt to send
            
        Returns:
            Response text
        """
        # OpenAI-style client
        if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature
            )
            return response.choices[0].message.content
        
        # Generic client with __call__
        if callable(self.client):
            return self.client(prompt)
        
        raise ValueError("Unsupported LLM client type")
    
    def _parse_llm_response(self, response: str, cluster: Cluster) -> AnalysisAdvice:
        """
        Parse LLM response into AnalysisAdvice.
        
        Args:
            response: Raw LLM response
            cluster: Original cluster for metadata
            
        Returns:
            Parsed AnalysisAdvice
        """
        # Default values
        advice_code = "HANDMATIG CHECKEN"
        reason = "LLM analyse uitgevoerd"
        confidence = "Midden"
        article = "-"
        
        # Parse response lines
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            
            if line.startswith('ADVIES:'):
                value = line.replace('ADVIES:', '').strip()
                if 'VERWIJDEREN' in value.upper():
                    advice_code = "VERWIJDEREN"
                elif 'SPLITSEN' in value.upper():
                    advice_code = "⚠️ SPLITSEN"
                elif 'STANDAARDISEREN' in value.upper():
                    advice_code = "🛠️ STANDAARDISEREN"
                elif 'BEHOUDEN' in value.upper():
                    advice_code = "BEHOUDEN (CLAUSULE)"
                else:
                    advice_code = "HANDMATIG CHECKEN"
                    
            elif line.startswith('REDEN:'):
                reason = line.replace('REDEN:', '').strip()
                
            elif line.startswith('VERTROUWEN:'):
                value = line.replace('VERTROUWEN:', '').strip().lower()
                if 'hoog' in value:
                    confidence = ConfidenceLevel.HOOG.value
                elif 'midden' in value:
                    confidence = ConfidenceLevel.MIDDEN.value
                else:
                    confidence = ConfidenceLevel.LAAG.value
                    
            elif line.startswith('ARTIKEL:'):
                article = line.replace('ARTIKEL:', '').strip()
        
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=advice_code,
            reason=reason,
            confidence=confidence,
            reference_article=article,
            category="LLM_ANALYSIS",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )
    
    def _format_sections_as_context(
        self, 
        sections: List[PolicyDocumentSection]
    ) -> str:
        """Format policy sections as context string."""
        if not sections:
            return ""
        
        parts = []
        for s in sections:
            part = f"### {s.id}"
            if s.title:
                part += f" - {s.title}"
            part += f"\n{s.raw_text[:500]}\n"
            parts.append(part)
        
        return "\n".join(parts)
    
    def _fallback_advice(self, cluster: Cluster) -> AnalysisAdvice:
        """Generate fallback advice when LLM fails."""
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code="HANDMATIG CHECKEN",
            reason="Automatische analyse niet beschikbaar. Handmatige beoordeling vereist.",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="FALLBACK",
            cluster_name=cluster.name,
            frequency=cluster.frequency
        )
    
    @property
    def is_available(self) -> bool:
        """Check if LLM service is properly configured."""
        return self.client is not None

