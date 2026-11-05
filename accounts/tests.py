"""Tests for registration, login, profile, password change and logout."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()
PASSWORD = "StrongPass123!"


class AuthTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )

    def _login(self, email="alice@example.com", password=PASSWORD):
        return self.client.post(reverse("login"), {"email": email, "password": password})

    def test_register_success(self) -> None:
        res = self.client.post(
            reverse("register"),
            {"email": "new@example.com", "username": "newbie", "password": PASSWORD},
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["user"]["username"], "newbie")
        self.assertIn("access", res.data["tokens"])
        self.assertNotIn("password", res.data["user"])
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_register_duplicate_email_rejected(self) -> None:
        res = self.client.post(
            reverse("register"),
            {"email": "ALICE@example.com", "username": "other", "password": PASSWORD},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", res.data)

    def test_register_weak_password_rejected(self) -> None:
        res = self.client.post(
            reverse("register"),
            {"email": "weak@example.com", "username": "weak", "password": "123"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_tokens(self) -> None:
        res = self._login()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"]["email"], "alice@example.com")

    def test_login_wrong_password(self) -> None:
        res = self._login(password="WrongPass999!")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", res.data)

    def test_me_requires_authentication(self) -> None:
        res = self.client.get(reverse("me"))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", res.data)

    def test_me_get_and_update_profile(self) -> None:
        self.client.force_authenticate(self.user)
        res = self.client.get(reverse("me"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "alice")

        res = self.client.put(reverse("me"), {"bio": "Hello world", "website": "https://alice.dev"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Hello world")
        self.assertEqual(self.user.website, "https://alice.dev")

    def test_change_password(self) -> None:
        self.client.force_authenticate(self.user)
        res = self.client.put(
            reverse("change-password"),
            {"old_password": PASSWORD, "new_password": "BrandNewPass456!"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass456!"))

    def test_change_password_wrong_old_password(self) -> None:
        self.client.force_authenticate(self.user)
        res = self.client.put(
            reverse("change-password"),
            {"old_password": "nope", "new_password": "BrandNewPass456!"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_blacklists_refresh_token(self) -> None:
        tokens = self._login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        res = self.client.post(reverse("logout"), {"refresh": tokens["refresh"]})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # The blacklisted refresh token can no longer be used.
        self.client.credentials()
        res = self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_rotates_token(self) -> None:
        tokens = self._login().data
        res = self.client.post(reverse("token-refresh"), {"refresh": tokens["refresh"]})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)  # rotation returns a new refresh token
        self.assertNotEqual(res.data["refresh"], tokens["refresh"])
