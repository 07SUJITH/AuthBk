from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")
        raw_token = request.COOKIES.get(cookie_name)
        if not raw_token:
            return None
        validated_token = self.get_validated_token(raw_token)
        try:
            user = self.get_user(validated_token)
        except TokenError as exc:
            raise InvalidToken(f"Token validation failed: {exc}") from exc
        return (user, validated_token)
