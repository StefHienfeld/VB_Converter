# hienfeld/services/ai/llm_analysis_service.py
"""
LLM-based analysis service for enhanced clause analysis.

Provides:
- Sanering analysis (redundancy check)
- Compliance analysis (conflict check)
- Batch processing with rate limiting
"""
from typing import List, Optional, Any, Callable, Dict

from ...domain.cluster import Cluster
from ...domain.policy_document import PolicyDocumentSection
from ...domain.analysis import AnalysisAdvice, ConfidenceLevel, AdviceCode
from ...prompts.sanering_prompt import SaneringPrompt, SaneringResult
from ...prompts.compliance_prompt import CompliancePrompt, ComplianceResult, ComplianceCategory
from ...prompts.semantic_match_prompt import SemanticMatchPrompt, SemanticMatchResult
from ...utils.rate_limiter import BatchProcessor, RetryConfig, RateLimitError, LLMError
from .rag_service import RAGService
from ...logging_config import get_logger

logger = get_logger('llm_analysis_service')


class LLMAnalysisService:
    """
    LLM-powered analysis service with structured prompts.
    
    Uses retrieval-augmented generation to provide context-aware
    analysis of policy clauses with two main analysis types:
    
    1. Sanering (Prompt A): Is the clause redundant given the conditions?
    2. Compliance (Prompt B): Does the clause conflict with conditions?
    
    Can be integrated with various LLM providers:
    - OpenAI API
    - Azure OpenAI
    - Local models via Ollama
    """
    
    # Default batch settings
    DEFAULT_BATCH_SIZE = 50
    DEFAULT_DELAY_BETWEEN_BATCHES = 1.0
    
    def __init__(
        self,
        client: Any = None,
        rag_service: Optional[RAGService] = None,
        model_name: str = "gpt-4",
        temperature: float = 0.0,
        batch_size: int = DEFAULT_BATCH_SIZE
    ):
        """
        Initialize LLM analysis service.
        
        Args:
            client: LLM client (e.g., OpenAI client)
            rag_service: Optional RAG service for context retrieval
            model_name: Model to use for analysis
            temperature: Generation temperature
            batch_size: Number of items to process per batch
        """
        self.client = client
        self.rag_service = rag_service
        self.model_name = model_name
        self.temperature = temperature
        self.batch_size = batch_size
        
        # Configure retry behavior
        self.retry_config = RetryConfig(
            max_retries=3,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0
        )
        
        # Batch processor for handling multiple items
        self.batch_processor = BatchProcessor(
            batch_size=batch_size,
            delay_between_batches=self.DEFAULT_DELAY_BETWEEN_BATCHES,
            retry_config=self.retry_config
        )
    
    def analyze_sanering(
        self,
        input_text: str,
        policy_context: str
    ) -> SaneringResult:
        """
        Analyze if a clause is redundant (Prompt A).
        
        Args:
            input_text: The free text clause to analyze
            policy_context: Relevant policy conditions text
            
        Returns:
            SaneringResult with redundancy assessment
        """
        if self.client is None:
            return SaneringResult.fallback("No LLM client configured")
        
        try:
            messages = SaneringPrompt.build_messages(input_text, policy_context)
            response = self._call_llm_chat(messages)
            return SaneringResult.from_json(response, raw_response=response)
        except Exception as e:
            logger.error(f"Sanering analysis failed: {e}")
            return SaneringResult.fallback(str(e))
    
    def analyze_compliance(
        self,
        input_text: str,
        policy_context: str
    ) -> ComplianceResult:
        """
        Analyze if a clause conflicts with conditions (Prompt B).
        
        Args:
            input_text: The free text clause to analyze
            policy_context: Relevant policy conditions text
            
        Returns:
            ComplianceResult with conflict assessment
        """
        if self.client is None:
            return ComplianceResult.fallback("No LLM client configured")
        
        try:
            messages = CompliancePrompt.build_messages(input_text, policy_context)
            response = self._call_llm_chat(messages)
            return ComplianceResult.from_json(response, raw_response=response)
        except Exception as e:
            logger.error(f"Compliance analysis failed: {e}")
            return ComplianceResult.fallback(str(e))
    
    def verify_semantic_match(
        self,
        conditions_text: str,
        policy_text: str,
        article_ref: str = "Voorwaarden"
    ) -> SemanticMatchResult:
        """
        Verify if two texts have the same semantic meaning.
        
        Used after embedding-based similarity finds a potential match.
        The LLM verifies whether the texts truly have the same meaning.
        
        Args:
            conditions_text: Text from the policy conditions (voorwaarden)
            policy_text: Free text from the policy (polis)
            article_ref: Reference to the article/section in conditions
            
        Returns:
            SemanticMatchResult with verification result
        """
        if self.client is None:
            return SemanticMatchResult.fallback("No LLM client configured")
        
        try:
            messages = SemanticMatchPrompt.build_messages(
                conditions_text, 
                policy_text,
                article_ref
            )
            response = self._call_llm_chat(messages)
            return SemanticMatchResult.from_json(response, raw_response=response)
        except Exception as e:
            logger.error(f"Semantic match verification failed: {e}")
            return SemanticMatchResult.fallback(str(e))
    
    def analyze_cluster_with_context(
        self,
        cluster: Cluster,
        policy_sections: Optional[List[PolicyDocumentSection]] = None
    ) -> AnalysisAdvice:
        """
        Analyze a cluster using LLM with relevant context.
        
        Uses the new structured prompts for analysis.
        
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
            context = self._format_sections_as_context(policy_sections[:3])
        
        if not context:
            return self._fallback_advice(cluster, reason="Geen voorwaarden context beschikbaar")
        
        try:
            # Step 1: Sanering check (is it redundant?)
            sanering_result = self.analyze_sanering(cluster.original_text, context)
            
            if sanering_result.is_redundant:
                return AnalysisAdvice(
                    cluster_id=cluster.id,
                    advice_code=AdviceCode.VERWIJDEREN.value,
                    reason=f"Redundant: {sanering_result.reason}",
                    confidence=ConfidenceLevel.HOOG.value if sanering_result.confidence > 0.8 else ConfidenceLevel.MIDDEN.value,
                    reference_article=sanering_result.matching_article or "-",
                    category="LLM_SANERING",
                    cluster_name=cluster.name,
                    frequency=cluster.frequency
                )
            
            # Step 2: Compliance check (is there a conflict?)
            compliance_result = self.analyze_compliance(cluster.original_text, context)
            
            return self._compliance_to_advice(compliance_result, cluster)
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._fallback_advice(cluster, reason=str(e))
    
    def analyze_clusters_batch(
        self,
        clusters: List[Cluster],
        policy_sections: Optional[List[PolicyDocumentSection]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, AnalysisAdvice]:
        """
        Analyze multiple clusters in batches with rate limiting.
        
        Args:
            clusters: List of clusters to analyze
            policy_sections: Policy sections for context
            progress_callback: Optional callback(processed, total)
            
        Returns:
            Dictionary mapping cluster_id -> AnalysisAdvice
        """
        if not self.is_available:
            logger.warning("LLM not available, returning fallback for all clusters")
            return {
                c.id: self._fallback_advice(c, "LLM niet beschikbaar")
                for c in clusters
            }
        
        logger.info(f"Starting batch analysis of {len(clusters)} clusters")
        
        def process_cluster(cluster: Cluster) -> AnalysisAdvice:
            return self.analyze_cluster_with_context(cluster, policy_sections)
        
        def fallback_for_cluster(cluster: Cluster, error: Exception) -> AnalysisAdvice:
            return self._fallback_advice(cluster, f"Fout: {str(error)}")
        
        # Process in batches
        results = self.batch_processor.process(
            items=clusters,
            process_func=process_cluster,
            fallback_func=fallback_for_cluster,
            progress_callback=progress_callback
        )
        
        # Convert to dictionary
        return {cluster.id: advice for cluster, advice in zip(clusters, results)}
    
    def _call_llm_chat(self, messages: List[dict]) -> str:
        """
        Call LLM with chat messages format.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Response text
        """
        # OpenAI-style client
        if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature
            )
            return response.choices[0].message.content
        
        # Generic client with __call__ (pass as single prompt)
        if callable(self.client):
            # Combine messages into single prompt
            prompt = "\n\n".join([
                f"{m['role'].upper()}: {m['content']}" 
                for m in messages
            ])
            return self.client(prompt)
        
        raise ValueError("Unsupported LLM client type")
    
    def _compliance_to_advice(
        self, 
        result: ComplianceResult, 
        cluster: Cluster
    ) -> AnalysisAdvice:
        """
        Convert ComplianceResult to AnalysisAdvice.
        
        Args:
            result: Compliance analysis result
            cluster: The analyzed cluster
            
        Returns:
            AnalysisAdvice
        """
        # Map category to advice code
        if result.category == ComplianceCategory.CONFLICT:
            advice_code = "⚠️ CONFLICT"
            confidence = ConfidenceLevel.HOOG.value
        elif result.category == ComplianceCategory.EXTENSION:
            advice_code = "BEHOUDEN (CLAUSULE)"
            confidence = ConfidenceLevel.MIDDEN.value
        elif result.category == ComplianceCategory.LIMITATION:
            advice_code = "BEHOUDEN (BEPERKING)"
            confidence = ConfidenceLevel.MIDDEN.value
        elif result.category == ComplianceCategory.NEUTRAL:
            advice_code = AdviceCode.HANDMATIG_CHECKEN.value
            confidence = ConfidenceLevel.LAAG.value
        else:
            advice_code = AdviceCode.HANDMATIG_CHECKEN.value
            confidence = ConfidenceLevel.LAAG.value
        
        # Build reason
        reason = result.advice
        if result.legal_subject:
            reason = f"[{result.legal_subject}] {reason}"
        if result.risk_score >= 7:
            reason = f"⚠️ HOOG RISICO ({result.risk_score}/10): {reason}"
        
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=advice_code,
            reason=reason,
            confidence=confidence,
            reference_article=result.cited_article or "-",
            category=f"LLM_COMPLIANCE_{result.category.value}",
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
    
    def _fallback_advice(
        self, 
        cluster: Cluster, 
        reason: str = "Automatische analyse niet beschikbaar"
    ) -> AnalysisAdvice:
        """Generate fallback advice when LLM fails."""
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason=f"{reason}. Handmatige beoordeling vereist.",
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
    
    def set_batch_size(self, batch_size: int) -> None:
        """
        Update the batch size for processing.
        
        Args:
            batch_size: New batch size
        """
        self.batch_size = batch_size
        self.batch_processor.batch_size = batch_size
        logger.info(f"Batch size updated to {batch_size}")
