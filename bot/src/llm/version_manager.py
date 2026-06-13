import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMVersionManager:
    """Manage LLM API versions and detect behavior changes."""
    
    def __init__(self):
        self.current_model = None
        self.version_history = []
        self.quality_metrics = []
    
    def set_model(self, model_name: str, version: str = None) -> None:
        """Set current LLM model with version tracking."""
        self.current_model = {
            "name": model_name,
            "version": version,
            "set_at": datetime.utcnow().isoformat()
        }
        self.version_history.append(self.current_model)
        logger.info(f"LLM model set to {model_name} (version: {version})")
    
    def record_quality(self, response_quality: float) -> None:
        """Record response quality metric."""
        self.quality_metrics.append({
            "model": self.current_model["name"] if self.current_model else "unknown",
            "quality": response_quality,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Check for quality degradation
        if len(self.quality_metrics) >= 10:
            recent = self.quality_metrics[-10:]
            avg_quality = sum(m["quality"] for m in recent) / len(recent)
            
            if avg_quality < 0.6:
                logger.warning(f"LLM quality degradation detected: avg={avg_quality:.2f}")
                return True
        
        return False
    
    def get_model_info(self) -> dict:
        """Get current model information."""
        return self.current_model or {"name": "unknown", "version": None}
