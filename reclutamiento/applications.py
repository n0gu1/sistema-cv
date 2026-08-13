from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from reclutamiento.models import (
    Entrevista,
    EstadoEntrevista,
    EstadoPostulacion,
    HistorialEstadoPostulacion,
    Plaza,
    Postulacion,
)


ALLOWED_APPLICATION_TRANSITIONS = {
    "ENVIADA": {"EN_REVISION", "RETIRADA"},
    "EN_REVISION": {"PRESELECCIONADA", "RECHAZADA", "RETIRADA"},
    "PRESELECCIONADA": {"ENTREVISTA", "RECHAZADA", "RETIRADA"},
    "ENTREVISTA": {"OFERTA_ENVIADA", "RECHAZADA", "RETIRADA"},
    "OFERTA_ENVIADA": {"CONTRATADA", "RECHAZADA", "RETIRADA"},
    "CONTRATADA": set(),
    "RECHAZADA": set(),
    "RETIRADA": set(),
}


ALLOWED_INTERVIEW_TRANSITIONS = {
    "PROGRAMADA": {"CONFIRMADA", "CANCELADA"},
    "CONFIRMADA": {"COMPLETADA", "CANCELADA", "NO_ASISTIO"},
    "COMPLETADA": set(),
    "CANCELADA": set(),
    "NO_ASISTIO": set(),
}


def vacancy_accepts_applications(vacancy, now=None):
    now = now or timezone.now()
    return vacancy.estado_id == "PUBLICADA" and (
        vacancy.cierra_en is None or vacancy.cierra_en > now
    )


@transaction.atomic
def create_application(vacancy_id, profile, cover_letter=None):
    vacancy = Plaza.objects.select_for_update().select_related("estado").get(
        pk=vacancy_id
    )
    if not vacancy_accepts_applications(vacancy):
        raise ValidationError("Esta plaza ya no recibe postulaciones.")
    if Postulacion.objects.filter(plaza=vacancy, aspirante=profile).exists():
        raise ValidationError("Ya te postulaste a esta plaza.")
    curriculum = profile.curriculo_set.filter(activo=True).order_by(
        "-cargado_en"
    ).first()
    if curriculum is None:
        raise ValidationError("Carga un currículum antes de postularte.")

    now = timezone.now()
    try:
        application = Postulacion.objects.create(
            plaza=vacancy,
            aspirante=profile,
            curriculo=curriculum,
            estado=EstadoPostulacion.objects.get(codigo="ENVIADA"),
            carta_presentacion=(cover_letter or "").strip() or None,
            postulado_en=now,
            actualizado_en=now,
        )
    except IntegrityError as error:
        raise ValidationError("Ya te postulaste a esta plaza.") from error
    HistorialEstadoPostulacion.objects.create(
        postulacion=application,
        codigo_estado_anterior=None,
        codigo_estado_nuevo="ENVIADA",
        cambiado_por=profile.usuario,
        motivo="Postulación enviada por el aspirante.",
        cambiado_en=now,
    )
    return application


@transaction.atomic
def transition_application(application_id, target_code, user, reason=None):
    application = Postulacion.objects.select_for_update().select_related("estado").get(
        pk=application_id
    )
    current_code = application.estado_id
    target_code = target_code.upper()
    if target_code not in ALLOWED_APPLICATION_TRANSITIONS.get(current_code, set()):
        raise ValidationError(
            f"No se permite cambiar una postulación de {current_code} a {target_code}."
        )
    if target_code == "RETIRADA" and application.aspirante_id != user.pk:
        raise ValidationError("Solo el aspirante puede retirar su postulación.")
    if target_code != "RETIRADA" and not user.has_role("RRHH", "ADMINISTRADOR"):
        raise ValidationError("No tienes permiso para cambiar este estado.")

    now = timezone.now()
    application.estado = EstadoPostulacion.objects.get(codigo=target_code)
    application.actualizado_en = now
    application.retirado_en = now if target_code == "RETIRADA" else None
    application.save(update_fields=("estado", "actualizado_en", "retirado_en"))
    HistorialEstadoPostulacion.objects.create(
        postulacion=application,
        codigo_estado_anterior=current_code,
        codigo_estado_nuevo=target_code,
        cambiado_por=user,
        motivo=(reason or "").strip() or None,
        cambiado_en=now,
    )
    return application


@transaction.atomic
def schedule_interview(form, application_id, user):
    application = Postulacion.objects.select_for_update().select_related("estado").get(
        pk=application_id
    )
    if application.estado_id == "PRESELECCIONADA":
        transition_application(
            application.pk,
            "ENTREVISTA",
            user,
            "Entrevista programada.",
        )
    elif application.estado_id != "ENTREVISTA":
        raise ValidationError(
            "La postulación debe estar preseleccionada o en entrevista."
        )
    interview = form.save(commit=False)
    interview.postulacion = application
    interview.creado_por = user
    interview.estado = EstadoEntrevista.objects.get(codigo="PROGRAMADA")
    interview.creado_en = timezone.now()
    interview.save()
    return interview


@transaction.atomic
def transition_interview(interview_id, target_code):
    interview = Entrevista.objects.select_for_update().select_related("estado").get(
        pk=interview_id
    )
    current_code = interview.estado_id
    target_code = target_code.upper()
    if target_code not in ALLOWED_INTERVIEW_TRANSITIONS.get(current_code, set()):
        raise ValidationError(
            f"No se permite cambiar una entrevista de {current_code} a {target_code}."
        )
    interview.estado = EstadoEntrevista.objects.get(codigo=target_code)
    interview.save(update_fields=("estado",))
    return interview
