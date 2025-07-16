from rest_framework.generics import GenericAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import UserRegistrationSerializer, CustomUserSerializer, RegistrationOTPSerializer
from rest_framework.response import Response
from rest_framework import status
from django_ratelimit.core import is_ratelimited
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.db import transaction
from rest_framework.exceptions import Throttled, PermissionDenied


@method_decorator(never_cache, name='dispatch')
class UserRegistrationAPIView(GenericAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):

        was_limited = is_ratelimited(
            request=request,
            group="user_registration",
            key='ip',
            rate='20/m',  
            method='POST',
            increment=True
        )
        
        if was_limited:
            raise Throttled(detail="Too many registration attempts from this IP. Try again later.")
        
       
        user_serializer = self.get_serializer(data=request.data)
        try:
      
            user_serializer.is_valid(raise_exception=True)
            
            
            if self._is_restricted_domain(user_serializer.validated_data.get('email')):
                raise PermissionDenied(detail="Registrations from this domain are currently not allowed.")
            
            with transaction.atomic():
                
                user = user_serializer.save()
                
                # Generate and send OTP
                otp_serializer = RegistrationOTPSerializer(user=user)
                otp_serializer.save()
                
                return Response({
                    "message": "Registration successful. Verification OTP sent.",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                        "is_verified": False 
                    },
                    "otp_meta": {
                        "resend_available": True,
                        "next_resend_in": 60  
                    }
                }, status=status.HTTP_201_CREATED)
                
        except PermissionDenied as e:
            
            return Response({
                "detail": str(e),
                "errors": {"email": [str(e)]} 
            }, status=status.HTTP_403_FORBIDDEN)
            
        except Exception as e:
            
            if 'email' in e.detail and isinstance(e.detail['email'], list):
                error_message = e.detail['email'][0]  
                return Response({
                    "detail": error_message,  
                    "errors": e.detail  
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                
                print(e.detail)  
                first_key = next(iter(e.detail), None)  
                error_message = e.detail[first_key][0] if first_key and isinstance(e.detail[first_key], list) else "Validation failed."
                return Response({
                    "detail": error_message,  
                    "errors": e.detail  
                }, status=status.HTTP_400_BAD_REQUEST)
             
    
    def _is_restricted_domain(self, email):
        from django.conf import settings
        if not email:
            return False
        domain = email.split('@')[-1]
        return domain in settings.RESTRICTED_REGISTRATION_DOMAINS

class UserInfoAPIView(RetrieveAPIView):
    serializer_class = CustomUserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user