import logging

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, connection
from django.http import JsonResponse
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
)
from reclutamiento.models import Usuario
from reclutamiento.permissions import roles_required
from reclutamiento.emails import send_verification_email
from reclutamiento.services import register_applicant
from reclutamiento.tokens import email_verification_token


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
    return render(request, "dashboard.html")


@roles_required("RRHH", "ADMINISTRADOR")
def plazas(request):
    return render(request, "plazas.html")


@roles_required("RRHH", "ADMINISTRADOR")
def nueva_plaza(request):
    return render(request, "nueva_plaza.html")


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
