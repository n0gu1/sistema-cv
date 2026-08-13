from django.db import connection
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone

from reclutamiento.models import RolUsuario, Usuario, UsuarioRol


class AuthenticationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(RolUsuario)
            schema_editor.create_model(Usuario)
            schema_editor.create_model(UsuarioRol)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(UsuarioRol)
            schema_editor.delete_model(Usuario)
            schema_editor.delete_model(RolUsuario)
        super().tearDownClass()

    def setUp(self):
        # Unmanaged tables are intentionally outside Django's automatic flush.
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM usuarios_roles")
            cursor.execute("DELETE FROM usuarios")
            cursor.execute("DELETE FROM roles_usuario")
        self.hr_role = RolUsuario.objects.create(codigo="RRHH", nombre="RR. HH.")
        self.applicant_role = RolUsuario.objects.create(
            codigo="ASPIRANTE",
            nombre="Aspirante",
        )
        self.hr_user = self._create_user(
            "rrhh@example.com",
            "Carlos",
            "Méndez",
            self.hr_role,
        )
        self.applicant = self._create_user(
            "andrea@example.com",
            "Andrea",
            "Ruiz",
            self.applicant_role,
        )

    def _create_user(self, email, first_name, last_name, role, **kwargs):
        user = Usuario.objects.create_user(
            email=email,
            password="Clave-Segura-2026",
            first_name=first_name,
            last_name=last_name,
            is_active=kwargs.get("is_active", True),
            is_verified=kwargs.get("is_verified", True),
        )
        UsuarioRol.objects.create(
            usuario=user,
            rol=role,
            asignado_en=timezone.now(),
        )
        return user

    def test_login_page_is_public(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bienvenido de vuelta")

    def test_credentials_are_verified_with_django_hash(self):
        self.assertTrue(self.hr_user.check_password("Clave-Segura-2026"))
        self.assertNotEqual(self.hr_user.password, "Clave-Segura-2026")

        response = self.client.post(
            reverse("index"),
            {
                "role": "rrhh",
                "email": self.hr_user.email,
                "password": "Clave-Segura-2026",
                "remember": "on",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.hr_user.pk)

    def test_applicant_is_redirected_to_applicant_portal(self):
        response = self.client.post(
            reverse("index"),
            {
                "role": "aspirante",
                "email": self.applicant.email,
                "password": "Clave-Segura-2026",
            },
        )

        self.assertRedirects(response, reverse("portal"))
        self.assertEqual(self.client.session.get_expire_at_browser_close(), True)

    def test_invalid_password_does_not_create_session(self):
        response = self.client.post(
            reverse("index"),
            {
                "role": "rrhh",
                "email": self.hr_user.email,
                "password": "incorrecta",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no son correctos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_selected_workspace_must_match_database_role(self):
        response = self.client.post(
            reverse("index"),
            {
                "role": "rrhh",
                "email": self.applicant.email,
                "password": "Clave-Segura-2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no tiene acceso")

    def test_unverified_user_cannot_login(self):
        self.applicant.is_verified = False
        self.applicant.save(update_fields=["is_verified"])

        response = self.client.post(
            reverse("index"),
            {
                "role": "aspirante",
                "email": self.applicant.email,
                "password": "Clave-Segura-2026",
            },
        )

        self.assertContains(response, "verificar tu correo")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_login(self):
        self.applicant.is_active = False
        self.applicant.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("index"),
            {
                "role": "aspirante",
                "email": self.applicant.email,
                "password": "Clave-Segura-2026",
            },
        )

        self.assertContains(response, "no son correctos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_does_not_redirect_to_an_external_host(self):
        response = self.client.post(
            f"{reverse('index')}?next=https://malicioso.example/robar-sesion",
            {
                "role": "rrhh",
                "email": self.hr_user.email,
                "password": "Clave-Segura-2026",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('index')}?next={reverse('dashboard')}",
        )

    def test_role_permissions_are_enforced(self):
        self.client.force_login(self.applicant)

        self.assertEqual(self.client.get(reverse("portal")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_hr_pages_are_available_for_hr_user(self):
        self.client.force_login(self.hr_user)
        expected_content = {
            "dashboard": "Centro de contratación",
            "plazas": "Gestión de plazas",
            "nueva_plaza": "Nueva plaza",
            "aspirantes": "Base de talento",
            "analisis": "Informe de compatibilidad",
        }

        for route_name, content in expected_content.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, content)

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.hr_user)

        get_response = self.client.get(reverse("cerrar_sesion"))
        self.assertRedirects(get_response, reverse("dashboard"))
        self.assertIn("_auth_user_id", self.client.session)

        post_response = self.client.post(reverse("cerrar_sesion"))
        self.assertRedirects(post_response, reverse("index"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_recovery_does_not_disclose_account_existence(self):
        existing_response = self.client.post(
            reverse("solicitar_recuperacion"),
            {"email": self.hr_user.email},
        )
        missing_response = self.client.post(
            reverse("solicitar_recuperacion"),
            {"email": "missing@example.com"},
        )

        self.assertEqual(existing_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 200)
        self.assertContains(existing_response, "Revisa tu correo")
        self.assertContains(missing_response, "Revisa tu correo")
        self.assertEqual(len(mail.outbox), 1)

    def test_valid_reset_token_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.hr_user.pk))
        token = default_token_generator.make_token(self.hr_user)
        response = self.client.post(
            reverse(
                "restablecer_contrasena",
                kwargs={"uidb64": uid, "token": token},
            ),
            {
                "new_password1": "Nueva-Clave-Segura-2027",
                "new_password2": "Nueva-Clave-Segura-2027",
            },
        )

        self.assertRedirects(response, reverse("index"))
        self.hr_user.refresh_from_db()
        self.assertTrue(self.hr_user.check_password("Nueva-Clave-Segura-2027"))

    def test_email_verification_token_activates_verification(self):
        self.applicant.is_verified = False
        self.applicant.save(update_fields=["is_verified"])
        uid = urlsafe_base64_encode(force_bytes(self.applicant.pk))
        token = default_token_generator.make_token(self.applicant)

        response = self.client.get(
            reverse(
                "verificar_correo",
                kwargs={"uidb64": uid, "token": token},
            )
        )

        self.assertRedirects(response, reverse("index"))
        self.applicant.refresh_from_db()
        self.assertTrue(self.applicant.is_verified)


class SaludViewTests(TestCase):
    def test_reports_database_connection(self):
        response = self.client.get(reverse("salud"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"aplicacion": "disponible", "base_de_datos": "conectada"},
        )
