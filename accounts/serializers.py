"""Serializers for registration, login, profile and password change."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Full profile of the logged-in user (also used in login/register responses)."""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "bio",
            "avatar",
            "website",
            "created_at",
        )
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """Fields a user may change on PUT /api/auth/me/ (all optional)."""

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "bio", "avatar", "website")
        extra_kwargs = {field: {"required": False} for field in fields}


class PublicUserSerializer(serializers.ModelSerializer):
    """Public profile: no email address is exposed."""

    post_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "bio",
            "avatar",
            "website",
            "created_at",
            "post_count",
        )

    def get_post_count(self, obj) -> int:
        return obj.posts.filter(status="published").count()


class RegisterSerializer(serializers.ModelSerializer):
    """Create an account from email, username and password."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "username", "password")

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        # Run Django's password validators (length, common passwords, similarity...).
        candidate = User(email=attrs.get("email", ""), username=attrs.get("username", ""))
        validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data: dict):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login with email + password.

    Because User.USERNAME_FIELD == "email", SimpleJWT already expects an `email`
    field. We additionally lower-case it and return the user profile.
    """

    def validate(self, attrs: dict) -> dict:
        attrs[self.username_field] = attrs[self.username_field].strip().lower()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user, context=self.context).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """Old password + new password."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, user=self.context["request"].user)
        return value
