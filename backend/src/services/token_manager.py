import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class TokenManager:
    """Manage JWT tokens with rotation and revocation."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_ttl = timedelta(minutes=15)
        self.refresh_token_ttl = timedelta(days=7)
        self.revoked_tokens = set()

    def create_access_token(self, user_id: str, payload: dict = None) -> str:
        """Create short-lived access token."""
        now = datetime.now(timezone.utc)
        token_payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + self.access_token_ttl,
            "jti": str(uuid4()),  # Unique token ID
            "type": "access"
        }
        if payload:
            token_payload.update(payload)

        return jwt.encode(token_payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Create long-lived refresh token."""
        now = datetime.now(timezone.utc)
        token_payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + self.refresh_token_ttl,
            "jti": str(uuid4()),
            "type": "refresh"
        }

        return jwt.encode(token_payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode token. Returns None if invalid or revoked."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check if token is revoked
            if payload.get("jti") in self.revoked_tokens:
                logger.warning("Revoked token used")
                return None

            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def revoke_token(self, token: str) -> bool:
        """Revoke a token (add to revocation list)."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm],
                               options={"verify_exp": False})
            jti = payload.get("jti")
            if jti:
                self.revoked_tokens.add(jti)
                logger.info(f"Token revoked: {jti}")
                return True
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")

        return False

    def rotate_tokens(self, refresh_token: str) -> Optional[dict]:
        """
        Rotate tokens: validate refresh token, issue new pair.
        Returns new tokens or None if refresh token invalid.
        """
        payload = self.verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        user_id = payload["sub"]

        # Revoke old refresh token
        self.revoke_token(refresh_token)

        # Issue new pair
        return {
            "access_token": self.create_access_token(user_id),
            "refresh_token": self.create_refresh_token(user_id)
        }
