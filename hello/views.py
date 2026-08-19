import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, connection
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
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
    FormularioCertificacionAspirante,
    FormularioCurriculo,
    FormularioEntrevista,
    FormularioEstadoEntrevista,
    FormularioExperiencia,
    FormularioFormacion,
    FormularioHabilidadAspirante,
    FormularioIdiomaAspirante,
    FormularioNuevaContrasena,
    FormularioPerfilAspirante,
    FormularioPostulacion,
    FormularioReenvioVerificacion,
    FormularioRegistroAspirante,
    FormularioPlaza,
)
from reclutamiento.models import (
    CertificacionAspirante,
    Curriculo,
    Departamento,
    Entrevista,
    ExperienciaLaboral,
    FormacionAcademica,
    HabilidadAspirante,
    HistorialEstadoPostulacion,
    HistorialEstadoPlaza,
    IdiomaAspirante,
    ModalidadTrabajo,
    PerfilAspirante,
    Plaza,
    Postulacion,
    RequisitoPlaza,
    Usuario,
)
from reclutamiento.permissions import roles_required
from reclutamiento.applications import (
    ALLOWED_APPLICATION_TRANSITIONS,
    ALLOWED_INTERVIEW_TRANSITIONS,
    create_application,
    schedule_interview,
    transition_application,
    transition_interview,
    vacancy_accepts_applications,
)
from reclutamiento.candidates import (
    curriculum_path,
    get_applicant_profile,
    profile_completion,
    save_curriculum,
    save_profile,
    save_profile_record,
)
from reclutamiento.emails import send_verification_email
from reclutamiento.services import register_applicant
from reclutamiento.tokens import email_verification_token
from reclutamiento.vacancies import (
    ALLOWED_TRANSITIONS,
    get_vacancy_form_initial,
    save_vacancy,
    transition_vacancy,
)


logger = logging.getLogger(__name__)


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
    if request.method == "POST" and form.is_valid():
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

    return render(request, "login.html", {"form": form})


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


@roles_required("RRHH", "ADMINISTRADOR")
def dashboard(request):
    vacancy_counts = dict(
        Plaza.objects.values("estado_id")
        .annotate(total=Count("id"))
        .values_list("estado_id", "total")
    )
    priority_vacancies = (
        Plaza.objects.filter(estado_id__in=("PUBLICADA", "PAUSADA"))
        .select_related("departamento", "modalidad_trabajo")
        .annotate(applicant_count=Count("postulacion", distinct=True))
        .order_by("cierra_en", "-actualizado_en")[:3]
    )
    return render(
        request,
        "dashboard.html",
        {
            "vacancy_counts": vacancy_counts,
            "active_vacancies": vacancy_counts.get("PUBLICADA", 0),
            "pending_vacancies": vacancy_counts.get("BORRADOR", 0)
            + vacancy_counts.get("PAUSADA", 0),
            "closed_vacancies": vacancy_counts.get("CERRADA", 0),
            "total_applicants": Usuario.objects.filter(
                usuariorol__rol__codigo="ASPIRANTE"
            ).distinct().count(),
            "priority_vacancies": priority_vacancies,
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def plazas(request):
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
    if request.method == "POST" and form.is_valid():
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
            "catalogs_ready": form.has_required_catalogs(),
            "editing": False,
        },
    )


@roles_required("RRHH", "ADMINISTRADOR")
def editar_plaza(request, plaza_id):
    vacancy = get_object_or_404(Plaza.objects.select_related("estado"), pk=plaza_id)
    if vacancy.estado_id == "CERRADA":
        messages.error(request, "Una plaza cerrada no puede editarse.")
        return redirect("detalle_plaza", plaza_id=vacancy.pk)
    form = FormularioPlaza(
        request.POST or None,
        instance=vacancy,
        initial=get_vacancy_form_initial(vacancy),
    )
    if request.method == "POST" and form.is_valid():
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
            "catalogs_ready": form.has_required_catalogs(),
            "editing": True,
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
def postulaciones(request):
    applications = Postulacion.objects.select_related(
        "aspirante__usuario",
        "plaza__departamento",
        "estado",
    ).order_by("-actualizado_en")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip().upper()
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
        Postulacion.objects.values_list("estado_id")
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
            "total_count": Postulacion.objects.count(),
            "filters": {"q": query, "estado": status},
        },
    )


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
    history = HistorialEstadoPostulacion.objects.filter(
        postulacion=application
    ).select_related("cambiado_por").order_by("-cambiado_en")
    interviews = Entrevista.objects.filter(postulacion=application).select_related(
        "estado", "creado_por"
    ).order_by("-inicia_en")
    for interview in interviews:
        interview.available_transitions = sorted(
            ALLOWED_INTERVIEW_TRANSITIONS.get(interview.estado_id, set())
        )
    transitions = ALLOWED_APPLICATION_TRANSITIONS.get(application.estado_id, set()) - {
        "RETIRADA"
    }
    status_choices = [
        (status.codigo, status.nombre)
        for status in Postulacion._meta.get_field("estado").remote_field.model.objects.filter(
            codigo__in=transitions
        )
    ]
    return render(
        request,
        "detalle_postulacion.html",
        {
            "postulacion": application,
            "history": history,
            "interviews": interviews,
            "state_form": FormularioCambioEstadoPostulacion(estados=status_choices),
            "has_state_transitions": bool(status_choices),
            "interview_form": FormularioEntrevista(),
        },
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
def programar_entrevista(request, postulacion_id):
    if request.method != "POST":
        return redirect("detalle_postulacion", postulacion_id=postulacion_id)
    form = FormularioEntrevista(request.POST)
    if form.is_valid():
        try:
            schedule_interview(form, postulacion_id, request.user)
        except (ValidationError, Postulacion.DoesNotExist) as error:
            message = error.message if isinstance(error, ValidationError) else "La postulación no existe."
            messages.error(request, message)
        else:
            messages.success(request, "La entrevista fue programada.")
    else:
        messages.error(request, "Revisa los datos de la entrevista.")
    return redirect("detalle_postulacion", postulacion_id=postulacion_id)


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
def analisis(request):
    return render(request, "analisis.html")


@roles_required("ASPIRANTE")
def portal(request):
    profile = get_applicant_profile(request.user)
    percentage, completed = profile_completion(profile)
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
            "applications": applications,
            "vacancies": vacancies,
            "curriculum": curriculum,
        },
    )


def _available_vacancies():
    now = timezone.now()
    return Plaza.objects.filter(estado_id="PUBLICADA").filter(
        Q(cierra_en__isnull=True) | Q(cierra_en__gt=now)
    ).select_related(
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
            "postulacion": application,
            "form": form,
            "curriculum": profile.curriculo_set.filter(activo=True).first(),
        },
    )


@roles_required("ASPIRANTE")
def mis_postulaciones(request):
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
    history = HistorialEstadoPostulacion.objects.filter(
        postulacion=application
    ).order_by("-cambiado_en")
    interviews = Entrevista.objects.filter(postulacion=application).select_related(
        "estado"
    ).order_by("-inicia_en")
    return render(
        request,
        "mi_postulacion.html",
        {"postulacion": application, "history": history, "interviews": interviews},
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
                "Restablece tu contraseña de Nexo Talento",
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
        user = get_object_or_404(Usuario, pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError):
        return render(request, "auth/enlace_invalido.html", status=400)

    if not email_verification_token.check_token(user, token):
        return render(request, "auth/enlace_invalido.html", status=400)

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
