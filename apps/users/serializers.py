from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.authentication.services.otp_service import otp_service
from apps.authentication.utils import Util


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'is_verified', 'date_joined', 'last_login')

class UserRegistrationSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'date_joined', 'password1', 'password2')
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {'read_only': True},
        }

    def validate(self, attrs):
        pwd1 = attrs.get('password1')
        pwd2 = attrs.get('password2')

        if pwd1 != pwd2:
            raise serializers.ValidationError("Passwords do not match!")

        try:
            temp_user = CustomUser(email=attrs.get('email', ''))
            validate_password(pwd1, user=temp_user)
        except ValidationError as exc:
            raise serializers.ValidationError({'password1': exc.messages})

        return attrs        
    
    def create(self, validated_data):
        password = validated_data.pop('password1')
        validated_data.pop('password2')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


class RegistrationOTPSerializer(serializers.Serializer):
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self):
        if not self.user:
            raise serializers.ValidationError("User instance required for OTP generation.")
        
        otp_data = otp_service.create_otp_for_user(self.user)
        
        self.send_otp_email(self.user, otp_data['otp'])
        
        return {
            'otp_sent': True,
            'user_id': self.user.id,
            'email': self.user.email,
            'message': 'Registration successful. Please check your email for verification OTP.'
        }
    
    def send_otp_email(self, user, otp):
        email_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Email Verification</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h2 style="color: #007bff; margin-top: 0;">Welcome! Please Verify Your Email</h2>
                <p>Hello {user.email},</p>
                <p>Thank you for registering with us! To complete your registration, please verify your email address using the OTP below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background-color: #007bff; color: white; padding: 20px; border-radius: 10px; font-size: 24px; font-weight: bold; letter-spacing: 3px;">
                        {otp}
                    </div>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>This OTP will expire in {otp_service.expiry_minutes} minutes</li>
                        <li>Do not share this OTP with anyone</li>
                        <li>If you didn't request this registration, please ignore this email</li>
                        <li>You can resend the OTP if it expires</li>
                    </ul>
                </div>
            </div>
            
            <div style="text-align: center; color: #6c757d; font-size: 12px; margin-top: 20px;">
                <p>This is an automated message, please do not reply to this email.</p>
            </div>
        </body>
        </html>
        """
        
        data = {
            'subject': 'Welcome! Please Verify Your Email Address',
            'body': email_body,
            'to_email': user.email
        }
        
        Util.send_email(data)