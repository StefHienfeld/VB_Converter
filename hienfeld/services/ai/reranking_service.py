# hienfeld/services/ai/reranking_service.py
"""
Cross-Encoder Re-Ranking Service.

Implements re-ranking of retrieval results using either:
1. Cross-encoder models (fast, ~50ms per comparison)
2. LLM-based ranking (slower, more accurate)

Cross-encoders jointly process query+document pairs, catching
paraphrases and semantic equivalences that bi-encoders miss.

Research shows +15-25% precision improvement on top-k results.
"""
from typing import List, Dict, Any, Optional, Tuple
import re

from ...logging_config import get_logger

logger = get_logger('reranking_service')


class ReRankingService:
    """
    Service for re-ranking retrieval results.

    Supports two modes:
    1. Cross-encoder mode: Uses sentence-transformers CrossEncoder
    2. LLM mode: Uses chat completion for ranking

    The service falls back gracefully if models aren't available.
    """

    # Default settings
    DEFAULT_TOP_K = 10
    DEFAULT_RERANK_TOP_K = 5

    # Cross-encoder model for Dutch/multilingual
    CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    def __init__(
        self,
        llm_client: Any = None,
        model_name: str = "gpt-4",
        use_cross_encoder: bool = True,
        cache_embeddings: bool = True
    ):
        """
        Initialize re-ranking service.

        Args:
            llm_client: Optional LLM client for LLM-based ranking
            model_name: Model name for LLM-based ranking
            use_cross_encoder: Try to use cross-encoder (faster)
            cache_embeddings: Cache cross-encoder for reuse
        """
        self.llm_client = llm_client
        self.model_name = model_name
        self.use_cross_encoder = use_cross_encoder
        self._cross_encoder = None
        self._cross_encoder_loaded = False
        self._cross_encoder_available = use_cross_encoder

        # Try to load cross-encoder if requested
        if use_cross_encoder:
            self._try_load_cross_encoder()

    def _try_load_cross_encoder(self) -> bool:
        """
        Try to load the cross-encoder model.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._cross_encoder_loaded:
            return self._cross_encoder is not None

        self._cross_encoder_loaded = True

        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading cross-encoder: {self.CROSS_ENCODER_MODEL}")
            self._cross_encoder = CrossEncoder(self.CROSS_ENCODER_MODEL)
            logger.info("Cross-encoder loaded successfully")
            return True
        except ImportError:
            logger.warning("sentence-transformers not installed, cross-encoder unavailable")
            self._cross_encoder_available = False
            return False
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}")
            self._cross_encoder_available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if any re-ranking method is available."""
        return self._cross_encoder is not None or self.llm_client is not None

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = DEFAULT_RERANK_TOP_K,
        text_key: str = "text"
    ) -> List[Dict[str, Any]]:
        """
        Re-rank results using the best available method.

        Automatically selects:
        1. Cross-encoder if available (faster, ~50ms)
        2. LLM-based if cross-encoder unavailable (slower, more accurate)
        3. Returns original order if neither available

        Args:
            query: The search query
            results: List of result dicts with text content
            top_k: Number of top results to return
            text_key: Key in result dict containing the text

        Returns:
            Re-ranked list of results (top_k items)
        """
        if not results:
            return []

        if len(results) <= 1:
            return results[:top_k]

        # Limit input to reasonable size
        candidates = results[:min(len(results), self.DEFAULT_TOP_K)]

        # Try cross-encoder first (faster)
        if self._cross_encoder is not None:
            try:
                return self._rerank_cross_encoder(query, candidates, top_k, text_key)
            except Exception as e:
                logger.warning(f"Cross-encoder rerank failed: {e}, falling back to LLM")

        # Try LLM-based ranking
        if self.llm_client is not None:
            try:
                return self._rerank_llm(query, candidates, top_k, text_key)
            except Exception as e:
                logger.warning(f"LLM rerank failed: {e}, returning original order")

        # Fallback: return original order
        logger.debug("No reranking available, returning original order")
        return candidates[:top_k]

    def _rerank_cross_encoder(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
        text_key: str
    ) -> List[Dict[str, Any]]:
        """
        Re-rank using cross-encoder model.

        Cross-encoders process query-document pairs jointly,
        giving more accurate relevance scores than bi-encoders.

        Args:
            query: Search query
            results: Candidate results
            top_k: Number to return
            text_key: Key containing text in results

        Returns:
            Re-ranked results
        """
        if self._cross_encoder is None:
            raise ValueError("Cross-encoder not loaded")

        # Create query-document pairs
        pairs = []
        for r in results:
            text = self._extract_text(r, text_key)
            if text:
                pairs.append([query, text])

        if not pairs:
            return results[:top_k]

        # Get cross-encoder scores
        logger.debug(f"Cross-encoder scoring {len(pairs)} pairs")
        scores = self._cross_encoder.predict(pairs)

        # Combine with original results and sort
        scored_results = list(zip(results[:len(scores)], scores))
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Extract top_k results
        reranked = [r for r, _ in scored_results[:top_k]]

        logger.debug(f"Cross-encoder reranked {len(results)} -> {len(reranked)} results")
        return reranked

    def _rerank_llm(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int,
        text_key: str
    ) -> List[Dict[str, Any]]:
        """
        Re-rank using LLM-based comparison.

        Asks the LLM to rank documents by relevance to the query.
        Slower but can be more accurate for nuanced queries.

        Args:
            query: Search query
            results: Candidate results
            top_k: Number to return
            text_key: Key containing text in results

        Returns:
            Re-ranked results
        """
        if self.llm_client is None:
            raise ValueError("LLM client not configured")

        # Build prompt with numbered documents
        docs_text = []
        valid_results = []
        for i, r in enumerate(results):
            text = self._extract_text(r, text_key)
            if text:
                # Truncate for prompt
                truncated = text[:300] + "..." if len(text) > 300 else text
                docs_text.append(f"{i+1}. {truncated}")
                valid_results.append((i, r))

        if not docs_text:
            return results[:top_k]

        prompt = f"""Rangschik de volgende {len(docs_text)} teksten op relevantie voor de zoekvraag.

Zoekvraag: "{query}"

Teksten:
{chr(10).join(docs_text)}

Geef ALLEEN de nummers terug in volgorde van meest naar minst relevant.
Formaat: [2, 1, 3, 5, 4] (voorbeeld)

Ranking:"""

        messages = [
            {"role": "system", "content": "Je rankt documenten op relevantie. Geef alleen de ranking als JSON array."},
            {"role": "user", "content": prompt}
        ]

        try:
            # Call LLM
            response = self._call_llm(messages)

            # Parse ranking from response
            ranking = self._parse_ranking(response, len(valid_results))

            # Reorder results according to ranking
            reranked = []
            for rank_idx in ranking[:top_k]:
                if 0 <= rank_idx < len(valid_results):
                    _, result = valid_results[rank_idx]
                    reranked.append(result)

            # Fill remaining slots if ranking incomplete
            if len(reranked) < top_k:
                used_indices = set(ranking[:top_k])
                for i, r in valid_results:
                    if i not in used_indices and len(reranked) < top_k:
                        reranked.append(r)

            logger.debug(f"LLM reranked {len(results)} -> {len(reranked)} results")
            return reranked

        except Exception as e:
            logger.error(f"LLM ranking failed: {e}")
            raise

    def _extract_text(self, result: Dict[str, Any], text_key: str) -> str:
        """
        Extract text from a result dict.

        Handles nested structures like metadata.raw_text.

        Args:
            result: Result dictionary
            text_key: Key to look for

        Returns:
            Extracted text or empty string
        """
        # Direct key
        if text_key in result:
            return str(result[text_key])

        # Try metadata.text_key
        if 'metadata' in result and isinstance(result['metadata'], dict):
            if text_key in result['metadata']:
                return str(result['metadata'][text_key])
            # Common variations
            for key in ['raw_text', 'text', 'content', 'chunk_text']:
                if key in result['metadata']:
                    return str(result['metadata'][key])

        # Try document key
        if 'document' in result:
            return str(result['document'])

        return ""

    def _call_llm(self, messages: List[dict]) -> str:
        """
        Call the LLM with messages.

        Args:
            messages: Chat messages

        Returns:
            Response text
        """
        if hasattr(self.llm_client, 'chat') and hasattr(self.llm_client.chat, 'completions'):
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0
            )
            return response.choices[0].message.content

        if callable(self.llm_client):
            prompt = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
            return self.llm_client(prompt)

        raise ValueError("Unsupported LLM client type")

    def _parse_ranking(self, response: str, num_items: int) -> List[int]:
        """
        Parse a ranking list from LLM response.

        Handles various formats:
        - [1, 2, 3, 4, 5]
        - 1, 2, 3, 4, 5
        - 1. 2. 3. 4. 5.

        Args:
            response: LLM response text
            num_items: Expected number of items

        Returns:
            List of 0-indexed positions
        """
        # Try JSON array first
        try:
            import json
            # Find array in response
            match = re.search(r'\[[\d,\s]+\]', response)
            if match:
                ranking = json.loads(match.group())
                # Convert to 0-indexed
                return [int(x) - 1 for x in ranking if isinstance(x, (int, float))]
        except (json.JSONDecodeError, ValueError):
            pass

        # Try comma-separated numbers
        numbers = re.findall(r'\d+', response)
        if numbers:
            # Convert to 0-indexed
            ranking = [int(n) - 1 for n in numbers if 0 < int(n) <= num_items]
            return ranking

        # Fallback: return original order
        return list(range(num_items))

    def score_pair(self, query: str, document: str) -> float:
        """
        Score a single query-document pair.

        Useful for comparing specific documents against a query.

        Args:
            query: Search query
            document: Document text

        Returns:
            Relevance score (higher is better)
        """
        if self._cross_encoder is None:
            # Fallback: return 0.5 (neutral)
            return 0.5

        try:
            score = self._cross_encoder.predict([[query, document]])[0]
            return float(score)
        except Exception as e:
            logger.warning(f"Scoring failed: {e}")
            return 0.5


def create_reranking_service(
    llm_client: Any = None,
    model_name: str = "gpt-4",
    prefer_cross_encoder: bool = True
) -> ReRankingService:
    """
    Factory function to create a ReRankingService.

    Args:
        llm_client: Optional LLM client for fallback
        model_name: Model name for LLM ranking
        prefer_cross_encoder: Try cross-encoder first

    Returns:
        Configured ReRankingService
    """
    return ReRankingService(
        llm_client=llm_client,
        model_name=model_name,
        use_cross_encoder=prefer_cross_encoder
    )
