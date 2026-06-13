import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from src.models.session import LessonSession, SessionStatus

logger = logging.getLogger(__name__)


class LessonCheckpoint:
    """Save and restore lesson progress for crash recovery."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_checkpoint(self, lesson_id: str, step: int, state: dict) -> None:
        """
        Save lesson progress to database.
        Called periodically during lesson execution.
        """
        try:
            session = self.db.query(LessonSession).filter(
                LessonSession.lesson_id == lesson_id
            ).first()
            
            if session:
                session.checkpoint_step = step
                session.checkpoint_state = json.dumps(state)
                session.checkpoint_time = datetime.now(timezone.utc)
                self.db.commit()
                logger.info(f"Checkpoint saved for lesson {lesson_id} at step {step}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def restore_checkpoint(self, lesson_id: str) -> Optional[dict]:
        """
        Restore lesson from last checkpoint.
        Returns None if no checkpoint exists.
        """
        try:
            session = self.db.query(LessonSession).filter(
                LessonSession.lesson_id == lesson_id
            ).first()
            
            if session and session.checkpoint_state:
                return {
                    "step": session.checkpoint_step,
                    "state": json.loads(session.checkpoint_state),
                    "time": session.checkpoint_time.isoformat()
                }
        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {e}")
        
        return None
    
    def has_checkpoint(self, lesson_id: str) -> bool:
        """Check if a checkpoint exists for this lesson."""
        session = self.db.query(LessonSession).filter(
            LessonSession.lesson_id == lesson_id
        ).first()
        
        return session is not None and session.checkpoint_state is not None
