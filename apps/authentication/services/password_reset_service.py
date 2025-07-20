from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


class RedisPasswordResetService:
    """Redis-based password reset protection service."""

    def __init__(self):
        self.reset_settings = getattr(settings, "PASSWORD_RESET_SETTINGS", {})
        self.max_reset_requests = self.reset_settings.get("MAX_RESET_REQUESTS_PER_HOUR", 3)
        self.reset_attempt_limit = self.reset_settings.get("MAX_RESET_ATTEMPTS", 5)
        self.lockout_duration = self.reset_settings.get("LOCKOUT_DURATION_MINUTES", 20)

    def _get_reset_request_key(self, email: str) -> str:
        """Generate Redis key for reset request tracking."""
        if not email:
            raise ValueError("Email cannot be None or empty")
        return f"pwd_reset:requests:{email.lower()}"

    def _get_reset_attempt_key(self, email: str) -> str:
        """Generate Redis key for reset attempt tracking."""
        if not email:
            raise ValueError("Email cannot be None or empty")
        return f"pwd_reset:attempts:{email.lower()}"

    def _get_lockout_key(self, email: str) -> str:
        """Generate Redis key for lockout tracking."""
        if not email:
            raise ValueError("Email cannot be None or empty")
        return f"pwd_reset:lockout:{email.lower()}"

    def can_request_reset(self, email: str) -> tuple[bool, str]:
        """Check if user can request password reset."""
        if self.is_user_locked_out(email):
            remaining = self.get_lockout_remaining_time(email)
            return (
                False,
                f"Too many reset attempts. Please wait {remaining} minutes before trying again.",
            )

        # Check hourly request limit
        request_count = self.get_reset_request_count(email)
        if request_count >= self.max_reset_requests:
            return (
                False,
                f"Maximum {self.max_reset_requests} reset requests per hour exceeded. Please try"
                "again later.",
            )

        return True, "Reset request allowed"

    def track_reset_request(self, email: str):
        """Track a password reset request."""
        key = self._get_reset_request_key(email)
        current_count = cache.get(key, 0)
        cache.set(key, current_count + 1, timeout=3600)  # 1 hour TTL

    def can_attempt_reset(self, email: str) -> tuple[bool, str]:
        """Check if user can attempt password reset with token."""
        if self.is_user_locked_out(email):
            remaining = self.get_lockout_remaining_time(email)
            return (
                False,
                f"Account temporarily locked. Please wait {remaining} minutes before trying again.",
            )

        attempt_count = self.get_reset_attempt_count(email)
        if attempt_count >= self.reset_attempt_limit:
            self._lockout_user(email)
            return (
                False,
                f"Too many reset attempts. Account locked for {self.lockout_duration} minutes.",
            )

        return True, "Reset attempt allowed"

    def track_failed_reset_attempt(self, email: str):
        key = self._get_reset_attempt_key(email)
        current_count = cache.get(key, 0)
        cache.set(key, current_count + 1, timeout=3600)  # 1 hour TTL

    def clear_reset_tracking(self, email: str):
        """Clear all tracking for successful reset."""
        cache.delete(self._get_reset_request_key(email))
        cache.delete(self._get_reset_attempt_key(email))
        cache.delete(self._get_lockout_key(email))

    def get_reset_request_count(self, email: str) -> int:
        """Get current reset request count."""
        return cache.get(self._get_reset_request_key(email), 0)

    def get_reset_attempt_count(self, email: str) -> int:
        """Get current reset attempt count."""
        return cache.get(self._get_reset_attempt_key(email), 0)

    def is_user_locked_out(self, email: str) -> bool:
        """Check if user is locked out."""
        return cache.get(self._get_lockout_key(email)) is not None

    def get_lockout_remaining_time(self, email: str) -> int:
        """Get remaining lockout time in minutes."""
        lockout_time = cache.get(self._get_lockout_key(email))
        if not lockout_time:
            return 0

        try:
            lockout_start = datetime.fromisoformat(lockout_time)
            if lockout_start.tzinfo is None:
                lockout_start = timezone.make_aware(lockout_start)

            elapsed_minutes = (timezone.now() - lockout_start).total_seconds() / 60
            remaining = max(0, self.lockout_duration - elapsed_minutes)
            return int(remaining)
        except (ValueError, TypeError):
            return 0

    def _lockout_user(self, email: str):
        """Lock out user for configured duration."""
        cache.set(
            self._get_lockout_key(email),
            timezone.now().isoformat(),
            timeout=self.lockout_duration * 60,
        )


# Global instance
password_reset_service = RedisPasswordResetService()
