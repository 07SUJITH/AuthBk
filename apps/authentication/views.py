from decouple import config
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import smart_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.core import is_ratelimited
from rest_framework import status
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.authentication.services.otp_service import otp_service
from apps.authentication.services.password_reset_service import password_reset_service
from apps.users.serializers import CustomUserSerializer

from .serializers import (
    ResendOTPSerializer,
    SendPasswordResetEmailSerializer,
    UserChangePasswordSerializer,
    UserLoginSerializer,
    UserPasswordResetSerializer,
    VerifyOTPSerializer,
)

User = get_user_model()


@method_decorator(never_cache, name='dispatch')
class UserLoginAPIView(GenericAPIView):

    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        
        was_limited = is_ratelimited(
            request=request,
            group="login",              
            key='ip',
            rate='5/m',
            method='POST',
            increment=True,
        )

        if was_limited:
            raise Throttled(detail="Too many login attempts from this IP. Try again later.")

        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data
            if not user.is_verified:
                return Response({
                    "message": "Email not verified. Please verify using the OTP sent to your email.",
                    "errors": {
                        "email": ["User account not verified."]
                    },
                    "email": user.email,
                    "is_verified": False
                }, status=status.HTTP_401_UNAUTHORIZED)

            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
            
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            user_data = CustomUserSerializer(user).data
            user_data["message"] = "Login successful"

            response = Response(user_data, status=status.HTTP_200_OK)
            response.set_cookie(
                key=settings.JWT_AUTH_COOKIE,
                value=access_token,
                max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds(),
                httponly=settings.JWT_AUTH_HTTPONLY,
                secure=settings.JWT_AUTH_SECURE,
                samesite=settings.JWT_AUTH_SAMESITE,
                domain=settings.JWT_AUTH_COOKIE_DOMAIN,
            )

            response.set_cookie(
                key=settings.JWT_AUTH_REFRESH_COOKIE,
                value=refresh_token,
                max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds(),
                httponly=settings.JWT_AUTH_HTTPONLY,
                secure=settings.JWT_AUTH_SECURE,
                samesite=settings.JWT_AUTH_SAMESITE,
                domain=settings.JWT_AUTH_COOKIE_DOMAIN,
            )

            return response
        except ValidationError as e:
            if isinstance(e.detail, dict):
                first_error = next(iter(e.detail.values()))[0] if e.detail else "Validation failed."
            elif isinstance(e.detail, list):
                first_error = e.detail[0] if e.detail else "Validation failed."
            else:
                first_error = "Validation failed."
            return Response({
                "error": e.detail,
                "detail": first_error
            }, status=status.HTTP_400_BAD_REQUEST)

        
    
class UserLogoutAPIView(APIView):
    
    permission_classes = ()  

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)

        response = Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_205_RESET_CONTENT
        )
        response.delete_cookie(
            settings.JWT_AUTH_COOKIE,
            samesite=settings.JWT_AUTH_SAMESITE
        )
        response.delete_cookie(
            settings.JWT_AUTH_REFRESH_COOKIE,
            samesite=settings.JWT_AUTH_SAMESITE
        )

        if refresh_token:
            try:
                token_obj = RefreshToken(refresh_token)
                token_obj.blacklist()
            except TokenError:
                pass

        return response

                       

class CookieTokenRefreshView(TokenRefreshView):
    
    def post(self, request, *args, **kwargs):

        refresh_token = request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)
        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found in cookies"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            old_refresh_obj = RefreshToken(refresh_token)

            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
                try:
                    old_refresh_obj.blacklist()
                except AttributeError:
                    pass
                User = get_user_model()
                try:
                    user = User.objects.get(pk=old_refresh_obj["user_id"])
                except User.DoesNotExist:
                    return Response({"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED)

                new_refresh_obj = RefreshToken.for_user(user)

                access_token = str(new_refresh_obj.access_token)
                new_refresh_token = str(new_refresh_obj)
            else:
                access_token = str(old_refresh_obj.access_token)
                new_refresh_token = refresh_token  # ensures safe fallback

            response = Response(
                {"detail": "Token refreshed successfully"},
                status=status.HTTP_200_OK
            )

            response.set_cookie(
                key=settings.JWT_AUTH_COOKIE,
                value=access_token,
                max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds(),
                httponly=settings.JWT_AUTH_HTTPONLY,
                secure=settings.JWT_AUTH_SECURE,
                samesite=settings.JWT_AUTH_SAMESITE,
                domain=settings.JWT_AUTH_COOKIE_DOMAIN,
            )

            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS'):
                response.set_cookie(
                    key=settings.JWT_AUTH_REFRESH_COOKIE,
                    value=new_refresh_token,
                    max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds(),
                    httponly=settings.JWT_AUTH_HTTPONLY,
                    secure=settings.JWT_AUTH_SECURE,
                    samesite=settings.JWT_AUTH_SAMESITE,
                    domain=settings.JWT_AUTH_COOKIE_DOMAIN,
                )

            return response

        except TokenError:
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )


class UserChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]  
    
    def post(self, request, *args, **kwargs):
        serializer = UserChangePasswordSerializer(data=request.data, context={'user': request.user})
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        except ValidationError as e:
            if isinstance(e.detail, dict):
                first_error = next(iter(e.detail.values()))[0] if e.detail else "Validation failed."
            elif isinstance(e.detail, list):
                first_error = e.detail[0] if e.detail else "Validation failed."
            else:
                first_error = "Validation failed."
            return Response({
                "error": e.detail,
                "detail": first_error
            }, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(never_cache, name='dispatch')
class SendPasswordResetEmailAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        was_limited = is_ratelimited(
            request=request,
            group="password_reset",  # Unique group name
            key='ip',
            rate='10/m',              # 10 requests/minute per IP
            method='POST',
            increment=True
        )
        
        if was_limited:
            raise Throttled(detail="Too many password reset requests from this IP. Try again later.")
        
        serializer = SendPasswordResetEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        can_request, message = password_reset_service.can_request_reset(email)
        if not can_request:
            raise Throttled(detail=message)
        
        password_reset_service.track_reset_request(email)
        serializer.save()  # Sends email
        
        return Response({
            "message": "Password reset link sent. Please check your email."
        }, status=status.HTTP_200_OK)


@method_decorator(never_cache, name='dispatch')
class UserPasswordResetAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uid, token, format=None):
        was_limited = is_ratelimited(
            request=request,
            group="password_reset_confirm",  # Unique group name
            key='ip',
            rate='20/m',                     # 20 requests/minute per IP
            method='POST',
            increment=True
        )
        
        if was_limited:
            raise Throttled(detail="Too many password reset attempts from this IP. Try again later.")

        try:
            user_id = smart_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
            user_email = user.email
        except (Exception):
            user_email = None
        if user_email:
            can_attempt, message = password_reset_service.can_attempt_reset(user_email)
            if not can_attempt:
                raise Throttled(detail=message)
        

        serializer = UserPasswordResetSerializer(
            data=request.data, 
            context={'uid': uid, 'token': token}
        )
        
        try:
            serializer.is_valid(raise_exception=True)
            
            user_email = (
                serializer.validated_data.get('email') or 
                getattr(serializer.context.get('validated_user'), 'email', None)
            )
            
            
            if user_email:
                can_attempt, message = password_reset_service.can_attempt_reset(user_email)
                if not can_attempt:
                    raise Throttled(detail=message)
            
            serializer.save()
            
            if user_email:
                password_reset_service.clear_reset_tracking(user_email)
            
            return Response({
                "message": "Password reset successful."
            }, status=status.HTTP_200_OK)
            
        except ValidationError as e:
            self._track_failed_attempt(uid)
            
            return Response({
                "detail": "Reset failed. Invalid or expired link.",
                "errors": e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
    
      
    def _track_failed_attempt(self, uid):
        try:
            if uid:
                decoded_uid = smart_str(urlsafe_base64_decode(uid))
                if user := User.objects.filter(pk=decoded_uid).first():
                    password_reset_service.track_failed_reset_attempt(user.email)
        except Exception:
            pass  # Silent fail - tracking is secondary to security response


@method_decorator(never_cache, name='dispatch')
class VerifyOTPAPIView(GenericAPIView):
 
    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        was_limited = is_ratelimited(
            request=request,
            group="verify_otp",  
            key='ip',
            rate='30/m',         
            method='POST',
            increment=True
        )
        
        if was_limited:
            raise Throttled(detail="Too many OTP verification attempts from this IP. Try again later.")
        
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            user = serializer.validated_data.get('user')
            
            if otp_service.is_user_locked_out(user.id):
                lockout_remaining = otp_service.get_lockout_remaining_time(user.id)
                raise Throttled(detail=f"Account locked. Try again in {lockout_remaining} minutes.")
            user = serializer.save()
            
            return Response({
                "message": "Email verified successfully.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "is_verified": user.is_verified
                }
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            if 'user' in serializer.errors:
                self._track_failed_attempt(serializer.errors['user'])
            
            if 'non_field_errors' in e.detail and isinstance(e.detail['non_field_errors'], list):
                error_message = e.detail['non_field_errors'][0] 
            elif isinstance(e.detail, dict):
                error_message = next(iter(e.detail.values()))[0] if e.detail else "Validation failed."
            elif isinstance(e.detail, list):
                error_message = e.detail[0] if e.detail else "Validation failed."
            else:
                error_message = "Validation failed."

            return Response({
                "detail": error_message, 
                "errors": e.detail 
            }, status=status.HTTP_400_BAD_REQUEST)

            
            
    def _track_failed_attempt(self, user_error):
        try:
            if isinstance(user_error, dict) and 'id' in user_error:
                otp_service.track_failed_attempt(user_error['id'])
        except Exception:
            pass 


@method_decorator(never_cache, name='dispatch')
class ResendOTPAPIView(GenericAPIView):
    serializer_class = ResendOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        was_limited = is_ratelimited(
            request=request,
            group="resend_otp",     
            key='ip',
            rate='4/m',         
            method='POST',
            increment=True
        )
        
        if was_limited:
            raise Throttled(detail="Too many OTP resend requests from this IP. Try again later.")
        
        
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            user = serializer.context['user']
            
            if otp_service.is_user_locked_out(user.id):
                lockout_remaining = otp_service.get_lockout_remaining_time(user.id)
                error_message = f"Account locked. Try again in {lockout_remaining} minutes."
                raise Throttled(detail=error_message)

            cooldown_remaining = otp_service.get_resend_cooldown_remaining(user.id)
            if cooldown_remaining > 0:
                raise Throttled(detail=f"Wait {cooldown_remaining}s before requesting another OTP.")
            
            
            result = serializer.save()
            
            return Response({
                "message": result.get('message', 'OTP resent successfully.'),
                "resend_count": result.get('resend_count', 0),
                "max_resend_count": result.get('max_resend_count', 3),
                "next_resend_available": result.get('cooldown', 60)  # in seconds
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response({
                "detail": "Could not verify rate limits. Please try again later."
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        except Throttled as e:
            raise e
        
        except ValidationError as e:
            if 'email' in e.detail and isinstance(e.detail['email'], list):
                error_message = e.detail['email'][0] 
                return Response({
                    "detail": error_message, 
                    "errors": e.detail 
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    "detail": "Validation failed.",
                    "errors": e.detail
                }, status=status.HTTP_400_BAD_REQUEST)
                        
        except Exception as e:
            return Response({
                "detail": "An unexpected error occurred.",
                "errors": str(e) 
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# This variable is crucial for securing your endpoint.
CRON_SECRET_KEY = config('CRON_SECRET_KEY', 'a-very-insecure-default-key-change-it!')

@csrf_exempt  # Allows POST requests without CSRF token 
@require_POST 
def run_flush_expired_tokens(request):
    """
    Triggers the flushexpiredtokens_daily management command via an HTTP endpoint.
    Requires a POST request and a matching 'X-Cron-Secret' header for security.
    """
    if request.method == 'POST':
        if request.headers.get('X-Cron-Secret') != CRON_SECRET_KEY:
            return JsonResponse({'status': 'Unauthorized', 'message': 'Invalid or missing secret key.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            call_command('flushexpiredtokens_daily') 
            return JsonResponse({'status': 'success', 'message': 'Expired tokens flushed successfully.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error flushing tokens: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return JsonResponse({'status': 'method_not_allowed', 'message': 'Only POST requests are allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
            