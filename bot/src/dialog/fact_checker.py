import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FactChecker:
    """Check LLM responses against knowledge base for accuracy."""
    
    def __init__(self, retriever=None):
        self.retriever = retriever
    
    def check_response(self, response: str, context: str = "") -> dict:
        """
        Check if response is supported by knowledge base.
        Returns confidence score and supporting evidence.
        """
        if not self.retriever:
            return {"confidence": 0.5, "supported": False, "evidence": []}
        
        # Extract key claims from response
        claims = self._extract_claims(response)
        
        # Search knowledge base for supporting evidence
        evidence = []
        for claim in claims:
            chunks = self.retriever.search(claim, top_k=3)
            evidence.extend(chunks)
        
        # Calculate confidence based on evidence coverage
        confidence = min(1.0, len(evidence) * 0.2) if evidence else 0.3
        
        return {
            "confidence": confidence,
            "supported": confidence > 0.6,
            "evidence": evidence
        }
    
    def _extract_claims(self, text: str) -> list[str]:
        """Extract key factual claims from text."""
        # Simple sentence splitting for now
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        return sentences[:5]  # Limit to top 5 claims
