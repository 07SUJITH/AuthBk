from decouple import config
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.utils.encoding import DjangoUnicodeDecodeError, force_bytes, smart_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers

from apps.authentication.services.otp_service import otp_service

from .utils import Util

User = get_user_model()


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, data):
        user = authenticate(**data)

        if user and user.is_active:
            return user

        raise serializers.ValidationError("Invalid credentials")


class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        fields = ["old_password", "new_password", "confirm_password"]

    def validate_old_password(self, value):
        user = self.context["user"]
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value

    def validate_new_password(self, value):
        user = self.context["user"]
        try:
            password_validation.validate_password(value, user=user)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages) from e
            """
              "new_password": [
                "This password is too common.",
                "This password is entirely numeric."
            ]
            """
        return value

    def validate(self, data):
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "New password and confirm password do not match."}
            )

        if old_password == new_password:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from the current password."}
            )

        return data

    def save(self):
        user = self.context["user"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class SendPasswordResetEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            self.context["user"] = user
        except User.DoesNotExist as err:
            raise serializers.ValidationError("No user found with this email address.") from err
        return value

    def save(self):
        user = self.context["user"]
        email = self.validated_data["email"]

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = PasswordResetTokenGenerator().make_token(user)
        frontend_url = config("FRONTEND_URL", default="http://127.0.0.1:5173")
        link = f"{frontend_url}/reset-password/{uid}/{token}/"
        email_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Password Reset Request</title>
        </head>
        <body
            style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;
                max-width: 600px; margin: 0 auto; padding: 20px;"
        >
            <div
                style="background-color: #f8f9fa; padding: 20px;
                    border-radius: 10px; margin-bottom: 20px;"
            >
                <h2 style="color: #007bff; margin-top: 0;">
                    Password Reset Request
                </h2>
                <p>Hello {user.email},</p>
                <p>
                    We received a request to reset your password for your account.
                    If you made this request, please click the button below to
                    reset your password:
                </p>

                <div style="text-align: center; margin: 30px 0;">
                    <a
                        href="{link}"
                        style="background-color: #007bff; color: white;
                            padding: 12px 30px; text-decoration: none;
                            border-radius: 5px; display: inline-block;
                            font-weight: bold;"
                    >
                        Reset Password
                    </a>
                </div>

                <p>Or copy and paste this link into your browser:</p>
                <p style="background-color: #e9ecef; padding: 10px;
                        border-radius: 5px; word-break: break-all;">
                    {link}
                </p>

                <div style="margin-top: 30px; padding-top: 20px;
                            border-top: 1px solid #dee2e6;">
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>This link will expire in 15 minutes for security reasons</li>
                        <li>If you didn't request this password reset, please ignore this email</li>
                        <li>Your password will remain unchanged until you create a new one</li>
                    </ul>
                </div>

                <p style="margin-top: 20px; color: #6c757d; font-size: 14px;">
                    If you're having trouble clicking the button, copy and
                    paste the URL into your web browser.
                </p>
            </div>

            <div style="text-align: center; color: #6c757d;
                        font-size: 12px; margin-top: 20px;">
                <p>This is an automated message, please do not reply to this email.</p>
            </div>
        </body>
        </html>
        """

        data = {
            "subject": "Password Reset Request - JWT Auth App",
            "body": email_body,
            "to_email": user.email,
        }

        Util.send_email(data)

        return {"email": email, "message": "Password reset email sent successfully"}


class UserPasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, data):
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")
        uid = self.context.get("uid")
        token = self.context.get("token")

        if not uid or not token:
            raise serializers.ValidationError("Missing required reset parameters.")

        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "New password and confirm password do not match."}
            )

        try:
            user_id = smart_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (DjangoUnicodeDecodeError, ValueError, User.DoesNotExist) as err:
            raise serializers.ValidationError("The reset link is invalid or has expired.") from err
        if not PasswordResetTokenGenerator().check_token(user, token):
            raise serializers.ValidationError("The reset link is invalid or has expired.")

        try:
            password_validation.validate_password(new_password, user=user)
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": e.messages}) from e

        self.context["validated_user"] = user
        data["email"] = user.email
        return data

    def save(self):
        user = self.context["validated_user"]
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, data):
        email = data.get("email")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as err:
            raise serializers.ValidationError("User with this email does not exist.") from err

        if user.is_verified:
            raise serializers.ValidationError("User is already verified.")

        data["user"] = user
        return data

    def save(self):
        user = self.validated_data["user"]
        otp = self.validated_data["otp"]

        is_valid, error_message = otp_service.verify_otp(user, otp)
        if not is_valid:
            raise serializers.ValidationError(error_message)

        user.is_verified = True
        user.save()

        return user


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist as err:
            raise serializers.ValidationError("User with this email does not exist.") from err
        if user.is_verified:
            raise serializers.ValidationError("User is already verified.")

        self.context["user"] = user
        return value

    def save(self):
        user = self.context["user"]

        otp_data, message = otp_service.resend_otp(user)

        self.send_otp_email(user, otp_data["otp"])

        return {
            "resend_count": otp_data.get("resend_count", 0),
            "max_resend_count": otp_service.max_resend_count,
            "message": message,
        }

    def send_otp_email(self, user, otp):
        email_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Email Verification - OTP Resend</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }}
                .header {{
                    color: #007bff;
                    margin-top: 0;
                }}
                .otp-container {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .otp-box {{
                    background-color: #007bff;
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    font-size: 24px;
                    font-weight: bold;
                    letter-spacing: 3px;
                    display: inline-block;
                }}
                .important-note {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #dee2e6;
                }}
                .footer {{
                    text-align: center;
                    color: #6c757d;
                    font-size: 12px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="header">Email Verification - OTP Resend</h2>
                <p>Hello {user.email},</p>
                <p>You requested to resend your email verification OTP. Please use the code below to
                verify your email:</p>

                <div class="otp-container">
                    <div class="otp-box">
                        {otp}
                    </div>
                </div>

                <div class="important-note">
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>This OTP will expire in {otp_service.expiry_minutes} minutes</li>
                        <li>Do not share this OTP with anyone</li>
                        <li>If you didn't request this verification, please ignore this email</li>
                    </ul>
                </div>
            </div>

            <div class="footer">
                <p>This is an automated message, please do not reply to this email.</p>
            </div>
        </body>
        </html>
        """

        data = {
            "subject": "Email Verification - OTP Resend",
            "body": email_body,
            "to_email": user.email,
        }

        Util.send_email(data)
