from django.urls import path
from .views import (
    UserRegistrationAPIView,
    UserInfoAPIView,
)

urlpatterns = [
    path('register/',    UserRegistrationAPIView .as_view(), name='user-register'),
    path('profile/',     UserInfoAPIView         .as_view(), name='user-profile'),
]
