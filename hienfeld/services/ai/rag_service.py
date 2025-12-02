# hienfeld/services/ai/rag_service.py
"""
RAG (Retrieval Augmented Generation) service for policy document search.
"""
from typing import List, Optional

from ...domain.policy_document import PolicyDocumentSection
from ...domain.clause import Clause
from .embeddings_service import EmbeddingsService
from .vector_store import VectorStore
from ...logging_config import get_logger

logger = get_logger('rag_service')


class RAGService:
    """
    Retrieval Augmented Generation service.
    
    Combines embedding-based retrieval with policy document sections
    to find relevant context for clause analysis.
    """
    
    def __init__(
        self, 
        embeddings_service: EmbeddingsService, 
        vector_store: VectorStore
    ):
        """
        Initialize RAG service.
        
        Args:
            embeddings_service: Service for generating embeddings
            vector_store: Store for vector similarity search
        """
        self.embeddings_service = embeddings_service
        self.vector_store = vector_store
        self._indexed = False
    
    def index_policy_sections(
        self, 
        sections: List[PolicyDocumentSection]
    ) -> None:
        """
        Index policy document sections for retrieval.
        
        Args:
            sections: List of policy sections to index
        """
        if not sections:
            logger.warning("No sections to index")
            return
        
        logger.info(f"Indexing {len(sections)} policy sections")
        
        # Extract texts and metadata
        texts = [s.simplified_text for s in sections]
        ids = [s.id for s in sections]
        metadata = [
            {
                'article_id': s.id,
                'title': s.title,
                'page': s.page_number,
                'document_id': s.document_id,
                'raw_text': s.raw_text[:500]  # Store truncated text
            }
            for s in sections
        ]
        
        # Generate embeddings
        vectors = self.embeddings_service.embed_texts(texts)
        
        # Clear existing index and add new documents
        self.vector_store.clear()
        self.vector_store.add_documents(ids, vectors, metadata)
        
        self._indexed = True
        logger.info("Policy sections indexed successfully")
    
    def retrieve_relevant_sections(
        self, 
        clause_text: str, 
        top_k: int = 3
    ) -> List[dict]:
        """
        Find policy sections relevant to a clause.
        
        Args:
            clause_text: Clause text to search for
            top_k: Number of results to return
            
        Returns:
            List of relevant section results with id, score, metadata
        """
        if not self._indexed:
            logger.warning("No documents indexed yet")
            return []
        
        # Generate query embedding
        query_vector = self.embeddings_service.embed_single(clause_text)
        
        # Search
        results = self.vector_store.similarity_search(query_vector, k=top_k)
        
        logger.debug(f"Found {len(results)} relevant sections for query")
        return results
    
    def retrieve_for_clause(
        self, 
        clause: Clause, 
        top_k: int = 3
    ) -> List[dict]:
        """
        Find policy sections relevant to a Clause object.
        
        Args:
            clause: Clause to search for
            top_k: Number of results
            
        Returns:
            List of relevant section results
        """
        # Use simplified text for more consistent matching
        return self.retrieve_relevant_sections(clause.simplified_text, top_k)
    
    def get_context_for_analysis(
        self, 
        clause_text: str, 
        top_k: int = 3,
        min_score: float = 0.5
    ) -> str:
        """
        Get formatted context text for LLM analysis.
        
        Args:
            clause_text: Clause to analyze
            top_k: Number of sections to include
            min_score: Minimum similarity score
            
        Returns:
            Formatted context string
        """
        results = self.retrieve_relevant_sections(clause_text, top_k)
        
        # Filter by score
        relevant = [r for r in results if r['score'] >= min_score]
        
        if not relevant:
            return "Geen relevante voorwaarden gevonden."
        
        # Format context
        context_parts = []
        for r in relevant:
            meta = r['metadata']
            text = meta.get('raw_text', '')
            article = meta.get('article_id', 'Onbekend')
            title = meta.get('title', '')
            
            part = f"### {article}"
            if title:
                part += f" - {title}"
            part += f"\n{text}\n"
            context_parts.append(part)
        
        return "\n".join(context_parts)
    
    def is_ready(self) -> bool:
        """Check if RAG service is ready for queries."""
        return self._indexed
    
    def clear(self) -> None:
        """Clear the index."""
        self.vector_store.clear()
        self._indexed = False

