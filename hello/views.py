import csv
import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.core.exceptions import ValidationError
from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)

from reclutamiento.forms import (
    FormularioAcceso,
    FormularioCambioEstadoPostulacion,
    FormularioCambioContrasena,
    FormularioConfiguracionCuenta,
    FormularioCertificacionAspirante,
    FormularioCurriculo,
    FormularioEntrevista,
    FormularioEstadoEntrevista,
    FormularioExperiencia,
    FormularioFormacion,
    FormularioHabilidadAspirante,
    FormularioHabilidadesPlaza,
    FormularioIdiomaAspirante,
    FormularioIdiomasPlaza,
    FormularioNuevaContrasena,
    FormularioPerfilAspirante,
    FormularioOfertaLaboral,
    FormularioPostulacion,
    FormularioReenvioVerificacion,
    FormularioRegistroAspirante,
    FormularioPlaza,
    FormularioDatosPlaza,
    FormularioRequisitosGenerales,
    FormularioCertificacionesPlaza,
)
from reclutamiento.models import (
    AnalisisCV,
    CertificacionAspirante,
    CertificacionAnalisisCV,
    Curriculo,
    DatosPersonalesAnalisisCV,
    Departamento,
    EducacionAnalisisCV,
    Entrevista,
    EvaluacionPostulacion,
    ExperienciaAnalisisCV,
    ExperienciaLaboral,
    FormacionAcademica,
    HabilidadAspirante,
    HabilidadAnalisisCV,
    HistorialEstadoPostulacion,
    HistorialEstadoPlaza,
    IdiomaAspirante,
    IdiomaAnalisisCV,
    ModalidadTrabajo,
    Notificacion,
    OfertaLaboral,
    PerfilAspirante,
    PerfilPersonal,
    RequisitoDisponibilidad,
    Plaza,
    Postulacion,
    RequisitoPlaza,
    Usuario,
)
from reclutamiento.permissions import roles_required
from reclutamiento.reports import (
    build_recruitment_report,
    report_applications,
    spreadsheet_safe,
)
from reclutamiento.applications import (
    ALLOWED_APPLICATION_TRANSITIONS,
    ALLOWED_INTERVIEW_TRANSITIONS,
    create_application,
    create_offer,
    expire_offers,
    respond_offer,
    schedule_interview,
    transition_application,
    transition_interview,
    vacancy_accepts_applications,
)
from reclutamiento.candidates import (
    PROFILE_SECTIONS,
    curriculum_path,
    get_applicant_profile,
    profile_completion,
    save_curriculum,
    save_profile,
    save_profile_record,
)
from reclutamiento.ai_analysis import (
    AnalysisError,
    enqueue_application_analysis,
    get_current_evaluation,
)
from reclutamiento.emails import send_verification_email
from reclutamiento.services import register_applicant
from reclutamiento.storage import B2_PROVIDER_CODE, backblaze_download_url
from reclutamiento.tokens import email_verification_token
from reclutamiento.vacancies import (
    ALLOWED_TRANSITIONS,
    get_requirement_editor_initial,
    save_vacancy,
    save_vacancy_requirements,
    transition_vacancy,
)


logger = logging.getLogger(__name__)

PROFILE_SECTION_LABELS = {
    "datos": "Datos personales",
    "experiencia": "Experiencia laboral",
    "formacion": "Formación académica",
    "habilidades": "Habilidades",
    "idiomas": "Idiomas",
    "certificaciones": "Certificaciones",
    "curriculo": "Currículum",
}


def _profile_checklist(completed):
    actions = {
        "datos": reverse("perfil_aspirante"),
        "experiencia": reverse("nuevo_registro_perfil", args=["experiencia"]),
        "formacion": reverse("nuevo_registro_perfil", args=["formacion"]),
        "habilidades": reverse("agregar_habilidad"),
        "idiomas": reverse("agregar_idioma"),
        "certificaciones": reverse("nuevo_registro_perfil", args=["certificacion"]),
        "curriculo": reverse("cargar_curriculo"),
    }
    return [
        {
            "key": key,
            "label": PROFILE_SECTION_LABELS[key],
            "completed": completed[key],
            "url": actions[key],
        }
        for key in PROFILE_SECTIONS
    ]


def _home_for(user):
    if user.has_role("RRHH", "ADMINISTRADOR"):
        return "dashboard"
    if user.has_role("ASPIRANTE"):
        return "portal"
    return "index"


def _send_verification_safely(request, user):
    try:
        send_verification_email(request, user)
        return True
    except Exception:
        logger.exception("No se pudo enviar la verificación a usuario_id=%s", user.pk)
        return False


def index(request):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))

    form = FormularioAcceso(request, request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if not form.cleaned_data["remember"]:
                request.session.set_expiry(0)

            requested_next = request.GET.get("next")
            if requested_next and url_has_allowed_host_and_scheme(
                requested_next,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(requested_next)
            return redirect(_home_for(user))

    show_verification_resend = any(
        error.code == "unverified"
        for error in form.non_field_errors().as_data()
    )
    return render(
        request,
        "login.html",
        {"form": form, "show_verification_resend": show_verification_resend},
    )


def registrar_aspirante(request):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))

    form = FormularioRegistroAspirante(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = register_applicant(form)
        except IntegrityError:
            form.add_error(
                "email",
                "Ya existe una cuenta con este correo electrónico.",
            )
        else:
            email_sent = _send_verification_safely(request, user)
            return render(
                request,
                "auth/registro_exitoso.html",
                {
                    "title": "Verifica tu correo",
                    "email": user.email,
                    "email_sent": email_sent,
                },
            )
    return render(
        request,
        "auth/registro_aspirante.html",
        {"form": form, "title": "Crear cuenta"},
    )


def reenviar_verificacion(request):
    if request.user.is_authenticated:
        return redirect(_home_for(request.user))

    form = FormularioReenvioVerificacion(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = (
            Usuario.objects.filter(
                email__iexact=form.cleaned_data["email"],
                is_active=True,
                is_verified=False,
                usuariorol__rol__codigo="ASPIRANTE",
            )
            .distinct()
            .first()
        )
        if user:
            _send_verification_safely(request, user)
        return render(
            request,
            "auth/reenvio_completado.html",
            {"title": "Revisa tu correo"},
        )
    return render(
        request,
        "auth/reenviar_verificacion.html",
        {"form": form, "title": "Reenviar verificación"},
    )


@login_required
def cerrar_sesion(request):
    if request.method == "POST":
        logout(request)
        return redirect("index")
    return redirect(_home_for(request.user))


def _recent_dashboard_activity():
    available_tables = set(connection.introspection.table_names())
    activity = []

    def tables_exist(*models):
        return all(model._meta.db_table in available_tables for model in models)

    if tables_exist(HistorialEstadoPlaza, Plaza):
        try:
            for item in HistorialEstadoPlaza.objects.select_related("plaza").order_by(
                "-cambiado_en"
            )[:4]:
                is_new_vacancy = item.codigo_estado_anterior is None
                activity.append(
                    {
                        "color": "blue",
                        "icon": "briefcase",
                        "label": (
                            "Plaza creada"
                            if is_new_vacancy
                            else "Cambio de estado en"
                        ),
                        "subject": item.plaza.titulo,
                        "created_at": item.cambiado_en,
                    }
                )
        except DatabaseError:
            pass

    if tables_exist(HistorialEstadoPostulacion, Postulacion, Plaza):
        try:
            for item in HistorialEstadoPostulacion.objects.select_related(
                "postulacion__plaza"
            ).order_by("-cambiado_en")[:4]:
                is_new_application = item.codigo_estado_nuevo == "ENVIADA"
                activity.append(
                    {
                        "color": "blue" if is_new_application else "green",
                        "icon": "send-check" if is_new_application else "arrow-repeat",
                        "label": (
                            "Nueva postulación para"
                            if is_new_application
                            else "Cambio de estado en"
                        ),
                        "subject": item.postulacion.plaza.titulo,
                        "created_at": item.cambiado_en,
                    }
                )
        except DatabaseError:
            pass

    if tables_exist(Entrevista, Postulacion, PerfilAspirante, Usuario):
        try:
            for item in Entrevista.objects.select_related(
                "postulacion__aspirante__usuario"
            ).order_by("-creado_en")[:4]:
                user = item.postulacion.aspirante.usuario
                activity.append(
                    {
                        "color": "violet",
                        "icon": "person",
                        "label": "Entrevista programada con",
                        "subject": user.get_full_name() or user.email,
                        "created_at": item.creado_en,
                    }
                )
        except DatabaseError:
            pass

    if tables_exist(EvaluacionPostulacion, Postulacion, PerfilAspirante, Usuario):
        try:
            for item in EvaluacionPostulacion.objects.filter(
                estado_id="COMPLETADO",
                completado_en__isnull=False,
            ).select_related("postulacion__aspirante__usuario").order_by(
                "-completado_en"
            )[:4]:
                user = item.postulacion.aspirante.usuario
                activity.append(
                    {
                        "color": "amber",
                        "icon": "bell",
                        "label": "Evaluación completada para",
                        "subject": user.get_full_name() or user.email,
                        "created_at": item.completado_en,
                    }
                )
        except DatabaseError:
            pass

    return sorted(activity, key=lambda item: item["created_at"], reverse=True)[:4]


@roles_required("RRHH", "ADMINISTRADOR")
def dashboard(request):
    now = timezone.now()
    vacancy_counts = dict(
        Plaza.objects.values("estado_id")
        .annotate(total=Count("id"))
        .values_list("estado_id", "total")
    )
    active_vacancy_query = Q(estado_id="PUBLICADA") & (
        Q(cierra_en__isnull=True) | Q(cierra_en__gt=now)
    )
    priority_vacancies = list(
        Plaza.objects.annotate(
            hired_count=Count(
                "postulacion",
                filter=Q(postulacion__estado_id="CONTRATADA"),
                distinct=True,
            )
        )
        .filter(
            Q(estado_id="PAUSADA")
            | (active_vacancy_query & Q(hired_count__lt=F("cantidad_vacantes")))
        )
        .select_related("departamento", "modalidad_trabajo")
        .annotate(applicant_count=Count("postulacion", distinct=True))
        .order_by("cierra_en", "-actualizado_en")[:3]
    )
    maximum_applicants = max(
        (vacancy.applicant_count for vacancy in priority_vacancies), default=0
    )
    for vacancy in priority_vacancies:
        vacancy.bar_width = (
            round(vacancy.applicant_count * 100 / maximum_applicants)
            if maximum_applicants
            else 0
        )
    top_evaluations = (
        EvaluacionPostulacion.objects.filter(
            vigente=True,
            estado_id="COMPLETADO",
            porcentaje_compatibilidad__isnull=False,
        )
        .order_by("-porcentaje_compatibilidad", "-creado_en")[:4]
    )
    return render(
        request,
        "dashboard.html",
        {
            "vacancy_counts": vacancy_counts,
            "active_vacancies": _available_vacancies().count(),
            "pending_vacancies": vacancy_counts.get("BORRADOR", 0)
            + vacancy_counts.get("PAUSADA", 0),
            "closed_vacancies": vacancy_counts.get("CERRADA", 0),
            "total_applicants": Usuario.objects.filter(
                usuariorol__rol__codigo="ASPIRANTE"
            ).distinct().count(),
            "priority_vacancies": priority_vacancies,
            "top_evaluations": top_evaluations,
            "recent_activity": _recent_dashboard_activity(),
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def reportes(request):
    return render(
        request,
        "reportes.html",
        build_recruitment_report(request.GET.get("periodo", "30")),
    )


@roles_required("RRHH", "ADMINISTRADOR")
def exportar_reporte(request):
    period, applications = report_applications(request.GET.get("periodo", "30"))
    applications = applications.select_related(
        "aspirante__usuario", "plaza__departamento", "estado"
    ).order_by("-postulado_en")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="reporte-reclutamiento-{period}.csv"'
    )
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ("Aspirante", "Correo", "Plaza", "Departamento", "Fecha", "Estado")
    )
    for application in applications.iterator():
        writer.writerow(
            (
                spreadsheet_safe(application.aspirante.usuario.get_full_name()),
                spreadsheet_safe(application.aspirante.usuario.email),
                spreadsheet_safe(application.plaza.titulo),
                spreadsheet_safe(application.plaza.departamento.nombre),
                application.postulado_en.date().isoformat(),
                spreadsheet_safe(application.estado.nombre),
            )
        )
    return response


@roles_required("RRHH", "ADMINISTRADOR")
def configuracion(request):
    profile = PerfilPersonal.objects.filter(usuario=request.user).first()
    form = FormularioConfiguracionCuenta(
        request.POST or None,
        instance=profile,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, "La configuración de tu cuenta fue actualizada.")
        return redirect("configuracion")
    return render(
        request,
        "configuracion.html",
        {"form": form, "profile": profile},
    )


@roles_required("RRHH", "ADMINISTRADOR")
def plazas(request):
    now = timezone.now()
    active_filter = Q(estado_id="PUBLICADA") & (
        Q(cierra_en__isnull=True) | Q(cierra_en__gt=now)
    )
    expired_filter = Q(
        estado_id="PUBLICADA",
        cierra_en__isnull=False,
        cierra_en__lte=now,
    )
    vacancies = (
        Plaza.objects.select_related(
            "departamento",
            "modalidad_trabajo",
            "tipo_empleo",
            "estado",
        )
        .annotate(applicant_count=Count("postulacion", distinct=True))
        .order_by("-actualizado_en")
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip().upper()
    department = request.GET.get("departamento", "").strip()
    work_mode = request.GET.get("modalidad", "").strip()
    if query:
        vacancies = vacancies.filter(
            Q(titulo__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(departamento__nombre__icontains=query)
        )
    if status:
        if status == "PUBLICADA":
            vacancies = vacancies.filter(active_filter)
        elif status == "VENCIDA":
            vacancies = vacancies.filter(expired_filter)
        else:
            vacancies = vacancies.filter(estado_id=status)
    if department:
        vacancies = vacancies.filter(departamento_id=department)
    if work_mode:
        vacancies = vacancies.filter(modalidad_trabajo_id=work_mode)

    status_counts = dict(
        Plaza.objects.values_list("estado_id")
        .annotate(total=Count("id"))
        .values_list("estado_id", "total")
    )
    status_counts["PUBLICADA"] = Plaza.objects.filter(active_filter).count()
    status_counts["VENCIDA"] = Plaza.objects.filter(expired_filter).count()
    page = Paginator(vacancies, 9).get_page(request.GET.get("pagina"))
    return render(
        request,
        "plazas.html",
        {
            "page": page,
            "status_counts": status_counts,
            "total_count": Plaza.objects.count(),
            "departments": Departamento.objects.filter(activo=True).order_by("nombre"),
            "work_modes": ModalidadTrabajo.objects.order_by("nombre"),
            "filters": {
                "q": query,
                "estado": status,
                "departamento": department,
                "modalidad": work_mode,
            },
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def nueva_plaza(request):
    form = FormularioPlaza(request.POST or None)
    missing_catalogs = form.missing_required_catalogs()
    catalogs_ready = not missing_catalogs
    if request.method == "POST" and not catalogs_ready:
        form.add_error(
            None,
            "No se puede guardar la plaza porque faltan catálogos obligatorios: "
            + ", ".join(missing_catalogs)
            + ".",
        )
    elif request.method == "POST" and form.is_valid():
        publish = request.POST.get("accion") == "publicar"
        try:
            vacancy = save_vacancy(form, request.user, publish=publish)
        except ValidationError as error:
            form.add_error(None, error.message)
        else:
            messages.success(
                request,
                "La plaza fue publicada." if publish else "La plaza se guardó como borrador.",
            )
            return redirect("detalle_plaza", plaza_id=vacancy.pk)
    return render(
        request,
        "nueva_plaza.html",
        {
            "form": form,
            "catalogs_ready": catalogs_ready,
            "missing_catalogs": missing_catalogs,
            "editing": False,
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def editar_plaza(request, plaza_id):
    vacancy = get_object_or_404(Plaza.objects.select_related("estado"), pk=plaza_id)
    if vacancy.estado_id == "CERRADA":
        messages.error(request, "Una plaza cerrada no puede editarse.")
        return redirect("detalle_plaza", plaza_id=vacancy.pk)
    form = FormularioDatosPlaza(
        request.POST or None,
        instance=vacancy,
    )
    missing_catalogs = form.missing_required_catalogs()
    catalogs_ready = not missing_catalogs
    if request.method == "POST" and not catalogs_ready:
        form.add_error(
            None,
            "No se puede guardar la plaza porque faltan catálogos obligatorios: "
            + ", ".join(missing_catalogs)
            + ".",
        )
    elif request.method == "POST" and form.is_valid():
        try:
            vacancy = save_vacancy(form, request.user)
        except ValidationError as error:
            form.add_error(None, error.message)
        else:
            messages.success(request, "Los cambios de la plaza fueron guardados.")
            return redirect("detalle_plaza", plaza_id=vacancy.pk)
    return render(
        request,
        "nueva_plaza.html",
        {
            "form": form,
            "plaza": vacancy,
            "catalogs_ready": catalogs_ready,
            "missing_catalogs": missing_catalogs,
            "editing": True,
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def editar_requisitos_plaza(request, plaza_id):
    vacancy = get_object_or_404(Plaza.objects.select_related("estado"), pk=plaza_id)
    if vacancy.estado_id == "CERRADA":
        messages.error(request, "Los requisitos de una plaza cerrada no pueden editarse.")
        return redirect("detalle_plaza", plaza_id=vacancy.pk)
    general_initial, skills_initial, languages_initial, certifications_initial = (
        get_requirement_editor_initial(vacancy)
    )
    general_form = FormularioRequisitosGenerales(
        request.POST or None,
        initial=general_initial,
        prefix="general",
    )
    skill_formset = FormularioHabilidadesPlaza(
        request.POST or None,
        initial=skills_initial,
        prefix="habilidades",
    )
    language_formset = FormularioIdiomasPlaza(
        request.POST or None,
        initial=languages_initial,
        prefix="idiomas",
    )
    certification_formset = FormularioCertificacionesPlaza(
        request.POST or None,
        initial=certifications_initial,
        prefix="certificaciones",
    )
    forms_are_valid = all(
        item.is_valid()
        for item in (
            general_form,
            skill_formset,
            language_formset,
            certification_formset,
        )
    )
    if request.method == "POST" and forms_are_valid:
        try:
            save_vacancy_requirements(
                vacancy.pk,
                general_form,
                skill_formset,
                language_formset,
                certification_formset,
            )
        except ValidationError as error:
            general_form.add_error(None, error.message)
        else:
            messages.success(request, "Los requisitos de la plaza fueron actualizados.")
            return redirect("detalle_plaza", plaza_id=vacancy.pk)
    return render(
        request,
        "requisitos_plaza.html",
        {
            "plaza": vacancy,
            "general_form": general_form,
            "skill_formset": skill_formset,
            "language_formset": language_formset,
            "certification_formset": certification_formset,
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def detalle_plaza(request, plaza_id):
    vacancy = get_object_or_404(
        Plaza.objects.select_related(
            "departamento",
            "profesion",
            "ciudad",
            "tipo_empleo",
            "modalidad_trabajo",
            "periodo_salarial",
            "estado",
            "creado_por",
        ).annotate(applicant_count=Count("postulacion", distinct=True)),
        pk=plaza_id,
    )
    requirements = RequisitoPlaza.objects.filter(plaza=vacancy).select_related(
        "tipo"
    ).order_by("orden_visualizacion")
    history = HistorialEstadoPlaza.objects.filter(plaza=vacancy).select_related(
        "cambiado_por"
    ).order_by("-cambiado_en")
    return render(
        request,
        "detalle_plaza.html",
        {
            "plaza": vacancy,
            "requirements": requirements,
            "history": history,
            "allowed_transitions": ALLOWED_TRANSITIONS.get(vacancy.estado_id, set()),
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def cambiar_estado_plaza(request, plaza_id, estado):
    if request.method != "POST":
        return redirect("detalle_plaza", plaza_id=plaza_id)
    try:
        transition_vacancy(
            plaza_id,
            estado.upper(),
            request.user,
            request.POST.get("motivo"),
        )
    except (ValidationError, Plaza.DoesNotExist) as error:
        message = error.message if isinstance(error, ValidationError) else "La plaza no existe."
        messages.error(request, message)
    else:
        messages.success(request, "El estado de la plaza fue actualizado.")
    return redirect("detalle_plaza", plaza_id=plaza_id)


@roles_required("RRHH", "ADMINISTRADOR")
def aspirantes(request):
    applicants = (
        PerfilAspirante.objects.select_related("usuario", "profesion", "ciudad")
        .annotate(application_count=Count("postulacion", distinct=True))
        .order_by("usuario__first_name", "usuario__last_name")
    )
    query = request.GET.get("q", "").strip()
    if query:
        applicants = applicants.filter(
            Q(usuario__first_name__icontains=query)
            | Q(usuario__last_name__icontains=query)
            | Q(usuario__email__icontains=query)
            | Q(profesion__nombre__icontains=query)
        )
    page = Paginator(applicants, 15).get_page(request.GET.get("pagina"))
    return render(request, "aspirantes.html", {"page": page, "query": query})


@roles_required("RRHH", "ADMINISTRADOR")
def detalle_aspirante(request, aspirante_id):
    profile = get_object_or_404(
        PerfilAspirante.objects.select_related("usuario", "profesion", "ciudad"),
        pk=aspirante_id,
    )
    percentage, completed = profile_completion(profile)
    return render(
        request,
        "detalle_aspirante.html",
        {
            "perfil": profile,
            "profile_percentage": percentage,
            "profile_sections": completed,
            "experiences": profile.experiencialaboral_set.select_related(
                "profesion", "ciudad"
            ).order_by("-fecha_inicio"),
            "education": profile.formacionacademica_set.select_related(
                "institucion", "nivel_educativo", "area_estudio"
            ).order_by("-fecha_fin", "-fecha_inicio"),
            "skills": profile.habilidadaspirante_set.select_related(
                "habilidad", "nivel_habilidad"
            ).order_by("habilidad__nombre"),
            "languages": profile.idiomaaspirante_set.select_related(
                "idioma", "nivel_idioma"
            ).order_by("idioma__nombre"),
            "certifications": profile.certificacionaspirante_set.select_related(
                "certificacion"
            ).order_by("-emitida_en"),
            "curriculum": profile.curriculo_set.filter(activo=True).order_by(
                "-cargado_en"
            ).first(),
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def postulaciones(request):
    expire_offers()
    current_compatibility = (
        EvaluacionPostulacion.objects.filter(
            postulacion=OuterRef("pk"),
            vigente=True,
            estado_id="COMPLETADO",
        )
        .order_by("-creado_en")
        .values("porcentaje_compatibilidad")[:1]
    )
    applications = Postulacion.objects.select_related(
        "aspirante__usuario",
        "plaza__departamento",
        "estado",
    ).annotate(
        compatibility_score=Subquery(
            current_compatibility,
            output_field=DecimalField(max_digits=5, decimal_places=2),
        )
    ).order_by("-actualizado_en")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip().upper()
    vacancy_filter = request.GET.get("plaza", "").strip()
    if not vacancy_filter.isdigit():
        vacancy_filter = ""
    application_scope = Postulacion.objects.all()
    if vacancy_filter:
        applications = applications.filter(plaza_id=vacancy_filter)
        application_scope = application_scope.filter(plaza_id=vacancy_filter)
    if query:
        applications = applications.filter(
            Q(aspirante__usuario__first_name__icontains=query)
            | Q(aspirante__usuario__last_name__icontains=query)
            | Q(aspirante__usuario__email__icontains=query)
            | Q(plaza__titulo__icontains=query)
        )
    if status:
        applications = applications.filter(estado_id=status)
    page = Paginator(applications, 15).get_page(request.GET.get("pagina"))
    status_counts = dict(
        application_scope.values_list("estado_id")
        .annotate(total=Count("id"))
        .values_list("estado_id", "total")
    )
    statuses = Postulacion._meta.get_field("estado").remote_field.model.objects.order_by(
        "nombre"
    )
    status_summary = [
        {"status": item, "count": status_counts.get(item.codigo, 0)}
        for item in statuses
    ]
    return render(
        request,
        "postulaciones.html",
        {
            "page": page,
            "statuses": statuses,
            "status_summary": status_summary,
            "total_count": application_scope.count(),
            "plaza_filter": Plaza.objects.filter(pk=vacancy_filter).first()
            if vacancy_filter
            else None,
            "filters": {"q": query, "estado": status, "plaza": vacancy_filter},
        },
    )


def _postulacion_detail_context(application, interview_form=None):
    expire_offers(application.pk)
    application.refresh_from_db()
    history = HistorialEstadoPostulacion.objects.filter(
        postulacion=application
    ).select_related("cambiado_por").order_by("-cambiado_en")
    interviews = Entrevista.objects.filter(postulacion=application).select_related(
        "estado", "creado_por"
    ).order_by("-inicia_en")
    evaluation = get_current_evaluation(application)
    for interview in interviews:
        interview.available_transitions = sorted(
            ALLOWED_INTERVIEW_TRANSITIONS.get(interview.estado_id, set())
        )
    offers = OfertaLaboral.objects.filter(postulacion=application).select_related(
        "estado", "creado_por"
    ).order_by("-creado_en")
    active_offer = offers.filter(estado_id__in={"ENVIADA", "ACEPTADA"}).first()
    transitions = ALLOWED_APPLICATION_TRANSITIONS.get(application.estado_id, set()) - {
        "RETIRADA",
        "OFERTA_ENVIADA",
    }
    if not active_offer or active_offer.estado_id != "ACEPTADA":
        transitions.discard("CONTRATADA")
    status_choices = [
        (status.codigo, status.nombre)
        for status in Postulacion._meta.get_field("estado").remote_field.model.objects.filter(
            codigo__in=transitions
        )
    ]
    return {
        "postulacion": application,
        "history": history,
        "interviews": interviews,
        "state_form": FormularioCambioEstadoPostulacion(estados=status_choices),
        "has_state_transitions": bool(status_choices),
        "interview_form": (
            interview_form if interview_form is not None else FormularioEntrevista()
        ),
        "can_schedule_interview": application.estado_id in {"PRESELECCIONADA", "ENTREVISTA"},
        "evaluacion": evaluation,
        "ofertas": offers,
        "offer_form": FormularioOfertaLaboral(),
        "can_send_offer": application.estado_id == "ENTREVISTA" and active_offer is None,
    }


@roles_required("RRHH", "ADMINISTRADOR")
def detalle_postulacion(request, postulacion_id):
    application = get_object_or_404(
        Postulacion.objects.select_related(
            "aspirante__usuario",
            "aspirante__profesion",
            "aspirante__ciudad",
            "plaza",
            "curriculo",
            "estado",
        ),
        pk=postulacion_id,
    )
    return render(
        request,
        "detalle_postulacion.html",
        _postulacion_detail_context(application),
    )


@roles_required("RRHH", "ADMINISTRADOR")
def cambiar_estado_postulacion(request, postulacion_id):
    if request.method != "POST":
        return redirect("detalle_postulacion", postulacion_id=postulacion_id)
    application = get_object_or_404(Postulacion, pk=postulacion_id)
    transitions = ALLOWED_APPLICATION_TRANSITIONS.get(application.estado_id, set()) - {
        "RETIRADA"
    }
    states = Postulacion._meta.get_field("estado").remote_field.model.objects.filter(
        codigo__in=transitions
    )
    form = FormularioCambioEstadoPostulacion(
        request.POST,
        estados=[(state.codigo, state.nombre) for state in states],
    )
    if form.is_valid():
        try:
            transition_application(
                application.pk,
                form.cleaned_data["estado"],
                request.user,
                form.cleaned_data["motivo"],
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "El estado de la postulación fue actualizado.")
    else:
        messages.error(request, "Selecciona una transición válida.")
    return redirect("detalle_postulacion", postulacion_id=postulacion_id)


@roles_required("RRHH", "ADMINISTRADOR")
def enviar_oferta(request, postulacion_id):
    if request.method != "POST":
        return redirect("detalle_postulacion", postulacion_id=postulacion_id)
    application = get_object_or_404(Postulacion, pk=postulacion_id)
    form = FormularioOfertaLaboral(request.POST)
    if form.is_valid():
        try:
            create_offer(
                application.pk,
                request.user,
                form.cleaned_data["condiciones"],
                form.cleaned_data["vence_en"],
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "La oferta laboral fue enviada al aspirante.")
    else:
        messages.error(request, "Revisa las condiciones y el vencimiento de la oferta.")
    return redirect("detalle_postulacion", postulacion_id=postulacion_id)


@roles_required("ASPIRANTE")
def responder_oferta(request, oferta_id, respuesta):
    offer = get_object_or_404(
        OfertaLaboral.objects.select_related("postulacion__aspirante"),
        pk=oferta_id,
        postulacion__aspirante__usuario=request.user,
    )
    if request.method == "POST":
        try:
            offer = respond_offer(offer.pk, request.user, respuesta)
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            if offer.estado_id == "VENCIDA":
                messages.error(request, "La oferta venció y ya no puede responderse.")
            else:
                messages.success(request, "Tu respuesta a la oferta fue registrada.")
    return redirect("mi_postulacion", postulacion_id=offer.postulacion_id)


@roles_required("RRHH", "ADMINISTRADOR")
def programar_entrevista(request, postulacion_id):
    if request.method != "POST":
        return redirect("detalle_postulacion", postulacion_id=postulacion_id)
    application = get_object_or_404(
        Postulacion.objects.select_related("estado"),
        pk=postulacion_id,
    )
    form = FormularioEntrevista(request.POST)
    if form.is_valid():
        try:
            schedule_interview(form, application.pk, request.user)
        except ValidationError as error:
            form.add_error(None, error.message)
        else:
            messages.success(request, "La entrevista fue programada.")
            return redirect("detalle_postulacion", postulacion_id=application.pk)
    return render(
        request,
        "detalle_postulacion.html",
        _postulacion_detail_context(application, interview_form=form),
    )


@roles_required("RRHH", "ADMINISTRADOR")
def cambiar_estado_entrevista(request, entrevista_id):
    interview = get_object_or_404(Entrevista, pk=entrevista_id)
    if request.method == "POST":
        form = FormularioEstadoEntrevista(request.POST)
        if form.is_valid():
            try:
                transition_interview(interview.pk, form.cleaned_data["estado"].codigo)
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "El estado de la entrevista fue actualizado.")
    return redirect("detalle_postulacion", postulacion_id=interview.postulacion_id)


@roles_required("RRHH", "ADMINISTRADOR")
def analisis(request, postulacion_id=None):
    if postulacion_id is None:
        return render(request, "analisis_index.html")
    application = get_object_or_404(
        Postulacion.objects.select_related(
            "aspirante__usuario",
            "aspirante__profesion",
            "aspirante__ciudad",
            "plaza__departamento",
            "curriculo__proveedor_almacenamiento",
        ),
        pk=postulacion_id,
    )
    if request.method == "POST":
        try:
            job = enqueue_application_analysis(
                application,
                force=request.POST.get("force") == "1",
            )
        except AnalysisError as error:
            messages.error(request, error.messages[0] if error.messages else str(error))
        else:
            if job.state == "COMPLETADO":
                messages.success(request, "El análisis del currículum ya estaba completado.")
            elif job.already_queued:
                messages.success(request, "El análisis ya está en proceso. Esta página mostrará su avance.")
            elif job.state == "FALLIDO":
                messages.error(request, "No se pudo iniciar el análisis. Usa Reintentar análisis para volver a intentarlo.")
            elif job.synchronous:
                messages.success(request, "El análisis del currículum fue completado.")
            else:
                messages.success(request, "El análisis fue enviado a segundo plano. Esta página mostrará su avance.")
        return redirect("analisis", postulacion_id=application.pk)

    evaluation = get_current_evaluation(application)
    analysis = (
        AnalisisCV.objects.filter(curriculo=application.curriculo, vigente=True)
        .select_related("estado", "motor_analisis", "motor_analisis__modelo_ia")
        .order_by("-creado_en")
        .first()
    )
    if evaluation:
        analysis = evaluation.analisis_cv
    status_record = evaluation or analysis
    analysis_state = getattr(status_record, "estado_id", "SIN_ANALISIS")
    analysis_progress = {
        "PENDIENTE": 10,
        "PROCESANDO": 55,
        "COMPLETADO": 100,
        "FALLIDO": 100,
    }.get(analysis_state, 0)
    analysis_in_progress = analysis_state in {"PENDIENTE", "PROCESANDO"}
    analysis_error = getattr(status_record, "mensaje_error", None)
    requirements = list(
        RequisitoPlaza.objects.filter(plaza=application.plaza)
        .select_related("tipo")
        .order_by("orden_visualizacion", "pk")
    )
    results = []
    if evaluation:
        results = list(
            evaluation.resultadorequisitoevaluacion_set.select_related("requisito").all()
        )
    result_by_requirement = {result.requisito_id: result for result in results}
    for requirement in requirements:
        requirement.analysis_result = result_by_requirement.get(requirement.pk)

    personal_data = (
        DatosPersonalesAnalisisCV.objects.filter(analisis=analysis).first()
        if analysis
        else None
    )
    context = {
        "postulacion": application,
        "evaluacion": evaluation,
        "analisis_cv": analysis,
        "analysis_state": analysis_state,
        "analysis_state_label": (
            status_record.estado.nombre if status_record else "Sin análisis"
        ),
        "analysis_progress": analysis_progress,
        "analysis_in_progress": analysis_in_progress,
        "analysis_failed": analysis_state == "FALLIDO",
        "analysis_error": analysis_error,
        "analysis_status_url": reverse("estado_analisis", args=[application.pk]),
        "datos_personales": personal_data,
        "experiencias": (
            ExperienciaAnalisisCV.objects.filter(analisis=analysis)
            .select_related("profesion")
            .order_by("-fecha_inicio", "-pk")
            if analysis
            else []
        ),
        "educaciones": (
            EducacionAnalisisCV.objects.filter(analisis=analysis)
            .select_related("nivel_educativo", "area_estudio")
            .order_by("-fecha_fin", "-fecha_inicio", "-pk")
            if analysis
            else []
        ),
        "habilidades": (
            HabilidadAnalisisCV.objects.filter(analisis=analysis)
            .select_related("habilidad")
            .order_by("nombre_detectado")
            if analysis
            else []
        ),
        "idiomas": (
            IdiomaAnalisisCV.objects.filter(analisis=analysis)
            .select_related("idioma", "nivel_idioma")
            .order_by("nombre_detectado")
            if analysis
            else []
        ),
        "certificaciones": (
            CertificacionAnalisisCV.objects.filter(analisis=analysis)
            .select_related("certificacion")
            .order_by("nombre_detectado")
            if analysis
            else []
        ),
        "requirements": requirements,
        "requirements_met": sum(result.cumplido for result in results),
        "compatibility_score": (
            evaluation.porcentaje_compatibilidad
            if evaluation and evaluation.porcentaje_compatibilidad is not None
            else None
        ),
        "candidate_name": (
            personal_data.nombre_completo
            if personal_data and personal_data.nombre_completo
            else application.aspirante.usuario.get_full_name()
        ),
        "candidate_email": (
            personal_data.correo
            if personal_data and personal_data.correo
            else application.aspirante.usuario.email
        ),
        "candidate_phone": (
            personal_data.telefono
            if personal_data and personal_data.telefono
            else application.aspirante.telefono
        ),
        "candidate_profession": (
            personal_data.profesion_texto
            if personal_data and personal_data.profesion_texto
            else application.aspirante.profesion
        ),
        "candidate_city": (
            personal_data.ciudad_texto
            if personal_data and personal_data.ciudad_texto
            else application.aspirante.ciudad
        ),
    }
    return render(request, "analisis.html", context)


@roles_required("RRHH", "ADMINISTRADOR")
def estado_analisis(request, postulacion_id):
    application = get_object_or_404(Postulacion, pk=postulacion_id)
    evaluation = get_current_evaluation(application)
    analysis = (
        AnalisisCV.objects.select_related("estado")
        .filter(curriculo=application.curriculo, vigente=True)
        .order_by("-creado_en")
        .first()
    )
    status_record = evaluation or analysis
    status = getattr(status_record, "estado_id", "SIN_ANALISIS")
    return JsonResponse(
        {
            "status": status,
            "label": (
                status_record.estado.nombre if status_record else "Sin análisis"
            ),
            "progress": {
                "PENDIENTE": 10,
                "PROCESANDO": 55,
                "COMPLETADO": 100,
                "FALLIDO": 100,
            }.get(status, 0),
            "error": getattr(status_record, "mensaje_error", None),
        }
    )


@roles_required("ASPIRANTE")
def portal(request):
    expire_offers()
    profile = get_applicant_profile(request.user)
    percentage, completed = profile_completion(profile)
    profile_checklist = _profile_checklist(completed)
    applications = Postulacion.objects.filter(aspirante=profile).select_related(
        "plaza__departamento", "plaza__modalidad_trabajo", "estado"
    ).order_by("-actualizado_en")[:4]
    vacancies = _available_vacancies().exclude(
        postulacion__aspirante=profile
    ).order_by("-publicado_en")[:3]
    curriculum = profile.curriculo_set.filter(activo=True).order_by("-cargado_en").first()
    return render(
        request,
        "portal.html",
        {
            "perfil": profile,
            "profile_percentage": percentage,
            "profile_sections": completed,
            "profile_checklist": profile_checklist,
            "pending_profile_sections": [
                section for section in profile_checklist if not section["completed"]
            ],
            "applications": applications,
            "vacancies": vacancies,
            "curriculum": curriculum,
        },
    )


@login_required
def notificaciones(request):
    notifications = (
        Notificacion.objects.filter(usuario_destinatario=request.user)
        .select_related(
            "tipo",
            "postulacion__plaza",
            "entrevista",
        )
        .order_by("-creado_en", "-pk")
    )
    is_portal = request.user.has_role("ASPIRANTE") and not request.user.has_role(
        "RRHH", "ADMINISTRADOR"
    )
    return render(
        request,
        "notificaciones.html",
        {
            "base_template": "portal_base.html" if is_portal else "base.html",
            "is_portal": is_portal,
            "notificaciones": notifications,
            "unread_count": notifications.filter(leido_en__isnull=True).count(),
        },
    )


@login_required
def marcar_notificacion_leida(request, notificacion_id):
    if request.method == "POST":
        Notificacion.objects.filter(
            pk=notificacion_id,
            usuario_destinatario=request.user,
            leido_en__isnull=True,
        ).update(leido_en=timezone.now())
    return redirect("notificaciones")


@login_required
def marcar_notificaciones_leidas(request):
    if request.method == "POST":
        Notificacion.objects.filter(
            usuario_destinatario=request.user,
            leido_en__isnull=True,
        ).update(leido_en=timezone.now())
    return redirect("notificaciones")


def _available_vacancies():
    now = timezone.now()
    return Plaza.objects.filter(estado_id="PUBLICADA").filter(
        Q(cierra_en__isnull=True) | Q(cierra_en__gt=now)
    ).annotate(
        hired_count=Count(
            "postulacion",
            filter=Q(postulacion__estado_id="CONTRATADA"),
            distinct=True,
        )
    ).filter(hired_count__lt=F("cantidad_vacantes")).select_related(
        "departamento", "profesion", "ciudad", "tipo_empleo", "modalidad_trabajo"
    )


@roles_required("ASPIRANTE")
def perfil_aspirante(request):
    profile = get_applicant_profile(request.user)
    form = FormularioPerfilAspirante(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        save_profile(form, request.user)
        messages.success(request, "Tu información personal fue actualizada.")
        return redirect("perfil_aspirante")
    percentage, completed = profile_completion(profile)
    return render(
        request,
        "perfil_aspirante.html",
        {
            "perfil": profile,
            "form": form,
            "profile_percentage": percentage,
            "profile_sections": completed,
            "experiences": profile.experiencialaboral_set.select_related(
                "profesion", "ciudad"
            ).order_by("-fecha_inicio"),
            "education": profile.formacionacademica_set.select_related(
                "institucion", "nivel_educativo", "area_estudio"
            ).order_by("-fecha_fin", "-fecha_inicio"),
            "skills": profile.habilidadaspirante_set.select_related(
                "habilidad", "nivel_habilidad"
            ).order_by("habilidad__nombre"),
            "languages": profile.idiomaaspirante_set.select_related(
                "idioma", "nivel_idioma"
            ).order_by("idioma__nombre"),
            "certifications": profile.certificacionaspirante_set.select_related(
                "certificacion"
            ).order_by("-emitida_en"),
            "curriculum": profile.curriculo_set.filter(activo=True).order_by(
                "-cargado_en"
            ).first(),
        },
    )


PROFILE_RECORDS = {
    "experiencia": (ExperienciaLaboral, FormularioExperiencia, "Experiencia laboral"),
    "formacion": (FormacionAcademica, FormularioFormacion, "Formación académica"),
    "certificacion": (
        CertificacionAspirante,
        FormularioCertificacionAspirante,
        "Certificación",
    ),
}


@roles_required("ASPIRANTE")
def editar_registro_perfil(request, tipo, registro_id=None):
    config = PROFILE_RECORDS.get(tipo)
    if config is None:
        raise Http404
    model, form_class, title = config
    profile = get_applicant_profile(request.user)
    instance = None
    if registro_id is not None:
        instance = get_object_or_404(model, pk=registro_id, aspirante=profile)
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        save_profile_record(form, profile)
        messages.success(request, f"{title} guardada correctamente.")
        return redirect("perfil_aspirante")
    return render(
        request,
        "formulario_perfil.html",
        {"form": form, "title": title, "editing": instance is not None},
    )


@roles_required("ASPIRANTE")
def eliminar_registro_perfil(request, tipo, registro_id):
    config = PROFILE_RECORDS.get(tipo)
    if config is None:
        raise Http404
    if request.method == "POST":
        profile = get_applicant_profile(request.user)
        get_object_or_404(config[0], pk=registro_id, aspirante=profile).delete()
        messages.success(request, "El registro fue eliminado.")
    return redirect("perfil_aspirante")


@roles_required("ASPIRANTE")
def agregar_habilidad(request):
    profile = get_applicant_profile(request.user)
    form = FormularioHabilidadAspirante(
        request.POST or None, aspirante=profile
    )
    if request.method == "POST" and form.is_valid():
        save_profile_record(form, profile)
        messages.success(request, "Habilidad agregada.")
        return redirect("perfil_aspirante")
    return render(request, "formulario_perfil.html", {"form": form, "title": "Habilidad"})


@roles_required("ASPIRANTE")
def editar_habilidad(request, habilidad_id):
    profile = get_applicant_profile(request.user)
    instance = get_object_or_404(
        HabilidadAspirante,
        aspirante=profile,
        habilidad_id=habilidad_id,
    )
    form = FormularioHabilidadAspirante(
        request.POST or None,
        instance=instance,
        aspirante=profile,
    )
    if request.method == "POST" and form.is_valid():
        save_profile_record(form, profile)
        messages.success(request, "Habilidad actualizada.")
        return redirect("perfil_aspirante")
    return render(
        request,
        "formulario_perfil.html",
        {"form": form, "title": "Habilidad", "editing": True},
    )


@roles_required("ASPIRANTE")
def eliminar_habilidad(request, habilidad_id):
    if request.method == "POST":
        profile = get_applicant_profile(request.user)
        get_object_or_404(
            HabilidadAspirante,
            aspirante=profile,
            habilidad_id=habilidad_id,
        ).delete()
        messages.success(request, "Habilidad eliminada.")
    return redirect("perfil_aspirante")


@roles_required("ASPIRANTE")
def agregar_idioma(request):
    profile = get_applicant_profile(request.user)
    form = FormularioIdiomaAspirante(request.POST or None, aspirante=profile)
    if request.method == "POST" and form.is_valid():
        save_profile_record(form, profile)
        messages.success(request, "Idioma agregado.")
        return redirect("perfil_aspirante")
    return render(request, "formulario_perfil.html", {"form": form, "title": "Idioma"})


@roles_required("ASPIRANTE")
def editar_idioma(request, idioma_id):
    profile = get_applicant_profile(request.user)
    instance = get_object_or_404(
        IdiomaAspirante,
        aspirante=profile,
        idioma_id=idioma_id,
    )
    form = FormularioIdiomaAspirante(
        request.POST or None,
        instance=instance,
        aspirante=profile,
    )
    if request.method == "POST" and form.is_valid():
        save_profile_record(form, profile)
        messages.success(request, "Idioma actualizado.")
        return redirect("perfil_aspirante")
    return render(
        request,
        "formulario_perfil.html",
        {"form": form, "title": "Idioma", "editing": True},
    )


@roles_required("ASPIRANTE")
def eliminar_idioma(request, idioma_id):
    if request.method == "POST":
        profile = get_applicant_profile(request.user)
        get_object_or_404(
            IdiomaAspirante,
            aspirante=profile,
            idioma_id=idioma_id,
        ).delete()
        messages.success(request, "Idioma eliminado.")
    return redirect("perfil_aspirante")


@roles_required("ASPIRANTE")
def cargar_curriculo(request):
    profile = get_applicant_profile(request.user)
    form = FormularioCurriculo(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            save_curriculum(form.cleaned_data["archivo"], profile)
        except ValidationError as error:
            form.add_error(None, error.message)
        else:
            messages.success(request, "Tu currículum fue cargado de forma privada.")
            return redirect("perfil_aspirante")
    return render(request, "formulario_perfil.html", {"form": form, "title": "Currículum"})


@login_required
def descargar_curriculo(request, curriculo_id):
    curriculum = get_object_or_404(
        Curriculo.objects.select_related("aspirante__usuario", "proveedor_almacenamiento"),
        pk=curriculo_id,
    )
    is_owner = curriculum.aspirante.usuario_id == request.user.pk
    if not is_owner and not request.user.has_role("RRHH", "ADMINISTRADOR"):
        raise Http404
    try:
        if curriculum.proveedor_almacenamiento.codigo == B2_PROVIDER_CODE:
            response = redirect(
                backblaze_download_url(
                    curriculum.clave_objeto,
                    curriculum.nombre_archivo_original,
                )
            )
            response["Cache-Control"] = "private, no-store"
            return response
        path = curriculum_path(curriculum)
    except ValidationError as error:
        raise Http404(error.message) from error
    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=curriculum.nombre_archivo_original,
        content_type="application/pdf",
    )


@roles_required("ASPIRANTE")
def oportunidades(request):
    profile = get_applicant_profile(request.user)
    vacancies = _available_vacancies().order_by("-publicado_en")
    query = request.GET.get("q", "").strip()
    if query:
        vacancies = vacancies.filter(
            Q(titulo__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(departamento__nombre__icontains=query)
        )
    applied_ids = set(
        Postulacion.objects.filter(aspirante=profile).values_list("plaza_id", flat=True)
    )
    page = Paginator(vacancies, 9).get_page(request.GET.get("pagina"))
    return render(
        request,
        "oportunidades.html",
        {"page": page, "query": query, "applied_ids": applied_ids},
    )


@roles_required("ASPIRANTE")
def detalle_oportunidad(request, plaza_id):
    profile = get_applicant_profile(request.user)
    vacancy = get_object_or_404(_available_vacancies(), pk=plaza_id)
    requirements = RequisitoPlaza.objects.filter(plaza=vacancy).select_related(
        "tipo"
    ).order_by("orden_visualizacion")
    availability = RequisitoDisponibilidad.objects.filter(
        requisito__plaza=vacancy
    ).first()
    application = Postulacion.objects.filter(plaza=vacancy, aspirante=profile).first()
    form = FormularioPostulacion(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            application = create_application(
                vacancy.pk,
                profile,
                form.cleaned_data["carta_presentacion"],
            )
        except ValidationError as error:
            form.add_error(None, error.message)
        else:
            messages.success(request, "Tu postulación fue enviada.")
            return redirect("mi_postulacion", postulacion_id=application.pk)
    return render(
        request,
        "detalle_oportunidad.html",
        {
            "plaza": vacancy,
            "requirements": requirements,
            "availability": availability,
            "postulacion": application,
            "form": form,
            "curriculum": profile.curriculo_set.filter(activo=True).first(),
        },
    )


@roles_required("ASPIRANTE")
def mis_postulaciones(request):
    expire_offers()
    profile = get_applicant_profile(request.user)
    applications = Postulacion.objects.filter(aspirante=profile).select_related(
        "plaza__departamento", "plaza__modalidad_trabajo", "estado"
    ).order_by("-actualizado_en")
    return render(request, "mis_postulaciones.html", {"postulaciones": applications})


@roles_required("ASPIRANTE")
def mi_postulacion(request, postulacion_id):
    profile = get_applicant_profile(request.user)
    application = get_object_or_404(
        Postulacion.objects.select_related(
            "plaza__departamento", "plaza__modalidad_trabajo", "estado", "curriculo"
        ),
        pk=postulacion_id,
        aspirante=profile,
    )
    expire_offers(application.pk)
    application.refresh_from_db()
    history = HistorialEstadoPostulacion.objects.filter(
        postulacion=application
    ).order_by("-cambiado_en")
    entrevistas = Entrevista.objects.filter(postulacion=application).select_related(
        "estado"
    ).order_by("-inicia_en")
    return render(
        request,
        "mi_postulacion.html",
        {
            "postulacion": application,
            "history": history,
            "entrevistas": entrevistas,
            "ofertas": OfertaLaboral.objects.filter(postulacion=application)
            .select_related("estado")
            .order_by("-creado_en"),
        },
    )


@roles_required("ASPIRANTE")
def retirar_postulacion(request, postulacion_id):
    profile = get_applicant_profile(request.user)
    application = get_object_or_404(Postulacion, pk=postulacion_id, aspirante=profile)
    if request.method == "POST":
        try:
            transition_application(
                application.pk,
                "RETIRADA",
                request.user,
                request.POST.get("motivo") or "Retirada por el aspirante.",
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "Tu postulación fue retirada.")
    return redirect("mi_postulacion", postulacion_id=application.pk)


@login_required
def cambiar_contrasena(request):
    form = FormularioCambioContrasena(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Tu contraseña fue actualizada.")
        return redirect(_home_for(user))
    return render(
        request,
        "auth/formulario_contrasena.html",
        {"form": form, "title": "Cambiar contraseña"},
    )


def solicitar_recuperacion(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = Usuario.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = request.build_absolute_uri(
                reverse(
                    "restablecer_contrasena",
                    kwargs={"uidb64": uid, "token": token},
                )
            )
            send_mail(
                "Restablece tu contraseña de Sistema CV",
                f"Abre este enlace para crear una nueva contraseña:\n\n{reset_url}",
                None,
                [user.email],
            )
        return render(
            request,
            "auth/recuperacion_enviada.html",
            {"title": "Revisa tu correo"},
        )
    return render(
        request,
        "auth/solicitar_recuperacion.html",
        {"title": "Recuperar contraseña"},
    )


def restablecer_contrasena(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = Usuario.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return render(request, "auth/enlace_invalido.html", status=400)

    form = FormularioNuevaContrasena(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contraseña actualizada. Ya puedes iniciar sesión.")
        return redirect("index")
    return render(
        request,
        "auth/formulario_contrasena.html",
        {"form": form, "title": "Crear nueva contraseña"},
    )


def verificar_correo(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = Usuario.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
        return render(
            request,
            "auth/enlace_invalido.html",
            {
                "title": "Enlace de verificación no válido",
                "verification_invalid": True,
            },
            status=400,
        )

    if not email_verification_token.check_token(user, token):
        return render(
            request,
            "auth/enlace_invalido.html",
            {
                "title": "Enlace de verificación no válido",
                "verification_invalid": True,
            },
            status=400,
        )

    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified"])
    messages.success(request, "Tu correo fue verificado. Ya puedes iniciar sesión.")
    return redirect("index")


def salud(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    return JsonResponse({"aplicacion": "disponible", "base_de_datos": "conectada"})
