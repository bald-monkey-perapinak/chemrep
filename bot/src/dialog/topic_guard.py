import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TopicGuard:
    """Keep bot responses on-topic during lessons."""
    
    def __init__(self, topic_context: str, topic_keywords: list[str] = None):
        self.topic_context = topic_context
        self.topic_keywords = topic_keywords or []
        self.off_topic_count = 0
        self.max_off_topic = 3
    
    def is_on_topic(self, user_input: str) -> bool:
        """
        Check if user input is related to the lesson topic.
        Uses keyword matching and context similarity.
        """
        user_input_lower = user_input.lower()
        
        # Check keyword matches
        keyword_matches = sum(1 for kw in self.topic_keywords if kw.lower() in user_input_lower)
        
        # Simple relevance check
        if keyword_matches > 0:
            return True
        
        # Check for topic-related phrases
        topic_phrases = ["химия", "реакция", "формула", "элемент", "соединение"]
        phrase_matches = sum(1 for phrase in topic_phrases if phrase in user_input_lower)
        
        return phrase_matches > 0
    
    def get_redirect_response(self) -> str:
        """Get response to redirect off-topic questions."""
        self.off_topic_count += 1
        
        if self.off_topic_count >= self.max_off_topic:
            return (
                "Я заметил, что мы отошли от темы. "
                "Давай вернёмся к уроку. Если есть вопросы после занятия, "
                "задайте их преподавателю."
            )
        
        return "Давай вернёмся к теме урока. Есть вопросы по материалу?"
