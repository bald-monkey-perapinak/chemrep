import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PronunciationDictionary:
    """Custom pronunciation for chemistry terms."""
    
    def __init__(self):
        self.custom_pronunciations = {
            # Common chemistry terms with pronunciation guides
            "спирт": "спирт",
            "кислота": "кислота",
            "щелочь": "щёлочь",
            "катион": "катион",
            "анион": "анион",
            "оксид": "оксид",
            "гидроксид": "гидроксид",
            "хлорид": "хлорид",
            "сульфат": "сульфат",
            "нитрат": "нитрат",
            # Abbreviations
            "ИЮПАК": "и-ю-пак",
            "sp3": "эс-пе-три",
            "sp2": "эс-пе-два",
            "sp": "эс-пе",
            "ΔH": "дельта-аш",
            "ΔG": "дельта-джи",
            "ΔS": "дельта-эс",
        }
    
    def get_pronunciation(self, term: str) -> Optional[str]:
        """Get custom pronunciation for a term."""
        return self.custom_pronunciations.get(term.lower())
    
    def add_pronunciation(self, term: str, pronunciation: str) -> None:
        """Add custom pronunciation."""
        self.custom_pronunciations[term.lower()] = pronunciation
    
    def apply_pronunciations(self, text: str) -> str:
        """
        Replace terms with custom pronunciations in text.
        """
        result = text
        for term, pronunciation in self.custom_pronunciations.items():
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            result = pattern.sub(pronunciation, result)
        
        return result
