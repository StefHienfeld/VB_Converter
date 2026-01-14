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
from ...prompts.reflection_prompt import ReflectionPrompt, ReflectionResult
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
                top_k=20
            )
        elif policy_sections:
            context = self._format_sections_as_context(policy_sections[:20])
        
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

    def verify_analysis(
        self,
        clause_text: str,
        context: str,
        initial_advice: AnalysisAdvice
    ) -> ReflectionResult:
        """
        Verify an initial analysis using reflection (self-verification).

        This implements the dual-pass verification architecture where
        the LLM critically reviews its own initial analysis.

        Args:
            clause_text: Original clause text
            context: Relevant policy conditions
            initial_advice: The initial analysis result to verify

        Returns:
            ReflectionResult with verification outcome
        """
        if self.client is None:
            return ReflectionResult.fallback("No LLM client configured")

        try:
            messages = ReflectionPrompt.build_messages(
                clause_text=clause_text,
                context=context,
                initial_conclusion=initial_advice.advice_code,
                initial_reason=initial_advice.reason,
                initial_confidence=str(initial_advice.confidence),
                initial_article=initial_advice.reference_article or "-"
            )
            response = self._call_llm_chat(messages)
            return ReflectionResult.from_json(response, raw_response=response)
        except Exception as e:
            logger.error(f"Reflection verification failed: {e}")
            return ReflectionResult.fallback(str(e))

    def analyze_with_reflection(
        self,
        cluster: Cluster,
        policy_sections: Optional[List[PolicyDocumentSection]] = None,
        reflection_threshold: float = 0.7
    ) -> AnalysisAdvice:
        """
        Analyze a cluster with automatic reflection/self-verification.

        Implements a dual-pass architecture:
        1. First pass: Standard analysis (sanering + compliance)
        2. Second pass: Reflection/verification of the initial result
        3. Decision: Accept, revise, or flag for manual check

        Args:
            cluster: Cluster to analyze
            policy_sections: Optional list of relevant policy sections
            reflection_threshold: Minimum confidence to skip reflection (default 0.7)

        Returns:
            AnalysisAdvice (potentially revised based on reflection)
        """
        if self.client is None:
            logger.warning("No LLM client configured")
            return self._fallback_advice(cluster)

        # Get context for analysis
        context = ""
        if self.rag_service and self.rag_service.is_ready():
            context = self.rag_service.get_context_for_analysis(
                cluster.original_text,
                top_k=20
            )
        elif policy_sections:
            context = self._format_sections_as_context(policy_sections[:20])

        if not context:
            return self._fallback_advice(cluster, reason="Geen voorwaarden context beschikbaar")

        # PASS 1: Initial analysis
        initial_advice = self.analyze_cluster_with_context(cluster, policy_sections)

        # Skip reflection if initial confidence is very high and not high-risk
        is_high_risk = (
            initial_advice.advice_code in ["⚠️ CONFLICT", "BEHOUDEN (CLAUSULE)"] or
            "HOOG RISICO" in initial_advice.reason
        )

        # Parse confidence from string if needed
        try:
            confidence_value = float(initial_advice.confidence) if isinstance(initial_advice.confidence, (int, float)) else 0.5
        except (ValueError, TypeError):
            confidence_value = 0.5

        if confidence_value >= reflection_threshold and not is_high_risk:
            logger.debug(f"Skipping reflection: confidence {confidence_value} >= {reflection_threshold}")
            return initial_advice

        # PASS 2: Reflection/verification
        logger.info(f"Running reflection for cluster {cluster.id}")
        reflection = self.verify_analysis(
            clause_text=cluster.original_text,
            context=context,
            initial_advice=initial_advice
        )

        # Decision based on reflection
        if reflection.recommendation == "ACCEPT" and reflection.agrees_with_initial:
            # Reflection confirms initial analysis
            logger.debug("Reflection confirms initial analysis")
            return initial_advice

        elif reflection.recommendation == "REVISE" and reflection.revised_conclusion:
            # Reflection suggests revision
            logger.info(f"Reflection suggests revision: {reflection.revised_conclusion}")
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"[HERZIEN] {reflection.revised_conclusion}. Origineel: {initial_advice.reason}",
                confidence=ConfidenceLevel.MIDDEN.value,
                reference_article=initial_advice.reference_article,
                category="REFLECTION_REVISED",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )

        else:
            # Reflection uncertain or recommends manual check
            logger.info("Reflection recommends manual check")
            issues = reflection.issues_found or "Onzekerheid in analyse"
            return AnalysisAdvice(
                cluster_id=cluster.id,
                advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
                reason=f"[REFLECTIE] {issues}. Origineel: {initial_advice.reason}",
                confidence=ConfidenceLevel.LAAG.value,
                reference_article=initial_advice.reference_article,
                category="REFLECTION_MANUAL",
                cluster_name=cluster.name,
                frequency=cluster.frequency
            )
    
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
    
    def _call_llm_chat(self, messages: List[dict], force_json: bool = True) -> str:
        """
        Call LLM with chat messages format.

        Args:
            messages: List of message dicts with 'role' and 'content'
            force_json: If True, request JSON output format (reduces parsing errors)

        Returns:
            Response text
        """
        # OpenAI-style client
        if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
            kwargs = {
                'model': self.model_name,
                'messages': messages,
                'temperature': self.temperature
            }

            # Add JSON mode if supported and requested
            if force_json:
                try:
                    kwargs['response_format'] = {"type": "json_object"}
                except Exception:
                    # Some models/providers don't support response_format
                    logger.debug("JSON mode not supported, using standard response")

            response = self.client.chat.completions.create(**kwargs)
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
    
    def intelligent_split(self, text: str) -> List[str]:
        """
        Intelligently split a text into semantically separate clauses using LLM.
        
        This method splits text WITHOUT changing any words - it only cuts the text
        at logical boundaries between separate legal provisions.
        
        Args:
            text: Text to split
            
        Returns:
            List of text segments (sub-clauses)
        """
        if self.client is None:
            logger.warning("No LLM client configured, returning original text as single segment")
            return [text]
        
        if not text or len(text.strip()) == 0:
            return [text]
        
        try:
            # Build prompt for splitting
            prompt = self._build_split_prompt(text)
            messages = [
                {
                    "role": "system",
                    "content": """Je bent een tekst-editor voor juridische documenten. 
Je taak is om lange teksten op te knippen in semantisch losstaande bepalingen.

BELANGRIJK: Verander GEEN ENKEL WOORD. Knip alleen de tekst op logische punten.
Je output moet een JSON array zijn met strings, waarbij elke string een deel van de originele tekst is."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = self._call_llm_chat(messages)
            
            # Parse JSON response
            import json
            # Try to extract JSON from response (might have markdown code blocks)
            response_clean = response.strip()
            if response_clean.startswith("```"):
                # Remove markdown code blocks
                response_clean = response_clean.split("```")[1]
                if response_clean.startswith("json"):
                    response_clean = response_clean[4:]
                response_clean = response_clean.strip()
            
            segments = json.loads(response_clean)
            
            # Validate that segments are strings and non-empty
            segments = [s.strip() for s in segments if isinstance(s, str) and s.strip()]
            
            if len(segments) == 0:
                logger.warning("LLM returned empty segments, using original text")
                return [text]
            
            logger.info(f"LLM split text into {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"LLM split failed: {e}")
            # Fallback: return original text as single segment
            return [text]
    
    def _build_split_prompt(self, text: str) -> str:
        """
        Build the prompt for intelligent text splitting.
        
        Args:
            text: Text to split
            
        Returns:
            Prompt string
        """
        return f"""Splits de volgende tekst in semantisch losstaande bepalingen.

REGELS:
1. Verander GEEN ENKEL WOORD - knip alleen op logische punten
2. Elke segment moet een complete, zelfstandige bepaling zijn
3. Behoud alle originele tekst - niets weglaten of toevoegen
4. Geef een JSON array terug met strings

Tekst om te splitsen:
---
{text}
---

Geef alleen de JSON array terug, zonder extra uitleg. Bijvoorbeeld:
["Eerste bepaling tekst...", "Tweede bepaling tekst...", "Derde bepaling tekst..."]"""