import shutil
import tempfile
from unittest.mock import patch
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from reclutamiento.candidates import save_curriculum
from reclutamiento.applications import create_application, transition_application
from reclutamiento.models import (
    AreaEstudio,
    CategoriaHabilidad,
    Certificacion,
    CertificacionAspirante,
    Ciudad,
    Curriculo,
    Departamento,
    Entrevista,
    EstadoEntrevista,
    EstadoPlaza,
    EstadoPostulacion,
    ExperienciaLaboral,
    FormacionAcademica,
    Habilidad,
    HabilidadAspirante,
    HistorialEstadoPostulacion,
    Idioma,
    IdiomaAspirante,
    Institucion,
    ModalidadTrabajo,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    Pais,
    PerfilAspirante,
    PerfilPersonal,
    PeriodoSalarial,
    Plaza,
    Postulacion,
    Profesion,
    ProveedorAlmacenamiento,
    Region,
    RolUsuario,
    TipoEmpleo,
    Usuario,
    UsuarioRol,
)


class ApplicantWorkflowTests(TransactionTestCase):
    models = (
        RolUsuario,
        Pais,
        Region,
        Ciudad,
        Departamento,
        Profesion,
        NivelEducativo,
        AreaEstudio,
        Institucion,
        CategoriaHabilidad,
        Habilidad,
        NivelHabilidad,
        Idioma,
        NivelIdioma,
        Certificacion,
        TipoEmpleo,
        ModalidadTrabajo,
        PeriodoSalarial,
        ProveedorAlmacenamiento,
        EstadoPlaza,
        EstadoPostulacion,
        EstadoEntrevista,
        Usuario,
        UsuarioRol,
        PerfilPersonal,
        PerfilAspirante,
        ExperienciaLaboral,
        FormacionAcademica,
        HabilidadAspirante,
        IdiomaAspirante,
        CertificacionAspirante,
        Plaza,
        Curriculo,
        Postulacion,
        HistorialEstadoPostulacion,
        Entrevista,
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as schema_editor:
            for model in cls.models:
                schema_editor.create_model(model)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema_editor:
            for model in reversed(cls.models):
                schema_editor.delete_model(model)
        super().tearDownClass()

    def setUp(self):
        with connection.cursor() as cursor:
            for model in reversed(self.models):
                cursor.execute(f'DELETE FROM "{model._meta.db_table}"')
        self.upload_root = Path(tempfile.mkdtemp())
        self.settings_override = override_settings(PRIVATE_UPLOAD_ROOT=self.upload_root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.upload_root, True)

        applicant_role = RolUsuario.objects.create(codigo="ASPIRANTE", nombre="Aspirante")
        hr_role = RolUsuario.objects.create(codigo="RRHH", nombre="RR. HH.")
        self.applicant = self._user("aspirante@example.com", applicant_role)
        self.other_applicant = self._user("otro@example.com", applicant_role)
        self.hr_user = self._user("rrhh@example.com", hr_role)
        self.profile = PerfilAspirante.objects.create(
            usuario=self.applicant,
            creado_en=timezone.now(),
            actualizado_en=timezone.now(),
        )
        self.other_profile = PerfilAspirante.objects.create(
            usuario=self.other_applicant,
            creado_en=timezone.now(),
            actualizado_en=timezone.now(),
        )
        self.department = Departamento.objects.create(nombre="Tecnología", activo=True)
        self.employment_type = TipoEmpleo.objects.create(
            codigo="TIEMPO_COMPLETO", nombre="Tiempo completo"
        )
        self.work_mode = ModalidadTrabajo.objects.create(
            codigo="REMOTO", nombre="Remoto"
        )
        EstadoPlaza.objects.create(codigo="PUBLICADA", nombre="Activa")
        for code, name, final in (
            ("ENVIADA", "Enviada", False),
            ("EN_REVISION", "En revisión", False),
            ("PRESELECCIONADA", "Preseleccionada", False),
            ("ENTREVISTA", "Entrevista", False),
            ("OFERTA_ENVIADA", "Oferta enviada", False),
            ("CONTRATADA", "Contratada", True),
            ("RECHAZADA", "Rechazada", True),
            ("RETIRADA", "Retirada", True),
        ):
            EstadoPostulacion.objects.create(codigo=code, nombre=name, es_final=final)
        for code, name, final in (
            ("PROGRAMADA", "Programada", False),
            ("CONFIRMADA", "Confirmada", False),
            ("COMPLETADA", "Completada", True),
            ("CANCELADA", "Cancelada", True),
            ("NO_ASISTIO", "No asistió", True),
        ):
            EstadoEntrevista.objects.create(codigo=code, nombre=name, es_final=final)
        self.provider = ProveedorAlmacenamiento.objects.create(
            codigo="LOCAL_PRIVADO", nombre="Local privado"
        )
        now = timezone.now()
        self.vacancy = Plaza.objects.create(
            departamento=self.department,
            creado_por=self.hr_user,
            tipo_empleo=self.employment_type,
            modalidad_trabajo=self.work_mode,
            estado_id="PUBLICADA",
            titulo="Desarrollador Python",
            descripcion="Construcción de aplicaciones Django.",
            cantidad_vacantes=1,
            publicado_en=now,
            cierra_en=now + timezone.timedelta(days=10),
            creado_en=now,
            actualizado_en=now,
        )
        self.curriculum = self._curriculum(self.profile, "curriculo.pdf")

    def _user(self, email, role):
        user = Usuario.objects.create_user(
            email=email,
            password="Clave-Segura-2026",
            first_name="Nombre",
            last_name="Prueba",
            is_active=True,
            is_verified=True,
        )
        UsuarioRol.objects.create(usuario=user, rol=role, asignado_en=timezone.now())
        return user

    def _curriculum(self, profile, name):
        key = f"{profile.pk}/{name}"
        path = self.upload_root / "curriculos" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4\n%%EOF")
        return Curriculo.objects.create(
            aspirante=profile,
            proveedor_almacenamiento=self.provider,
            clave_objeto=key,
            nombre_archivo_original=name,
            tamano_bytes=14,
            suma_sha256="a" * 64,
            cargado_en=timezone.now(),
            activo=True,
        )

    def test_profile_update_and_owned_experience(self):
        self.client.force_login(self.applicant)
        profession = Profesion.objects.create(nombre="Ingeniería de software")
        response = self.client.post(
            reverse("perfil_aspirante"),
            {
                "first_name": "Andrea",
                "last_name": "Ruiz",
                "profesion": profession.pk,
                "telefono": "5555-0101",
                "resumen_profesional": "Desarrolladora de software.",
                "acepta_viajar": "on",
            },
        )
        self.assertRedirects(response, reverse("perfil_aspirante"))
        self.profile.refresh_from_db()
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.first_name, "Andrea")
        self.assertEqual(self.profile.profesion, profession)
        self.assertTrue(self.profile.acepta_viajar)

        experience = ExperienciaLaboral.objects.create(
            aspirante=self.other_profile,
            empresa="Empresa ajena",
            puesto="Analista",
            fecha_inicio=timezone.localdate(),
        )
        response = self.client.get(
            reverse("editar_registro_perfil", args=["experiencia", experience.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_pdf_validation_and_private_download_permissions(self):
        self.client.force_login(self.applicant)
        invalid = SimpleUploadedFile(
            "falso.pdf", b"contenido de texto", content_type="application/pdf"
        )
        response = self.client.post(reverse("cargar_curriculo"), {"archivo": invalid})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no corresponde a un PDF")

        self.client.force_login(self.other_applicant)
        self.assertEqual(
            self.client.get(reverse("descargar_curriculo", args=[self.curriculum.pk])).status_code,
            404,
        )
        self.client.force_login(self.hr_user)
        response = self.client.get(
            reverse("descargar_curriculo", args=[self.curriculum.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_backblaze_is_used_when_enabled(self):
        provider = ProveedorAlmacenamiento.objects.create(
            codigo="BACKBLAZE_B2",
            nombre="Almacenamiento privado Backblaze B2",
        )
        uploaded = SimpleUploadedFile(
            "nuevo.pdf",
            b"%PDF-1.4\n%%EOF",
            content_type="application/pdf",
        )
        settings = {
            "BACKBLAZE_ENABLED": True,
            "BACKBLAZE_APPLICATION_KEY_ID": "key-id",
            "BACKBLAZE_APPLICATION_KEY": "application-key",
            "BACKBLAZE_BUCKET_NAME": "sistema-cv-curriculos-privados",
            "BACKBLAZE_ENDPOINT_URL": "https://s3.eu-central-003.backblazeb2.com",
            "BACKBLAZE_OBJECT_PREFIX": "curriculos",
        }
        with override_settings(**settings), patch(
            "reclutamiento.candidates.upload_backblaze_object"
        ) as upload:
            curriculum = save_curriculum(uploaded, self.profile)

        self.assertEqual(curriculum.proveedor_almacenamiento, provider)
        self.assertTrue(curriculum.clave_objeto.startswith("curriculos/"))
        upload.assert_called_once()

    def test_backblaze_download_uses_temporary_url(self):
        provider = ProveedorAlmacenamiento.objects.create(
            codigo="BACKBLAZE_B2",
            nombre="Almacenamiento privado Backblaze B2",
        )
        curriculum = Curriculo.objects.create(
            aspirante=self.profile,
            proveedor_almacenamiento=provider,
            clave_objeto="curriculos/1/archivo.pdf",
            nombre_archivo_original="archivo.pdf",
            tamano_bytes=14,
            suma_sha256="a" * 64,
            cargado_en=timezone.now(),
            activo=True,
        )
        self.client.force_login(self.hr_user)
        with patch(
            "hello.views.backblaze_download_url",
            return_value="https://signed.example/curriculo",
        ) as download_url:
            response = self.client.get(
                reverse("descargar_curriculo", args=[curriculum.pk])
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://signed.example/curriculo")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        download_url.assert_called_once_with("curriculos/1/archivo.pdf", "archivo.pdf")

    def test_hr_can_view_reports(self):
        create_application(self.vacancy.pk, self.profile)
        self.client.force_login(self.hr_user)

        response = self.client.get(reverse("reportes"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_applications"], 1)
        self.assertContains(response, "Estado de las postulaciones")
        self.assertContains(response, "Plazas con mayor actividad")

    def test_hr_can_export_report_as_csv(self):
        create_application(self.vacancy.pk, self.profile)
        self.client.force_login(self.hr_user)

        response = self.client.get(reverse("exportar_reporte"), {"periodo": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("reporte-reclutamiento-all.csv", response["Content-Disposition"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("Aspirante,Correo,Plaza", content)
        self.assertIn("Desarrollador Python", content)

    def test_hr_can_update_account_settings(self):
        self.client.force_login(self.hr_user)

        response = self.client.post(
            reverse("configuracion"),
            {
                "first_name": "Sofía",
                "last_name": "Herrera",
                "departamento": self.department.pk,
                "cargo": "Especialista de selección",
                "telefono": "5555-0101",
            },
        )

        self.assertRedirects(response, reverse("configuracion"))
        self.hr_user.refresh_from_db()
        profile = PerfilPersonal.objects.get(usuario=self.hr_user)
        self.assertEqual(self.hr_user.first_name, "Sofía")
        self.assertEqual(profile.cargo, "Especialista de selección")

    def test_account_settings_reject_invalid_phone(self):
        self.client.force_login(self.hr_user)

        response = self.client.post(
            reverse("configuracion"),
            {
                "first_name": "Sofía",
                "last_name": "Herrera",
                "departamento": self.department.pk,
                "cargo": "Especialista de selección",
                "telefono": "teléfono inválido",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "número de teléfono válido")
        self.assertFalse(PerfilPersonal.objects.filter(usuario=self.hr_user).exists())

    def test_application_creation_prevents_duplicates_and_records_history(self):
        application = create_application(self.vacancy.pk, self.profile, "Me interesa.")
        self.assertEqual(application.estado_id, "ENVIADA")
        self.assertEqual(application.curriculo, self.curriculum)
        self.assertEqual(
            HistorialEstadoPostulacion.objects.get().codigo_estado_nuevo,
            "ENVIADA",
        )
        with self.assertRaises(ValidationError):
            create_application(self.vacancy.pk, self.profile)

    def test_applicant_can_withdraw_but_cannot_manage_pipeline(self):
        application = create_application(self.vacancy.pk, self.profile)
        with self.assertRaises(ValidationError):
            transition_application(application.pk, "EN_REVISION", self.applicant)
        transition_application(application.pk, "EN_REVISION", self.hr_user)
        transition_application(application.pk, "RETIRADA", self.applicant)
        application.refresh_from_db()
        self.assertEqual(application.estado_id, "RETIRADA")
        self.assertIsNotNone(application.retirado_en)
        self.assertEqual(
            HistorialEstadoPostulacion.objects.filter(postulacion=application).count(),
            3,
        )

    def test_hr_can_schedule_interview_from_shortlist(self):
        application = create_application(self.vacancy.pk, self.profile)
        transition_application(application.pk, "EN_REVISION", self.hr_user)
        transition_application(application.pk, "PRESELECCIONADA", self.hr_user)
        self.client.force_login(self.hr_user)
        start = timezone.now() + timezone.timedelta(days=2)
        response = self.client.post(
            reverse("programar_entrevista", args=[application.pk]),
            {
                "inicia_en": start.strftime("%Y-%m-%dT%H:%M"),
                "termina_en": (start + timezone.timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M"
                ),
                "zona_horaria": "America/Guatemala",
                "url_reunion": "https://meet.example.com/entrevista",
            },
        )
        self.assertRedirects(
            response,
            reverse("detalle_postulacion", args=[application.pk]),
        )
        application.refresh_from_db()
        self.assertEqual(application.estado_id, "ENTREVISTA")
        self.assertEqual(Entrevista.objects.get().estado_id, "PROGRAMADA")

    def test_applicant_and_hr_pages_render_real_data(self):
        application = create_application(self.vacancy.pk, self.profile)
        self.client.force_login(self.applicant)
        for route_name, args, content in (
            ("portal", (), "Desarrollador Python"),
            ("perfil_aspirante", (), "Tu historia"),
            ("oportunidades", (), "Desarrollador Python"),
            ("mis_postulaciones", (), "Desarrollador Python"),
            ("mi_postulacion", (application.pk,), "Historial del proceso"),
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, content)

        self.client.force_login(self.hr_user)
        self.assertContains(self.client.get(reverse("postulaciones")), "Desarrollador Python")
        self.assertContains(
            self.client.get(reverse("detalle_postulacion", args=[application.pk])),
            "Historial de estados",
        )
