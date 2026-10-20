"""Smoke checks for first-login password rotation on fresh installations."""

from django.contrib.auth import get_user_model
from django.test import TestCase


class BootstrapAdminRotationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin", email="", password="admin123"
        )

    def test_default_admin_cannot_open_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/password/")

    def test_default_admin_can_change_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/password/",
            {
                "old_password": "admin123",
                "new_password1": "NewPrivatePassphraseForFirstLogin!2026",
                "new_password2": "NewPrivatePassphraseForFirstLogin!2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("NewPrivatePassphraseForFirstLogin!2026"))
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_non_admin_users_are_not_forced(self):
        user = get_user_model().objects.create_user(
            username="worker", password="admin123"
        )
        self.client.force_login(user)
        self.assertNotEqual(self.client.get("/").status_code, 302)

    def test_anonymous_login_page_works(self):
        self.assertEqual(self.client.get("/login/").status_code, 200)
