import json
import random
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()


class RedisOTPService:
    """Redis-based OTP service with automatic expiry and rate limiting."""

    def __init__(self):
        self.otp_settings = getattr(settings, "OTP_SETTINGS", {})
        self.expiry_minutes = self.otp_settings.get("EXPIRY_MINUTES", 5)
        self.max_resend_count = self.otp_settings.get("MAX_RESEND_COUNT", 3)
        self.resend_cooldown = self.otp_settings.get("RESEND_COOLDOWN_SECONDS", 60)
        self.lockout_duration = self.otp_settings.get("LOCKOUT_DURATION_MINUTES", 20)
        self.otp_length = self.otp_settings.get("OTP_LENGTH", 6)
        self.max_failed_attempts = self.otp_settings.get("MAX_FAILED_ATTEMPTS", 5)
        self.failed_attempts_window = self.otp_settings.get("FAILED_ATTEMPTS_WINDOW_MINUTES", 10)

    def _get_otp_key(self, user_id: int) -> str:
        """Generate Redis key for OTP storage."""
        return f"otp:user:{user_id}"

    def _get_lockout_key(self, user_id: int) -> str:
        """Generate Redis key for lockout storage."""
        return f"otp:lockout:user:{user_id}"

    def _get_resend_key(self, user_id: int) -> str:
        """Generate Redis key for resend tracking."""
        return f"otp:resend:user:{user_id}"

    def _get_failed_attempts_key(self, user_id: int) -> str:
        """Generate Redis key for failed attempts tracking."""
        return f"otp:failed_attempts:user:{user_id}"

    def track_failed_attempt(self, user_id: int):
        """
        Track failed OTP verification attempt for a user.
        Locks user if max attempts are exceeded.
        """
        key = self._get_failed_attempts_key(user_id)

        # Get current count or initialize
        attempts = cache.get(key, 0)
        new_attempts = attempts + 1

        # Update count with window expiry
        cache.set(key, new_attempts, timeout=self.failed_attempts_window * 60)

        # Lock user if max attempts reached
        if new_attempts >= self.max_failed_attempts:
            self._lockout_user(user_id)

    def reset_failed_attempts(self, user_id: int):
        """Reset failed attempts counter for user."""
        cache.delete(self._get_failed_attempts_key(user_id))

    def generate_otp(self) -> str:
        """Generate a random OTP."""
        return str(random.randint(10 ** (self.otp_length - 1), 10**self.otp_length - 1))

    def create_otp_for_user(self, user: Any) -> dict[str, Any]:
        """
        Create and store OTP for user in Redis.

        Returns:
            dict: OTP data with code, created_at, and resend_count
        """
        # Check if user is in lockout
        if self.is_user_locked_out(user.id):
            lockout_remaining = self.get_lockout_remaining_time(user.id)
            raise ValueError(
                f"User is temporarily locked out. Please wait {lockout_remaining} minutes before "
                "trying again."
            )

        otp_code = self.generate_otp()
        now = timezone.now()

        otp_data = {
            "user_id": user.id,
            "otp": otp_code,
            "created_at": now.isoformat(),
            "is_used": False,
            "resend_count": 0,
            "last_resend_at": None,
        }

        # Store OTP with expiry
        cache.set(
            self._get_otp_key(user.id),
            json.dumps(otp_data, default=str),
            timeout=self.expiry_minutes * 60,
        )

        # Reset resend tracking when creating new OTP
        cache.delete(self._get_resend_key(user.id))

        return otp_data

    def get_otp_for_user(self, user_id: int) -> dict[str, Any] | None:
        """Get OTP data for user from Redis."""
        otp_json = cache.get(self._get_otp_key(user_id))
        if not otp_json:
            return None

        try:
            return json.loads(otp_json)
        except json.JSONDecodeError:
            return None

    def verify_otp(self, user: Any, otp_code: str) -> tuple[bool, str]:
        """
        Verify OTP for user.

        Returns:
            tuple: (is_valid, error_message)
        """
        if self.is_user_locked_out(user.id):
            lockout_remaining = self.get_lockout_remaining_time(user.id)
            return (
                False,
                f"User is temporarily locked out. Please wait {lockout_remaining} minutes before "
                "trying again.",
            )

        otp_data = self.get_otp_for_user(user.id)
        if not otp_data:
            return False, "No valid OTP found. Please request a new one."

        if otp_data.get("is_used", False):
            return False, "OTP has already been used. Please request a new one."

        if self.is_otp_expired(otp_data):
            # Clean up expired OTP
            self._cleanup_user_data(user.id)
            return False, "OTP has expired. Please request a new one."

        if otp_data.get("otp") != otp_code:
            # Track failed attempt before returning
            self.track_failed_attempt(user.id)
            return False, "Invalid OTP code. Please check and try again."

        # Mark OTP as used and update in Redis
        otp_data["is_used"] = True
        otp_data["verified_at"] = timezone.now().isoformat()
        cache.set(
            self._get_otp_key(user.id),
            json.dumps(otp_data, default=str),
            timeout=self.expiry_minutes * 60,
        )

        # Clean up after successful verification
        # Note: We keep the OTP data briefly for potential audit purposes
        # but remove tracking keys
        cache.delete(self._get_resend_key(user.id))
        cache.delete(self._get_lockout_key(user.id))

        # Reset failed attempts on success
        self.reset_failed_attempts(user.id)
        return True, "OTP verified successfully"

    def resend_otp(self, user: Any) -> tuple[dict[str, Any], str]:
        """
        Resend OTP for user with rate limiting.

        Returns:
            tuple: (otp_data, success_message)
        """
        if self.is_user_locked_out(user.id):
            lockout_remaining = self.get_lockout_remaining_time(user.id)
            raise ValueError(
                f"User is temporarily locked out. Please wait {lockout_remaining} minutes before "
                "trying again."
            )

        # Check resend cooldown
        cooldown_remaining = self.get_resend_cooldown_remaining(user.id)
        if cooldown_remaining > 0:
            raise ValueError(
                f"Please wait {cooldown_remaining} seconds before requesting another OTP."
            )

        existing_otp = self.get_otp_for_user(user.id)

        if existing_otp and not self.is_otp_expired(existing_otp):
            # Check if we've hit the resend limit
            current_resend_count = existing_otp.get("resend_count", 0)
            if current_resend_count >= self.max_resend_count:
                # Lock out the user
                self._lockout_user(user.id)
                raise ValueError(
                    f"Maximum resend limit ({self.max_resend_count}) reached. Please wait "
                    f"{self.lockout_duration} minutes before trying again."
                )

            # Generate new OTP code but keep the same structure
            existing_otp["otp"] = self.generate_otp()
            existing_otp["resend_count"] = current_resend_count + 1
            existing_otp["last_resend_at"] = timezone.now().isoformat()
            existing_otp["is_used"] = False  # Reset used status for new OTP

            # Update in Redis with fresh expiry
            cache.set(
                self._get_otp_key(user.id),
                json.dumps(existing_otp, default=str),
                timeout=self.expiry_minutes * 60,
            )

            # Update resend tracking
            self._update_resend_tracking(user.id)

            return (
                existing_otp,
                f"OTP resent successfully. Attempt {existing_otp['resend_count']}/"
                f"{self.max_resend_count}",
            )
        else:
            # No existing OTP or expired - create new one
            if existing_otp:
                # Clean up expired OTP
                self._cleanup_user_data(user.id)

            new_otp_data = self.create_otp_for_user(user)
            return new_otp_data, "New OTP sent successfully"

    def is_otp_expired(self, otp_data: dict[str, Any]) -> bool:
        """Check if OTP is expired."""
        if not otp_data.get("created_at"):
            return True

        try:
            created_at = datetime.fromisoformat(otp_data["created_at"])
            if created_at.tzinfo is None:
                created_at = timezone.make_aware(created_at)

            return timezone.now() > created_at + timedelta(minutes=self.expiry_minutes)
        except (ValueError, TypeError):
            return True

    def is_user_locked_out(self, user_id: int) -> bool:
        """Check if user is locked out."""
        return cache.get(self._get_lockout_key(user_id)) is not None

    def get_lockout_remaining_time(self, user_id: int) -> int:
        """Get remaining lockout time in minutes."""
        lockout_time = cache.get(self._get_lockout_key(user_id))
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

    def get_resend_cooldown_remaining(self, user_id: int) -> int:
        """Get remaining cooldown time in seconds."""
        last_resend = cache.get(self._get_resend_key(user_id))
        if not last_resend:
            return 0

        try:
            last_resend_time = datetime.fromisoformat(last_resend)
            if last_resend_time.tzinfo is None:
                last_resend_time = timezone.make_aware(last_resend_time)

            elapsed = (timezone.now() - last_resend_time).total_seconds()
            remaining = max(0, self.resend_cooldown - elapsed)
            return int(remaining)
        except (ValueError, TypeError):
            return 0

    def get_user_otp_status(self, user_id: int) -> dict[str, Any]:
        """Get comprehensive OTP status for user."""
        otp_data = self.get_otp_for_user(user_id)

        status = {
            "has_active_otp": False,
            "is_locked_out": self.is_user_locked_out(user_id),
            "lockout_remaining_minutes": self.get_lockout_remaining_time(user_id)
            if self.is_user_locked_out(user_id)
            else 0,
            "resend_cooldown_seconds": self.get_resend_cooldown_remaining(user_id),
            "can_resend": False,
            "resend_count": 0,
            "max_resend_count": self.max_resend_count,
            "otp_expires_in_minutes": 0,
        }

        if otp_data and not self.is_otp_expired(otp_data):
            status["has_active_otp"] = True
            status["resend_count"] = otp_data.get("resend_count", 0)

            # Calculate expiry
            try:
                created_at = datetime.fromisoformat(otp_data["created_at"])
                if created_at.tzinfo is None:
                    created_at = timezone.make_aware(created_at)

                elapsed_minutes = (timezone.now() - created_at).total_seconds() / 60
                remaining_minutes = max(0, self.expiry_minutes - elapsed_minutes)
                status["otp_expires_in_minutes"] = int(remaining_minutes)
            except (ValueError, TypeError):
                pass

        # Can resend if not locked out, has cooldown passed, and hasn't exceeded limit
        status["can_resend"] = (
            not status["is_locked_out"]
            and status["resend_cooldown_seconds"] == 0
            and status["resend_count"] < self.max_resend_count
        )

        return status

    def _lockout_user(self, user_id: int):
        """Lock out user for configured duration."""
        cache.set(
            self._get_lockout_key(user_id),
            timezone.now().isoformat(),
            timeout=self.lockout_duration * 60,  # Convert minutes to seconds
        )

    def _update_resend_tracking(self, user_id: int):
        """Update resend tracking timestamp."""
        cache.set(
            self._get_resend_key(user_id), timezone.now().isoformat(), timeout=self.resend_cooldown
        )

    def _cleanup_user_data(self, user_id: int):
        """Clean up all OTP-related data for user."""
        cache.delete(self._get_otp_key(user_id))
        cache.delete(self._get_resend_key(user_id))
        cache.delete(self._get_lockout_key(user_id))
        cache.delete(self._get_failed_attempts_key(user_id))

    def cleanup_expired_otps(self):
        """Manual cleanup method (Redis handles auto-expiry)."""
        # Redis automatically handles expiry, but this method exists for interface compatibility
        pass

    def force_cleanup_user(self, user_id: int):
        """Force cleanup all data for a specific user (useful for testing/admin)."""
        self._cleanup_user_data(user_id)


# Global instance
otp_service = RedisOTPService()
