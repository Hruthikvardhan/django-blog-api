"""Auth + profile views."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    PublicUserSerializer,
    RegisterSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ -> create account, return profile + tokens."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user, context={"request": request}).data,
                "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ -> {"access", "refresh", "user"}."""

    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """POST /api/auth/logout/ with {"refresh": "..."} -> blacklists that refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        token = request.data.get("refresh")
        if not token:
            return Response({"detail": "Refresh token is required."}, status=400)
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired refresh token."}, status=400)
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class MeView(APIView):
    """GET /api/auth/me/ -> my profile. PUT/PATCH -> update profile and avatar."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # multipart for avatar upload

    def get(self, request) -> Response:
        return Response(UserSerializer(request.user, context={"request": request}).data)

    def _update(self, request, partial: bool) -> Response:
        serializer = UserUpdateSerializer(
            request.user, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user, context={"request": request}).data)

    def put(self, request) -> Response:
        return self._update(request, partial=False)

    def patch(self, request) -> Response:
        return self._update(request, partial=True)


class ChangePasswordView(APIView):
    """PUT /api/auth/change-password/ with old_password + new_password."""

    permission_classes = [IsAuthenticated]

    def put(self, request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password updated successfully."})


class PublicProfileView(APIView):
    """GET /api/users/<username>/ -> public profile + their published posts (paginated)."""

    permission_classes = [AllowAny]

    def get(self, request, username: str) -> Response:
        # Imported here to avoid a circular import (blog depends on accounts).
        from blog.models import Post
        from blog.serializers import PostListSerializer

        user = get_object_or_404(User, username=username, is_active=True)
        posts = (
            Post.objects.with_stats(request.user)
            .published()
            .filter(author=user)
            .order_by("-published_at")
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(posts, request, view=self)
        posts_data = PostListSerializer(page, many=True, context={"request": request}).data

        data = PublicUserSerializer(user, context={"request": request}).data
        data["posts"] = paginator.get_paginated_response(posts_data).data
        return Response(data)
