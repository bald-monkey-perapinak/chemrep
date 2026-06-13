import logging
import time
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class VCSMonitor:
    """Monitor VCS platform for UI changes and failures."""

    def __init__(self):
        self.failure_count = 0
        self.last_success = datetime.utcnow()
        self.consecutive_failures = 0
        self.failure_threshold = 3

    def record_success(self) -> None:
        """Record successful VCS operation."""
        self.failure_count = 0
        self.consecutive_failures = 0
        self.last_success = datetime.utcnow()

    def record_failure(self, error: str) -> bool:
        """
        Record VCS failure.
        Returns True if alert should be sent.
        """
        self.failure_count += 1
        self.consecutive_failures += 1

        logger.warning(f"VCS failure: {error} (consecutive: {self.consecutive_failures})")

        # Alert if too many consecutive failures
        if self.consecutive_failures >= self.failure_threshold:
            logger.error(f"VCS alert: {self.consecutive_failures} consecutive failures")
            return True

        return False

    def get_status(self) -> dict:
        """Get current VCS monitoring status."""
        return {
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "last_success": self.last_success.isoformat(),
            "healthy": self.consecutive_failures < self.failure_threshold
        }
