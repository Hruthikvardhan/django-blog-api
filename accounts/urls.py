"""
URL patterns for the accounts app.

Two lists are exposed because they are mounted at different prefixes in
config/urls.py:
    auth_urlpatterns -> /api/auth/
    user_urlpatterns -> /api/users/
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

auth_urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
]

user_urlpatterns = [
    path("<str:username>/", views.PublicProfileView.as_view(), name="public-profile"),
]

# Convenience so `include("accounts.urls")` also works for the auth routes.
urlpatterns = auth_urlpatterns
