from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = "Email not verified. Please complete verification to access this resource."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_verified)
