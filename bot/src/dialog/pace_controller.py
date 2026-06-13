import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class PaceLevel(Enum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class PaceController:
    """Adapt teaching pace based on student understanding."""
    
    def __init__(self):
        self.current_pace = PaceLevel.NORMAL
        self.response_times = []
        self.correct_answers = 0
        self.total_questions = 0
        self.consecutive_correct = 0
        self.consecutive_wrong = 0
    
    def record_response(self, response_time: float, is_correct: bool) -> None:
        """Record student response for pace adaptation."""
        self.response_times.append(response_time)
        self.total_questions += 1
        
        if is_correct:
            self.correct_answers += 1
            self.consecutive_correct += 1
            self.consecutive_wrong = 0
        else:
            self.consecutive_correct = 0
            self.consecutive_wrong += 1
        
        self._adapt_pace()
    
    def _adapt_pace(self) -> None:
        """Adapt pace based on recent performance."""
        # Speed up if student is doing well
        if self.consecutive_correct >= 3:
            if self.current_pace == PaceLevel.SLOW:
                self.current_pace = PaceLevel.NORMAL
            elif self.current_pace == PaceLevel.NORMAL:
                self.current_pace = PaceLevel.FAST
            logger.info(f"Pace increased to {self.current_pace.value}")
        
        # Slow down if student is struggling
        elif self.consecutive_wrong >= 2:
            if self.current_pace == PaceLevel.FAST:
                self.current_pace = PaceLevel.NORMAL
            elif self.current_pace == PaceLevel.NORMAL:
                self.current_pace = PaceLevel.SLOW
            logger.info(f"Pace decreased to {self.current_pace.value}")
    
    def get_pace_multiplier(self) -> float:
        """Get pace multiplier for timing adjustments."""
        multipliers = {
            PaceLevel.SLOW: 1.5,    # 50% slower
            PaceLevel.NORMAL: 1.0,
            PaceLevel.FAST: 0.7     # 30% faster
        }
        return multipliers[self.current_pace]
    
    def should_add_extra_explanation(self) -> bool:
        """Determine if extra explanation is needed."""
        return self.current_pace == PaceLevel.SLOW or self.consecutive_wrong >= 2
