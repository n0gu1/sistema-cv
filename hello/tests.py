from django.db import connection
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from unittest.mock import patch

from reclutamiento.models import (
    AreaEstudio,
    CategoriaHabilidad,
    Certificacion,
    Ciudad,
    Departamento,
    EstadoPlaza,
    Habilidad,
    HistorialEstadoPlaza,
    Idioma,
    ModalidadTrabajo,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    Pais,
    PeriodoSalarial,
    PerfilAspirante,
    Plaza,
    Profesion,
    RequisitoCertificacion,
    RequisitoDisponibilidad,
    RequisitoEducacion,
    RequisitoExperiencia,
    RequisitoHabilidad,
    RequisitoIdioma,
    RequisitoPlaza,
    Region,
    RolUsuario,
    TipoEmpleo,
    TipoRequisito,
    Usuario,
    UsuarioRol,
)
from reclutamiento.tokens import email_verification_token
from reclutamiento.vacancies import transition_vacancy


class AuthenticationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(RolUsuario)
            schema_editor.create_model(Pais)
            schema_editor.create_model(Region)
            schema_editor.create_model(Ciudad)
            schema_editor.create_model(Profesion)
            schema_editor.create_model(Usuario)
            schema_editor.create_model(UsuarioRol)
            schema_editor.create_model(PerfilAspirante)
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE postulaciones ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, aspirante_id BIGINT NOT NULL)"
            )

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE postulaciones")
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(PerfilAspirante)
            schema_editor.delete_model(UsuarioRol)
            schema_editor.delete_model(Usuario)
            schema_editor.delete_model(Profesion)
            schema_editor.delete_model(Ciudad)
            schema_editor.delete_model(Region)
            schema_editor.delete_model(Pais)
            schema_editor.delete_model(RolUsuario)
        super().tearDownClass()

    def setUp(self):
        # Unmanaged tables are intentionally outside Django's automatic flush.
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM postulaciones")
            cursor.execute("DELETE FROM perfiles_aspirantes")
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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))
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

        self.assertRedirects(
            response,
            reverse("portal"),
            fetch_redirect_response=False,
        )
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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('index')}?next={reverse('dashboard')}",
        )

    def test_role_permissions_are_enforced(self):
        self.client.force_login(self.applicant)

        self.assertEqual(self.client.get(reverse("cargar_curriculo")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)

    def test_hr_pages_are_available_for_hr_user(self):
        self.client.force_login(self.hr_user)
        expected_content = {
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
        self.assertEqual(get_response.status_code, 302)
        self.assertEqual(get_response.url, reverse("dashboard"))
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
        token = email_verification_token.make_token(self.applicant)

        response = self.client.get(
            reverse(
                "verificar_correo",
                kwargs={"uidb64": uid, "token": token},
            )
        )

        self.assertRedirects(response, reverse("index"))
        self.applicant.refresh_from_db()
        self.assertTrue(self.applicant.is_verified)

    def test_public_registration_creates_applicant_and_sends_verification(self):
        response = self.client.post(
            reverse("registrar_aspirante"),
            {
                "first_name": "  Elena ",
                "last_name": " Morales  ",
                "email": "ELENA@EXAMPLE.COM",
                "password1": "Clave-Registro-2026",
                "password2": "Clave-Registro-2026",
                "accept_terms": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verifica tu correo")
        user = Usuario.objects.get(email="elena@example.com")
        self.assertEqual(user.first_name, "Elena")
        self.assertEqual(user.last_name, "Morales")
        self.assertFalse(user.is_verified)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("Clave-Registro-2026"))
        self.assertEqual(user.role_codes(), {"ASPIRANTE"})
        self.assertTrue(PerfilAspirante.objects.filter(usuario=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("multipart/alternative", str(mail.outbox[0].message()))
        self.assertIn("/cuenta/verificar/", mail.outbox[0].body)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        response = self.client.post(
            reverse("registrar_aspirante"),
            {
                "first_name": "Otra",
                "last_name": "Persona",
                "email": "ANDREA@EXAMPLE.COM",
                "password1": "Clave-Registro-2026",
                "password2": "Clave-Registro-2026",
                "accept_terms": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe una cuenta")
        self.assertEqual(Usuario.objects.filter(email__iexact="andrea@example.com").count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    @patch("hello.views.send_verification_email", side_effect=OSError("SMTP caído"))
    def test_registration_survives_email_provider_failure(self, mocked_send):
        response = self.client.post(
            reverse("registrar_aspirante"),
            {
                "first_name": "Elena",
                "last_name": "Morales",
                "email": "elena@example.com",
                "password1": "Clave-Registro-2026",
                "password2": "Clave-Registro-2026",
                "accept_terms": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu cuenta fue creada")
        self.assertTrue(Usuario.objects.filter(email="elena@example.com").exists())
        mocked_send.assert_called_once()

    def test_registration_requires_terms_and_strong_matching_passwords(self):
        response = self.client.post(
            reverse("registrar_aspirante"),
            {
                "first_name": "Elena",
                "last_name": "Morales",
                "email": "elena@example.com",
                "password1": "1234567890",
                "password2": "otra-clave",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Debes aceptar los términos")
        self.assertFalse(Usuario.objects.filter(email="elena@example.com").exists())

    def test_verification_token_is_single_use(self):
        self.applicant.is_verified = False
        self.applicant.save(update_fields=["is_verified"])
        uid = urlsafe_base64_encode(force_bytes(self.applicant.pk))
        token = email_verification_token.make_token(self.applicant)
        url = reverse(
            "verificar_correo",
            kwargs={"uidb64": uid, "token": token},
        )

        self.assertRedirects(self.client.get(url), reverse("index"))
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_resend_verification_does_not_disclose_account_existence(self):
        self.applicant.is_verified = False
        self.applicant.save(update_fields=["is_verified"])
        existing_response = self.client.post(
            reverse("reenviar_verificacion"),
            {"email": self.applicant.email},
        )
        missing_response = self.client.post(
            reverse("reenviar_verificacion"),
            {"email": "missing@example.com"},
        )
        verified_response = self.client.post(
            reverse("reenviar_verificacion"),
            {"email": self.hr_user.email},
        )

        self.assertContains(existing_response, "Revisa tu correo")
        self.assertContains(missing_response, "Revisa tu correo")
        self.assertContains(verified_response, "Revisa tu correo")
        self.assertEqual(len(mail.outbox), 1)


class SaludViewTests(TestCase):
    def test_reports_database_connection(self):
        response = self.client.get(reverse("salud"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"aplicacion": "disponible", "base_de_datos": "conectada"},
        )


class VacancyManagementTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.models = (
            RolUsuario,
            Pais,
            Region,
            Ciudad,
            Profesion,
            Departamento,
            TipoEmpleo,
            ModalidadTrabajo,
            PeriodoSalarial,
            EstadoPlaza,
            NivelEducativo,
            AreaEstudio,
            CategoriaHabilidad,
            Habilidad,
            NivelHabilidad,
            Idioma,
            NivelIdioma,
            Certificacion,
            TipoRequisito,
            Usuario,
            UsuarioRol,
            Plaza,
            HistorialEstadoPlaza,
            RequisitoPlaza,
            RequisitoHabilidad,
            RequisitoIdioma,
            RequisitoCertificacion,
            RequisitoEducacion,
            RequisitoExperiencia,
            RequisitoDisponibilidad,
        )
        with connection.schema_editor() as schema_editor:
            for model in cls.models:
                schema_editor.create_model(model)
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE postulaciones ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, plaza_id BIGINT NOT NULL)"
            )
            cursor.execute(
                "CREATE TABLE resultados_requisitos_evaluacion ("
                "evaluacion_id BIGINT NOT NULL, requisito_id BIGINT NOT NULL, "
                "cumplido BOOLEAN, porcentaje_puntuacion DECIMAL(5,2), "
                "evidencia TEXT, explicacion TEXT, "
                "PRIMARY KEY (evaluacion_id, requisito_id))"
            )

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE resultados_requisitos_evaluacion")
            cursor.execute("DROP TABLE postulaciones")
        with connection.schema_editor() as schema_editor:
            for model in reversed(cls.models):
                schema_editor.delete_model(model)
        super().tearDownClass()

    def setUp(self):
        with connection.cursor() as cursor:
            for table in (
                "postulaciones",
                "resultados_requisitos_evaluacion",
                "requisitos_disponibilidad",
                "requisitos_experiencia",
                "requisitos_educacion",
                "requisitos_certificacion",
                "requisitos_idioma",
                "requisitos_habilidad",
                "requisitos_plaza",
                "historial_estados_plaza",
                "plazas",
                "usuarios_roles",
                "usuarios",
                "roles_usuario",
            ):
                cursor.execute(f'DELETE FROM "{table}"')
        call_command("inicializar_catalogos", verbosity=0)
        self.hr_role = RolUsuario.objects.create(codigo="RRHH", nombre="RR. HH.")
        self.user = Usuario.objects.create_user(
            email="rrhh@example.com",
            password="Clave-Segura-2026",
            first_name="Carlos",
            last_name="Méndez",
            is_active=True,
            is_verified=True,
        )
        UsuarioRol.objects.create(
            usuario=self.user,
            rol=self.hr_role,
            asignado_en=timezone.now(),
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        data = {
            "titulo": "Desarrollador Python",
            "departamento": Departamento.objects.get(nombre="Tecnología").pk,
            "profesion": Profesion.objects.get(nombre="Ingeniería de software").pk,
            "tipo_empleo": TipoEmpleo.objects.get(codigo="TIEMPO_COMPLETO").pk,
            "modalidad_trabajo": ModalidadTrabajo.objects.get(codigo="REMOTO").pk,
            "periodo_salarial": PeriodoSalarial.objects.get(codigo="MES").pk,
            "descripcion": "Construir servicios confiables con Python y Django.",
            "detalle_ubicacion": "Remoto en Guatemala",
            "salario_minimo": "12000.00",
            "salario_maximo": "18000.00",
            "codigo_moneda": "GTQ",
            "cantidad_vacantes": "2",
            "cierra_en": (timezone.now() + timezone.timedelta(days=30)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "anios_experiencia": "3",
            "nivel_educativo": NivelEducativo.objects.get(
                codigo="LICENCIATURA"
            ).pk,
            "area_estudio": AreaEstudio.objects.get(
                nombre="Ingeniería en sistemas"
            ).pk,
            "habilidades_obligatorias": [
                Habilidad.objects.get(nombre="Python").pk,
                Habilidad.objects.get(nombre="Django").pk,
            ],
            "habilidades_deseables": [Habilidad.objects.get(nombre="Docker").pk],
            "idioma": Idioma.objects.get(codigo_iso="en").pk,
            "nivel_idioma": NivelIdioma.objects.get(codigo="B2").pk,
            "requiere_viajar": "on",
            "descripcion_horario": "Lunes a viernes",
        }
        data.update(overrides)
        return data

    def _create_draft(self):
        response = self.client.post(
            reverse("nueva_plaza"),
            {**self._payload(), "accion": "borrador"},
        )
        self.assertEqual(response.status_code, 302)
        return Plaza.objects.get()

    def test_catalog_initialization_is_idempotent(self):
        before = (
            Departamento.objects.count(),
            TipoEmpleo.objects.count(),
            Habilidad.objects.count(),
        )
        call_command("inicializar_catalogos", verbosity=0)
        after = (
            Departamento.objects.count(),
            TipoEmpleo.objects.count(),
            Habilidad.objects.count(),
        )
        self.assertEqual(before, after)

    def test_create_and_publish_vacancy_with_normalized_requirements(self):
        response = self.client.post(
            reverse("nueva_plaza"),
            {**self._payload(), "accion": "publicar"},
        )

        vacancy = Plaza.objects.get()
        self.assertRedirects(response, reverse("detalle_plaza", args=[vacancy.pk]))
        self.assertEqual(vacancy.estado_id, "PUBLICADA")
        self.assertIsNotNone(vacancy.publicado_en)
        requirements = RequisitoPlaza.objects.filter(plaza=vacancy)
        self.assertEqual(requirements.count(), 7)
        self.assertEqual(sum(item.peso for item in requirements), 100)
        self.assertEqual(RequisitoExperiencia.objects.count(), 1)
        self.assertEqual(RequisitoEducacion.objects.count(), 1)
        self.assertEqual(RequisitoHabilidad.objects.count(), 3)
        self.assertEqual(RequisitoIdioma.objects.count(), 1)
        self.assertEqual(RequisitoDisponibilidad.objects.count(), 1)
        self.assertEqual(
            list(
                HistorialEstadoPlaza.objects.values_list(
                    "codigo_estado_nuevo", flat=True
                ).order_by("cambiado_en")
            ),
            ["BORRADOR", "PUBLICADA"],
        )

    def test_edit_vacancy_replaces_requirements_atomically(self):
        vacancy = self._create_draft()
        response = self.client.post(
            reverse("editar_plaza", args=[vacancy.pk]),
            {
                **self._payload(
                    titulo="Desarrollador Django Senior",
                    habilidades_obligatorias=[
                        Habilidad.objects.get(nombre="PostgreSQL").pk
                    ],
                    habilidades_deseables=[],
                    idioma="",
                    nivel_idioma="",
                    requiere_viajar="",
                    descripcion_horario="",
                )
            },
        )

        self.assertRedirects(response, reverse("detalle_plaza", args=[vacancy.pk]))
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.titulo, "Desarrollador Django Senior")
        self.assertEqual(RequisitoHabilidad.objects.count(), 1)
        self.assertEqual(RequisitoIdioma.objects.count(), 0)

    def test_invalid_transition_is_rejected_and_valid_flow_is_recorded(self):
        vacancy = self._create_draft()
        with self.assertRaises(ValidationError):
            transition_vacancy(vacancy.pk, "PAUSADA", self.user)

        transition_vacancy(vacancy.pk, "PUBLICADA", self.user)
        transition_vacancy(vacancy.pk, "PAUSADA", self.user, "Revisión interna")
        transition_vacancy(vacancy.pk, "PUBLICADA", self.user)
        transition_vacancy(vacancy.pk, "CERRADA", self.user)
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.estado_id, "CERRADA")
        self.assertEqual(HistorialEstadoPlaza.objects.filter(plaza=vacancy).count(), 5)
        with self.assertRaises(ValidationError):
            transition_vacancy(vacancy.pk, "PUBLICADA", self.user)

    def test_state_endpoint_updates_vacancy_and_rejects_get(self):
        vacancy = self._create_draft()
        state_url = reverse(
            "cambiar_estado_plaza",
            args=[vacancy.pk, "PUBLICADA"],
        )

        self.assertRedirects(
            self.client.get(state_url),
            reverse("detalle_plaza", args=[vacancy.pk]),
        )
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.estado_id, "BORRADOR")

        self.assertRedirects(
            self.client.post(state_url, {"motivo": "Aprobada por RR. HH."}),
            reverse("detalle_plaza", args=[vacancy.pk]),
        )
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.estado_id, "PUBLICADA")
        self.assertEqual(
            HistorialEstadoPlaza.objects.latest("cambiado_en").motivo,
            "Aprobada por RR. HH.",
        )

    def test_closed_vacancy_cannot_be_edited(self):
        vacancy = self._create_draft()
        transition_vacancy(vacancy.pk, "CERRADA", self.user)

        response = self.client.get(reverse("editar_plaza", args=[vacancy.pk]))

        self.assertRedirects(response, reverse("detalle_plaza", args=[vacancy.pk]))

    def test_publish_requires_at_least_one_requirement(self):
        payload = self._payload(
            anios_experiencia="",
            nivel_educativo="",
            area_estudio="",
            habilidades_obligatorias=[],
            habilidades_deseables=[],
            idioma="",
            nivel_idioma="",
            requiere_viajar="",
            descripcion_horario="",
        )

        response = self.client.post(
            reverse("nueva_plaza"),
            {**payload, "accion": "publicar"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agrega al menos un requisito")
        self.assertEqual(Plaza.objects.count(), 0)

    def test_list_supports_search_status_and_pagination_context(self):
        vacancy = self._create_draft()
        response = self.client.get(
            reverse("plazas"),
            {"q": "Python", "estado": "BORRADOR"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, vacancy.titulo)
        self.assertEqual(response.context["page"].paginator.count, 1)

    def test_dashboard_uses_real_vacancy_counts(self):
        vacancy = self._create_draft()
        transition_vacancy(vacancy.pk, "PUBLICADA", self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_vacancies"], 1)
        self.assertEqual(response.context["pending_vacancies"], 0)
        self.assertContains(response, vacancy.titulo)

    def test_salary_and_duplicate_skill_validation(self):
        python_id = Habilidad.objects.get(nombre="Python").pk
        response = self.client.post(
            reverse("nueva_plaza"),
            {
                **self._payload(
                    salario_minimo="20000",
                    salario_maximo="10000",
                    habilidades_obligatorias=[python_id],
                    habilidades_deseables=[python_id],
                ),
                "accion": "borrador",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "salario máximo")
        self.assertContains(response, "obligatoria y deseable")
        self.assertEqual(Plaza.objects.count(), 0)
