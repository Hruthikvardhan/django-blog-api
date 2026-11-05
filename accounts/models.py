"""Custom user model: log in with email, extra profile fields."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Project user.

    * `email` is unique and is the login identifier (USERNAME_FIELD).
    * `username` is still required: it is shown publicly and used in
      profile URLs (/api/users/<username>/).
    """

    email = models.EmailField("email address", unique=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]  # asked by `createsuperuser` besides email/password

    def save(self, *args, **kwargs) -> None:
        # Normalise emails so "Bob@Mail.com" and "bob@mail.com" are the same account.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username
