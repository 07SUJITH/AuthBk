from django.urls import path
from .views import (
    UserLoginAPIView,
    UserLogoutAPIView,
    CookieTokenRefreshView,
    UserChangePasswordAPIView,
    SendPasswordResetEmailAPIView,
    UserPasswordResetAPIView,
    VerifyOTPAPIView,
    ResendOTPAPIView,
    run_flush_expired_tokens
)

urlpatterns = [
    path('login/',       UserLoginAPIView        .as_view(), name='user-login'),
    path('logout/',      UserLogoutAPIView       .as_view(), name='user-logout'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token-refresh'),
    path('change-password/', UserChangePasswordAPIView.as_view(), name='change-password'),
    path('send-reset-password-email/', SendPasswordResetEmailAPIView.as_view(), name='send-reset-password'),
    path('reset-password/<uid>/<token>/', UserPasswordResetAPIView.as_view(), name='password-reset'),
    path('verify-otp/', VerifyOTPAPIView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPAPIView.as_view(), name='resend-otp'),
    path('cron/flush-tokens/', run_flush_expired_tokens, name='flush_tokens_cron'),
]
