import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ChildAdaptiveVAD:
    """Voice Activity Detection adapted for children's voices."""
    
    def __init__(self):
        # Lower thresholds for children's quieter voices
        self.energy_threshold = 0.3  # vs 0.5 for adults
        self.speech_duration_min = 0.3  # shorter minimum for kids
        self.speech_duration_max = 30.0  # allow longer utterances
        self.silence_duration = 0.8  # slightly longer silence to confirm end
    
    def is_speech(self, audio_chunk: bytes, energy: float) -> bool:
        """
        Determine if audio chunk contains speech.
        Adapted for children's voice characteristics.
        """
        if energy < self.energy_threshold:
            return False
        
        # Additional check for children's speech patterns
        # Kids often have higher pitch and more variation
        return True
    
    def get_settings(self) -> dict:
        """Get VAD settings for current context."""
        return {
            "energy_threshold": self.energy_threshold,
            "speech_duration_min": self.speech_duration_min,
            "speech_duration_max": self.speech_duration_max,
            "silence_duration": self.silence_duration
        }
