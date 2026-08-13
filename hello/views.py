import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, connection
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)

from reclutamiento.forms import (
    FormularioAcceso,
    FormularioCambioContrasena,
    FormularioNuevaContrasena,
    FormularioReenvioVerificacion,
    FormularioRegistroAspirante,
    FormularioPlaza,
)
from reclutamiento.models import (
    Departamento,
    HistorialEstadoPlaza,
    ModalidadTrabajo,
    Plaza,
    RequisitoPlaza,
    Usuario,
)
from reclutamiento.permissions import roles_required
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
    return render(request, "aspirantes.html")


@roles_required("RRHH", "ADMINISTRADOR")
def analisis(request):
    return render(request, "analisis.html")


@roles_required("ASPIRANTE")
def portal(request):
    return render(request, "portal.html")


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
