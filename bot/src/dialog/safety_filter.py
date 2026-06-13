import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SafetyFilter:
    """Filter inappropriate content from bot responses."""
    
    def __init__(self):
        # Basic profanity list (expand as needed)
        self.profanity_patterns = [
            r'\b(блин|черт|дурак|идиот)\b',
            # Add more patterns as needed
        ]
        self.educational_disclaimers = [
            "Это учебный бот, а не настоящий преподаватель.",
            "Пожалуйста, перепроверяйте важную информацию.",
        ]
    
    def check_content(self, text: str) -> dict:
        """
        Check content for safety issues.
        Returns filtered text and any issues found.
        """
        issues = []
        filtered_text = text
        
        # Check for profanity
        for pattern in self.profanity_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Profanity detected: {pattern}")
                filtered_text = re.sub(pattern, '[...]', filtered_text, flags=re.IGNORECASE)
        
        # Check for inappropriate content
        inappropriate = self._check_inappropriate(text)
        if inappropriate:
            issues.extend(inappropriate)
        
        return {
            "safe": len(issues) == 0,
            "issues": issues,
            "filtered_text": filtered_text
        }
    
    def _check_inappropriate(self, text: str) -> list[str]:
        """Check for other inappropriate content."""
        issues = []
        
        # Check for personal attacks
        attack_patterns = [r'ты\s+некомпетентен', r'ты\s+не\s+понимаешь']
        for pattern in attack_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("Potential personal attack detected")
        
        return issues
    
    def add_disclaimer(self, text: str) -> str:
        """Add educational disclaimer to response."""
        return f"{text}\n\n[Обратите внимание: это ответ учебного бота]"
