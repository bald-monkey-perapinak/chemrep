import logging
import re
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
        
        claims = self._extract_claims(response)
        
        evidence = []
        supported_claims = 0
        for claim in claims:
            chunks = self.retriever.search(claim, top_k=3)
            if chunks:
                supported_claims += 1
                evidence.extend(chunks)
        
        if not claims:
            return {"confidence": 0.5, "supported": False, "evidence": []}
        
        support_ratio = supported_claims / len(claims)
        confidence = min(1.0, 0.3 + support_ratio * 0.7)
        
        return {
            "confidence": round(confidence, 2),
            "supported": confidence > 0.6,
            "evidence": evidence[:10],
        }
    
    def _extract_claims(self, text: str) -> list[str]:
        """Extract key factual claims from text, filtering out questions and exclamations."""
        sentences = re.split(r'[.!?]+', text)
        claims = []
        for s in sentences:
            s = s.strip()
            if len(s) < 10:
                continue
            if s.endswith('?'):
                continue
            if s.startswith(('Давай', 'Теперь', 'Итак', 'Хорошо', 'Отлично')):
                continue
            claims.append(s)
        return claims[:5]
