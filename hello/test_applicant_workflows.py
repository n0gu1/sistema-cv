import shutil
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch
from pathlib import Path

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from reclutamiento.candidates import save_curriculum
from reclutamiento.applications import create_application, transition_application
from reclutamiento.ai_analysis import analyze_application, enqueue_application_analysis
from reclutamiento.forms import FormularioEntrevista
from reclutamiento.tasks import process_application_analysis
from reclutamiento.models import (
    AnalisisCV,
    AreaEstudio,
    CanalNotificacion,
    CategoriaHabilidad,
    Certificacion,
    CertificacionAspirante,
    CertificacionAnalisisCV,
    Ciudad,
    Curriculo,
    DatosPersonalesAnalisisCV,
    Departamento,
    EducacionAnalisisCV,
    Entrevista,
    EstadoEntrevista,
    EstadoEntrega,
    EstadoPlaza,
    EstadoPostulacion,
    EstadoProcesamiento,
    EvaluacionPostulacion,
    ExperienciaAnalisisCV,
    ExperienciaLaboral,
    FormacionAcademica,
    Habilidad,
    HabilidadAspirante,
    HabilidadAnalisisCV,
    HistorialEstadoPostulacion,
    HistorialEstadoPlaza,
    Idioma,
    IdiomaAspirante,
    IdiomaAnalisisCV,
    Institucion,
    ModalidadTrabajo,
    ModeloIA,
    MotorAnalisis,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    Notificacion,
    Pais,
    PerfilAspirante,
    PerfilPersonal,
    PeriodoSalarial,
    Plaza,
    Postulacion,
    Profesion,
    ProveedorAlmacenamiento,
    Region,
    RequisitoCertificacion,
    RequisitoDisponibilidad,
    RequisitoEducacion,
    RequisitoExperiencia,
    RequisitoHabilidad,
    RequisitoIdioma,
    RequisitoPlaza,
    ResultadoRequisitoEvaluacion,
    RolUsuario,
    TipoEmpleo,
    TipoNotificacion,
    TipoRequisito,
    Usuario,
    UsuarioRol,
    EntregaNotificacion,
    IntentoEntregaNotificacion,
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
        EstadoProcesamiento,
        ModeloIA,
        MotorAnalisis,
        TipoRequisito,
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
        HistorialEstadoPlaza,
        RequisitoPlaza,
        RequisitoHabilidad,
        RequisitoIdioma,
        RequisitoCertificacion,
        RequisitoEducacion,
        RequisitoExperiencia,
        RequisitoDisponibilidad,
        Curriculo,
        AnalisisCV,
        DatosPersonalesAnalisisCV,
        ExperienciaAnalisisCV,
        EducacionAnalisisCV,
        HabilidadAnalisisCV,
        IdiomaAnalisisCV,
        CertificacionAnalisisCV,
        Postulacion,
        HistorialEstadoPostulacion,
        EvaluacionPostulacion,
        ResultadoRequisitoEvaluacion,
        Entrevista,
        TipoNotificacion,
        CanalNotificacion,
        EstadoEntrega,
        Notificacion,
        EntregaNotificacion,
        IntentoEntregaNotificacion,
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
        EstadoPlaza.objects.create(codigo="CERRADA", nombre="Cerrada", es_final=True)
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
        for code, name in (
            ("CONFIRMACION_POSTULACION", "Confirmación de postulación"),
            ("CAMBIO_ESTADO", "Cambio de estado"),
            ("INVITACION_ENTREVISTA", "Invitación a entrevista"),
        ):
            TipoNotificacion.objects.create(codigo=code, nombre=name)
        for code, name in (
            ("APLICACION", "Aplicación"),
            ("CORREO", "Correo electrónico"),
        ):
            CanalNotificacion.objects.create(codigo=code, nombre=name)
        for code, name, final in (
            ("PENDIENTE", "Pendiente", False),
            ("PROCESANDO", "Procesando", False),
            ("ENVIADO", "Enviado", True),
            ("FALLIDO", "Fallido", True),
        ):
            EstadoEntrega.objects.create(codigo=code, nombre=name, es_final=final)
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

    def _interview(self, application, state="PROGRAMADA"):
        start = timezone.now() + timezone.timedelta(days=3)
        return Entrevista.objects.create(
            postulacion=application,
            creado_por=self.hr_user,
            estado_id=state,
            inicia_en=start,
            termina_en=start + timezone.timedelta(hours=1),
            zona_horaria="America/Guatemala",
            detalle_ubicacion="Oficina central",
            creado_en=timezone.now(),
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

    def test_hr_can_view_complete_applicant_profile(self):
        profession = Profesion.objects.create(nombre="Ingeniería de software")
        self.profile.profesion = profession
        self.profile.telefono = "5555-0101"
        self.profile.resumen_profesional = "Desarrolladora con experiencia web."
        self.profile.save(
            update_fields=("profesion", "telefono", "resumen_profesional")
        )
        ExperienciaLaboral.objects.create(
            aspirante=self.profile,
            profesion=profession,
            empresa="Empresa de prueba",
            puesto="Desarrolladora backend",
            fecha_inicio=timezone.localdate(),
            descripcion="Construcción de APIs.",
        )
        institution = Institucion.objects.create(nombre="Universidad de prueba")
        education_level = NivelEducativo.objects.create(
            codigo="LICENCIATURA",
            nombre="Licenciatura",
            orden_nivel=1,
        )
        FormacionAcademica.objects.create(
            aspirante=self.profile,
            institucion=institution,
            nivel_educativo=education_level,
            titulo_obtenido="Ingeniera de software",
        )
        skill = Habilidad.objects.create(nombre="Django", activo=True)
        skill_level = NivelHabilidad.objects.create(
            codigo="AVANZADO",
            nombre="Avanzado",
            orden_nivel=1,
        )
        HabilidadAspirante.objects.create(
            aspirante=self.profile,
            habilidad=skill,
            nivel_habilidad=skill_level,
            anios_experiencia="3.0",
        )
        language = Idioma.objects.create(codigo_iso="en", nombre="Inglés")
        language_level = NivelIdioma.objects.create(
            codigo="B2",
            nombre="Intermedio alto",
            orden_nivel=1,
        )
        IdiomaAspirante.objects.create(
            aspirante=self.profile,
            idioma=language,
            nivel_idioma=language_level,
        )
        certification = Certificacion.objects.create(
            nombre="Django Certified",
            organizacion_emisora="Python Institute",
        )
        CertificacionAspirante.objects.create(
            aspirante=self.profile,
            certificacion=certification,
            codigo_credencial="CERT-001",
        )

        self.client.force_login(self.hr_user)
        response = self.client.get(
            reverse("detalle_aspirante", args=[self.profile.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_percentage"], 100)
        for content in (
            "Nombre Prueba",
            "Ingeniería de software",
            "Desarrolladora backend",
            "Universidad de prueba",
            "Django",
            "Inglés",
            "Django Certified",
            "curriculo.pdf",
        ):
            with self.subTest(content=content):
                self.assertContains(response, content)
        self.assertContains(
            self.client.get(reverse("aspirantes")),
            reverse("detalle_aspirante", args=[self.profile.pk]),
        )

        self.client.force_login(self.applicant)
        self.assertEqual(
            self.client.get(
                reverse("detalle_aspirante", args=[self.profile.pk])
            ).status_code,
            403,
        )

    def test_portal_lists_all_pending_profile_sections(self):
        self.client.force_login(self.applicant)

        response = self.client.get(reverse("portal"))

        pending_keys = {
            section["key"] for section in response.context["pending_profile_sections"]
        }
        self.assertEqual(
            pending_keys,
            {
                "datos",
                "experiencia",
                "formacion",
                "habilidades",
                "idiomas",
                "certificaciones",
            },
        )
        self.assertNotIn(
            "curriculo",
            pending_keys,
        )
        for label in (
            "Datos personales",
            "Experiencia laboral",
            "Formación académica",
            "Habilidades",
            "Idiomas",
            "Certificaciones",
        ):
            with self.subTest(label=label):
                self.assertContains(response, label)
        self.assertContains(
            response,
            reverse("nuevo_registro_perfil", args=["formacion"]),
        )

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

    def test_application_confirmation_creates_internal_and_email_deliveries(self):
        mail.outbox.clear()

        application = create_application(self.vacancy.pk, self.profile)

        notification = Notificacion.objects.get(
            postulacion=application,
            tipo_id="CONFIRMACION_POSTULACION",
        )
        deliveries = {
            delivery.canal_id: delivery
            for delivery in EntregaNotificacion.objects.filter(
                notificacion=notification
            )
        }
        self.assertEqual(set(deliveries), {"APLICACION", "CORREO"})
        self.assertEqual(deliveries["APLICACION"].estado_id, "ENVIADO")
        self.assertEqual(deliveries["CORREO"].estado_id, "ENVIADO")
        self.assertTrue(
            IntentoEntregaNotificacion.objects.filter(
                entrega=deliveries["CORREO"], exitoso=True
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Postulación recibida")
        self.assertIn("Desarrollador Python", mail.outbox[0].body)
        self.assertIn("multipart/alternative", str(mail.outbox[0].message()))

    def test_application_status_change_notifies_the_applicant(self):
        application = create_application(self.vacancy.pk, self.profile)
        mail.outbox.clear()

        transition_application(application.pk, "EN_REVISION", self.hr_user)

        notification = Notificacion.objects.get(
            postulacion=application,
            tipo_id="CAMBIO_ESTADO",
        )
        self.assertIn("Enviada", notification.mensaje)
        self.assertIn("En revisión", notification.mensaje)
        self.assertEqual(notification.usuario_destinatario_id, self.applicant.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Actualización de tu postulación")

    def test_hiring_respects_vacancy_limit(self):
        self._curriculum(self.other_profile, "otro-curriculo.pdf")
        second_application = create_application(self.vacancy.pk, self.other_profile)

        first_application = create_application(self.vacancy.pk, self.profile)
        for target in (
            "EN_REVISION",
            "PRESELECCIONADA",
            "ENTREVISTA",
            "OFERTA_ENVIADA",
            "CONTRATADA",
        ):
            transition_application(first_application.pk, target, self.hr_user)

        self.vacancy.refresh_from_db()
        self.assertEqual(self.vacancy.estado_id, "CERRADA")
        for target in (
            "EN_REVISION",
            "PRESELECCIONADA",
            "ENTREVISTA",
            "OFERTA_ENVIADA",
        ):
            transition_application(second_application.pk, target, self.hr_user)

        with self.assertRaisesRegex(ValidationError, "cantidad de vacantes"):
            transition_application(
                second_application.pk,
                "CONTRATADA",
                self.hr_user,
            )

        second_application.refresh_from_db()
        self.assertEqual(second_application.estado_id, "OFERTA_ENVIADA")
        self.assertEqual(
            Postulacion.objects.filter(
                plaza=self.vacancy,
                estado_id="CONTRATADA",
            ).count(),
            1,
        )

    def test_expired_vacancies_are_excluded_from_active_metrics(self):
        now = timezone.now()
        expired_vacancy = Plaza.objects.create(
            departamento=self.department,
            creado_por=self.hr_user,
            tipo_empleo=self.employment_type,
            modalidad_trabajo=self.work_mode,
            estado_id="PUBLICADA",
            titulo="Plaza vencida",
            descripcion="Esta plaza ya no está vigente.",
            cantidad_vacantes=1,
            publicado_en=now - timezone.timedelta(days=20),
            cierra_en=now - timezone.timedelta(days=1),
            creado_en=now - timezone.timedelta(days=20),
            actualizado_en=now - timezone.timedelta(days=1),
        )
        self.client.force_login(self.hr_user)

        dashboard = self.client.get(reverse("dashboard"))
        report = self.client.get(reverse("reportes"), {"periodo": "all"})

        self.assertEqual(dashboard.context["active_vacancies"], 1)
        self.assertEqual(report.context["active_vacancies"], 1)
        self.assertNotIn(
            expired_vacancy,
            dashboard.context["priority_vacancies"],
        )

    def test_applicant_can_list_and_mark_notifications_as_read(self):
        application = create_application(self.vacancy.pk, self.profile)
        notification = Notificacion.objects.get(postulacion=application)
        self.client.force_login(self.applicant)

        response = self.client.get(reverse("notificaciones"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["unread_count"], 1)
        self.assertContains(response, "Postulación recibida")
        response = self.client.post(
            reverse("marcar_notificacion_leida", args=[notification.pk])
        )
        self.assertRedirects(response, reverse("notificaciones"))
        notification.refresh_from_db()
        self.assertIsNotNone(notification.leido_en)
        self.assertEqual(
            self.client.get(reverse("notificaciones")).context["unread_count"],
            0,
        )

    @patch(
        "reclutamiento.notifications.EmailMultiAlternatives.send",
        side_effect=OSError("SMTP caído"),
    )
    def test_email_failure_keeps_application_and_records_failed_delivery(
        self, send
    ):
        application = create_application(self.vacancy.pk, self.profile)
        notification = Notificacion.objects.get(postulacion=application)
        delivery = EntregaNotificacion.objects.get(
            notificacion=notification,
            canal_id="CORREO",
        )

        self.assertTrue(Postulacion.objects.filter(pk=application.pk).exists())
        self.assertEqual(delivery.estado_id, "FALLIDO")
        attempt = IntentoEntregaNotificacion.objects.get(entrega=delivery)
        self.assertFalse(attempt.exitoso)
        self.assertIn("SMTP caído", attempt.mensaje_error)
        send.assert_called_once()

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
        interview = Entrevista.objects.get()
        self.assertEqual(interview.estado_id, "PROGRAMADA")
        invitation = Notificacion.objects.get(
            postulacion=application,
            entrevista=interview,
            tipo_id="INVITACION_ENTREVISTA",
        )
        self.assertIn("Desarrollador Python", invitation.mensaje)
        self.assertIn("meet.example.com/entrevista", invitation.mensaje)
        mail.outbox.clear()
        response = self.client.post(
            reverse("cambiar_estado_entrevista", args=[interview.pk]),
            {"estado": "CONFIRMADA"},
        )
        self.assertRedirects(
            response,
            reverse("detalle_postulacion", args=[application.pk]),
        )
        interview.refresh_from_db()
        self.assertEqual(interview.estado_id, "CONFIRMADA")
        interview_notification = Notificacion.objects.filter(
            entrevista=interview,
            tipo_id="CAMBIO_ESTADO",
        ).latest("pk")
        self.assertIn("Programada", interview_notification.mensaje)
        self.assertIn("Confirmada", interview_notification.mensaje)
        self.assertEqual(mail.outbox[0].subject, "Actualización de entrevista")

        self.client.force_login(self.applicant)
        response = self.client.get(
            reverse("mi_postulacion", args=[application.pk])
        )
        self.assertEqual(len(response.context["entrevistas"]), 1)
        self.assertContains(response, "America/Guatemala")

    def test_interview_form_is_only_available_in_interview_states(self):
        application = create_application(self.vacancy.pk, self.profile)
        self.client.force_login(self.hr_user)

        self.assertNotContains(
            self.client.get(reverse("detalle_postulacion", args=[application.pk])),
            "Programar entrevista",
        )
        transition_application(application.pk, "EN_REVISION", self.hr_user)
        self.assertNotContains(
            self.client.get(reverse("detalle_postulacion", args=[application.pk])),
            "Programar entrevista",
        )
        transition_application(application.pk, "PRESELECCIONADA", self.hr_user)
        self.assertContains(
            self.client.get(reverse("detalle_postulacion", args=[application.pk])),
            "Programar entrevista",
        )

    def test_invalid_interview_form_preserves_errors_and_submitted_data(self):
        application = create_application(self.vacancy.pk, self.profile)
        transition_application(application.pk, "EN_REVISION", self.hr_user)
        transition_application(application.pk, "PRESELECCIONADA", self.hr_user)
        self.client.force_login(self.hr_user)
        start = timezone.now() + timezone.timedelta(days=2)
        payload = {
            "inicia_en": start.strftime("%Y-%m-%dT%H:%M"),
            "termina_en": (start + timezone.timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "zona_horaria": "America/Guatemala",
            "notas": "Traer documento de identidad.",
        }

        response = self.client.post(
            reverse("programar_entrevista", args=[application.pk]),
            payload,
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["interview_form"]
        self.assertTrue(form.is_bound)
        self.assertEqual(form.data["notas"], payload["notas"])
        self.assertIn("Indica una ubicación o un enlace", response.content.decode())
        self.assertFalse(Entrevista.objects.exists())

    def test_interview_form_validates_future_date_and_timezone(self):
        future = "2035-01-15T09:00"
        valid = FormularioEntrevista(
            data={
                "inicia_en": future,
                "termina_en": "2035-01-15T10:00",
                "zona_horaria": "America/Guatemala",
                "detalle_ubicacion": "Oficina central",
            }
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        start = valid.cleaned_data["inicia_en"]
        self.assertEqual(start.tzinfo.key, "America/Guatemala")
        self.assertEqual(start.replace(tzinfo=None), datetime(2035, 1, 15, 9))

        past = FormularioEntrevista(
            data={
                "inicia_en": "2020-01-15T09:00",
                "termina_en": "2020-01-15T10:00",
                "zona_horaria": "America/Guatemala",
                "detalle_ubicacion": "Oficina central",
            }
        )
        self.assertFalse(past.is_valid())
        self.assertIn("futuro", past.errors["inicia_en"][0])

        invalid_timezone = FormularioEntrevista(
            data={
                "inicia_en": future,
                "termina_en": "2035-01-15T10:00",
                "zona_horaria": "Zona/Inexistente",
                "detalle_ubicacion": "Oficina central",
            }
        )
        self.assertFalse(invalid_timezone.is_valid())
        self.assertIn("IANA", invalid_timezone.errors["zona_horaria"][0])

    def test_rejecting_application_cancels_active_interviews(self):
        application = create_application(self.vacancy.pk, self.profile)
        transition_application(application.pk, "EN_REVISION", self.hr_user)
        transition_application(application.pk, "PRESELECCIONADA", self.hr_user)
        transition_application(application.pk, "ENTREVISTA", self.hr_user)
        scheduled = self._interview(application)
        confirmed = self._interview(application, "CONFIRMADA")
        completed = self._interview(application, "COMPLETADA")

        transition_application(application.pk, "RECHAZADA", self.hr_user)

        scheduled.refresh_from_db()
        confirmed.refresh_from_db()
        completed.refresh_from_db()
        self.assertEqual(scheduled.estado_id, "CANCELADA")
        self.assertEqual(confirmed.estado_id, "CANCELADA")
        self.assertEqual(completed.estado_id, "COMPLETADA")

    def test_withdrawing_application_cancels_active_interviews(self):
        application = create_application(self.vacancy.pk, self.profile)
        transition_application(application.pk, "EN_REVISION", self.hr_user)
        transition_application(application.pk, "PRESELECCIONADA", self.hr_user)
        transition_application(application.pk, "ENTREVISTA", self.hr_user)
        interview = self._interview(application)

        transition_application(application.pk, "RETIRADA", self.applicant)

        interview.refresh_from_db()
        self.assertEqual(interview.estado_id, "CANCELADA")

    def test_hiring_application_cancels_active_interviews(self):
        application = create_application(self.vacancy.pk, self.profile)
        for target in (
            "EN_REVISION",
            "PRESELECCIONADA",
            "ENTREVISTA",
            "OFERTA_ENVIADA",
        ):
            transition_application(application.pk, target, self.hr_user)
        interview = self._interview(application, "CONFIRMADA")

        transition_application(application.pk, "CONTRATADA", self.hr_user)

        interview.refresh_from_db()
        self.assertEqual(interview.estado_id, "CANCELADA")

    def test_application_must_have_offer_before_hiring(self):
        application = create_application(self.vacancy.pk, self.profile)
        for target in ("EN_REVISION", "PRESELECCIONADA", "ENTREVISTA"):
            transition_application(application.pk, target, self.hr_user)

        with self.assertRaisesRegex(ValidationError, "oferta enviada"):
            transition_application(application.pk, "CONTRATADA", self.hr_user)

        application.refresh_from_db()
        self.assertEqual(application.estado_id, "ENTREVISTA")
        transition_application(application.pk, "OFERTA_ENVIADA", self.hr_user)
        transition_application(application.pk, "CONTRATADA", self.hr_user)
        application.refresh_from_db()
        self.assertEqual(application.estado_id, "CONTRATADA")

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

    def test_hr_can_open_analysis_before_processing(self):
        application = create_application(self.vacancy.pk, self.profile)
        self.client.force_login(self.hr_user)

        response = self.client.get(reverse("analisis", args=[application.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aún no hay un análisis")

    def test_public_api_filters_and_paginates_vacancies(self):
        client = APIClient()

        response = client.get(
            reverse("api-plaza-list"),
            {"q": "Python", "abierta": "true", "page_size": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["titulo"], "Desarrollador Python")
        self.assertIn("next", response.data)

        response = client.get(reverse("api-plaza-list"), {"q": "no-existe"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_api_permissions_scope_applicant_data_by_role(self):
        client = APIClient()

        self.assertEqual(
            client.get(reverse("api-aspirante-list")).status_code,
            403,
        )

        client.force_authenticate(user=self.applicant)
        response = client.get(reverse("api-aspirante-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.profile.pk)
        self.assertEqual(
            client.get(
                reverse("api-aspirante-detail", args=[self.other_profile.pk])
            ).status_code,
            404,
        )

        client.force_authenticate(user=self.hr_user)
        response = client.get(reverse("api-aspirante-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_applicant_can_create_and_track_application_via_api(self):
        client = APIClient()
        client.force_authenticate(user=self.applicant)

        response = client.post(
            reverse("api-postulacion-list"),
            {
                "plaza_id": self.vacancy.pk,
                "carta_presentacion": "Me interesa la oportunidad.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        application = Postulacion.objects.get()
        self.assertEqual(response.data["id"], application.pk)
        self.assertEqual(response.data["plaza"]["titulo"], "Desarrollador Python")
        self.assertEqual(response.data["estado"]["codigo"], "ENVIADA")

        duplicate = client.post(
            reverse("api-postulacion-list"),
            {"plaza_id": self.vacancy.pk},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_hr_can_transition_and_queue_analysis_via_api(self):
        for code, name, final in (
            ("PENDIENTE", "Pendiente", False),
            ("PROCESANDO", "Procesando", False),
            ("COMPLETADO", "Completado", True),
            ("FALLIDO", "Fallido", True),
        ):
            EstadoProcesamiento.objects.create(codigo=code, nombre=name, es_final=final)
        application = create_application(self.vacancy.pk, self.profile)
        client = APIClient()
        client.force_authenticate(user=self.hr_user)

        response = client.post(
            reverse("api-postulacion-estado", args=[application.pk]),
            {"estado": "EN_REVISION", "motivo": "Revisión inicial."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"]["codigo"], "EN_REVISION")

        with override_settings(
            GROQ_API_KEY="test-key",
            ANALYSIS_ASYNC_ENABLED=True,
            CELERY_BROKER_URL="redis://127.0.0.1:6379/0",
        ), patch(
            "reclutamiento.tasks.process_application_analysis.delay",
            return_value=Mock(id="api-task-123"),
        ) as dispatch:
            response = client.post(
                reverse("api-postulacion-analisis", args=[application.pk]),
                {},
                format="json",
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["state"], "PENDIENTE")
        self.assertEqual(response.data["task_id"], "api-task-123")
        dispatch.assert_called_once_with(
            AnalisisCV.objects.get().pk,
            EvaluacionPostulacion.objects.get().pk,
        )

        response = client.get(
            reverse("api-postulacion-analisis", args=[application.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "PENDIENTE")
        self.assertEqual(response.data["evaluation"]["estado"]["codigo"], "PENDIENTE")

    def test_api_schema_and_swagger_endpoints_are_available(self):
        client = APIClient()

        schema = client.get(reverse("api-schema"))
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/api/v1/plazas/", schema.content.decode())
        self.assertIn("Nexo Talento API", schema.content.decode())
        self.assertEqual(client.get(reverse("api-docs")).status_code, 200)

    def test_analysis_job_is_queued_once_and_status_is_visible(self):
        for code, name, final in (
            ("PENDIENTE", "Pendiente", False),
            ("PROCESANDO", "Procesando", False),
            ("COMPLETADO", "Completado", True),
            ("FALLIDO", "Fallido", True),
        ):
            EstadoProcesamiento.objects.create(codigo=code, nombre=name, es_final=final)
        application = create_application(self.vacancy.pk, self.profile)

        with override_settings(
            GROQ_API_KEY="test-key",
            ANALYSIS_ASYNC_ENABLED=True,
            CELERY_BROKER_URL="redis://127.0.0.1:6379/0",
        ), patch(
            "reclutamiento.tasks.process_application_analysis.delay",
            return_value=Mock(id="task-123"),
        ) as dispatch:
            first = enqueue_application_analysis(application)
            second = enqueue_application_analysis(application)

        self.assertEqual(first.state, "PENDIENTE")
        self.assertEqual(first.task_id, "task-123")
        self.assertTrue(second.already_queued)
        self.assertEqual(AnalisisCV.objects.count(), 1)
        self.assertEqual(EvaluacionPostulacion.objects.count(), 1)
        dispatch.assert_called_once()

        self.client.force_login(self.hr_user)
        response = self.client.get(reverse("estado_analisis", args=[application.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PENDIENTE")
        self.assertEqual(response.json()["progress"], 10)
        page = self.client.get(reverse("analisis", args=[application.pk]))
        self.assertContains(page, "Procesamiento en segundo plano")
        self.assertContains(page, "La página se actualizará automáticamente")

    def test_worker_processes_prepared_analysis_job(self):
        for code, name, final in (
            ("PENDIENTE", "Pendiente", False),
            ("PROCESANDO", "Procesando", False),
            ("COMPLETADO", "Completado", True),
            ("FALLIDO", "Fallido", True),
        ):
            EstadoProcesamiento.objects.create(codigo=code, nombre=name, es_final=final)
        application = create_application(self.vacancy.pk, self.profile)
        page = Mock()
        page.extract_text.return_value = "Nombre Prueba\nExperiencia profesional"
        reader = Mock()
        reader.pages = [page]
        payload = {
            "personal_data": {
                "full_name": None,
                "email": None,
                "phone": None,
                "occupation": None,
                "city": None,
            },
            "professional_summary": "Resumen desde la cola.",
            "calculated_experience_months": 0,
            "experiences": [],
            "educations": [],
            "skills": [],
            "languages": [],
            "certifications": [],
        }
        with override_settings(
            GROQ_API_KEY="test-key",
            ANALYSIS_ASYNC_ENABLED=True,
            CELERY_BROKER_URL="redis://127.0.0.1:6379/0",
        ), patch(
            "reclutamiento.tasks.process_application_analysis.delay",
            return_value=Mock(id="task-456"),
        ):
            job = enqueue_application_analysis(application)

        with override_settings(ANALYSIS_OCR_ENABLED=False), patch(
            "pypdf.PdfReader", return_value=reader
        ), patch(
            "reclutamiento.ai_analysis.call_groq", return_value=payload
        ):
            result = process_application_analysis.run(job.analysis_id, job.evaluation_id)

        self.assertEqual(result["status"], "COMPLETADO")
        self.assertEqual(
            EvaluacionPostulacion.objects.get(pk=job.evaluation_id).estado_id,
            "COMPLETADO",
        )

    def test_ai_analysis_persists_cv_data_and_weighted_compatibility(self):
        for code, name, final in (
            ("PENDIENTE", "Pendiente", False),
            ("PROCESANDO", "Procesando", False),
            ("COMPLETADO", "Completado", True),
            ("FALLIDO", "Fallido", True),
        ):
            EstadoProcesamiento.objects.create(codigo=code, nombre=name, es_final=final)
        requirement_type = TipoRequisito.objects.create(
            codigo="HABILIDAD", nombre="Habilidad"
        )
        skill = Habilidad.objects.create(nombre="Python", activo=True)
        certification = Certificacion.objects.create(
            nombre="Python Professional",
            organizacion_emisora="Python Institute",
        )
        requirement = RequisitoPlaza.objects.create(
            plaza=self.vacancy,
            tipo=requirement_type,
            descripcion="Dominio de Python",
            obligatorio=True,
            peso="100.00",
            orden_visualizacion=1,
        )
        RequisitoHabilidad.objects.create(
            requisito=requirement,
            habilidad=skill,
        )
        application = create_application(self.vacancy.pk, self.profile)
        page = Mock()
        page.extract_text.return_value = "Nombre Prueba\nExperiencia con Python"
        reader = Mock()
        reader.pages = [page]
        payload = {
            "personal_data": {
                "full_name": "Nombre Prueba",
                "email": "nombre@example.com",
                "phone": "+502 5555-0101",
                "occupation": "Ingeniería de software",
                "city": "Ciudad de Guatemala",
            },
            "professional_summary": "Desarrollador con experiencia en Python.",
            "calculated_experience_months": 36,
            "experiences": [
                {
                    "company": "Empresa de prueba",
                    "occupation": "Ingeniería de software",
                    "position": "Desarrollador backend",
                    "start_date": "2020-01-01",
                    "end_date": "2021-01-01",
                    "description": "Construcción de APIs.",
                    "confidence": 0.95,
                },
                {
                    "company": "Empresa de prueba",
                    "occupation": "Ingeniería de software",
                    "position": "Desarrollador backend",
                    "start_date": "2020-06-01",
                    "end_date": "2020-12-01",
                    "description": "Periodo duplicado por solapamiento.",
                    "confidence": 0.90,
                },
            ],
            "educations": [],
            "skills": [
                {
                    "name": "Python",
                    "confidence": 0.98,
                    "evidence": "Experiencia con Python",
                }
            ],
            "languages": [],
            "certifications": [
                {
                    "name": certification.nombre,
                    "issued_on": "2024-01-15",
                    "expires_on": None,
                    "confidence": 0.96,
                }
            ],
        }
        with override_settings(
            GROQ_API_KEY="test-key",
            ANALYSIS_OCR_ENABLED=False,
        ), patch("pypdf.PdfReader", return_value=reader), patch(
            "reclutamiento.ai_analysis.call_groq", return_value=payload
        ) as call:
            evaluation = analyze_application(application)
            repeated = analyze_application(application)

        analysis = AnalisisCV.objects.get(curriculo=self.curriculum)
        self.assertEqual(analysis.estado_id, "COMPLETADO")
        self.assertTrue(analysis.vigente)
        self.assertEqual(analysis.resumen_profesional, payload["professional_summary"])
        self.assertEqual(analysis.meses_experiencia_calculados, 12)
        self.assertEqual(ExperienciaAnalisisCV.objects.filter(analisis=analysis).count(), 2)
        self.assertEqual(
            DatosPersonalesAnalisisCV.objects.get(analisis=analysis).correo,
            "nombre@example.com",
        )
        self.assertEqual(HabilidadAnalisisCV.objects.get(analisis=analysis).habilidad, skill)
        extracted_certification = CertificacionAnalisisCV.objects.get(analisis=analysis)
        self.assertEqual(extracted_certification.certificacion, certification)
        self.assertEqual(extracted_certification.nombre_detectado, certification.nombre)
        self.assertEqual(evaluation.pk, repeated.pk)
        self.assertEqual(evaluation.estado_id, "COMPLETADO")
        self.assertEqual(evaluation.porcentaje_compatibilidad, 100)
        self.assertTrue(
            ResultadoRequisitoEvaluacion.objects.get(
                evaluacion=evaluation,
                requisito=requirement,
            ).cumplido
        )
        call.assert_called_once()

        self.client.force_login(self.hr_user)
        response = self.client.get(reverse("analisis", args=[application.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Desarrollador con experiencia en Python.")
        self.assertContains(response, "Dominio de Python")
        self.assertContains(response, "Python Professional")
        self.assertContains(response, "100%")
        self.assertContains(
            self.client.get(reverse("postulaciones")),
            "100%",
        )
        self.assertContains(
            self.client.get(reverse("dashboard")),
            "Nombre Prueba",
        )
