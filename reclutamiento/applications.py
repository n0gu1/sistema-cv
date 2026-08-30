from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from reclutamiento.models import (
    Entrevista,
    EstadoEntrevista,
    EstadoOferta,
    EstadoPostulacion,
    HistorialEstadoPostulacion,
    OfertaLaboral,
    Plaza,
    Postulacion,
)
from reclutamiento.notifications import (
    notify_application_created,
    notify_application_status_changed,
    notify_interview_scheduled,
    notify_interview_status_changed,
    notify_offer_created,
    notify_offer_response,
)
from reclutamiento.vacancies import transition_vacancy


OFFER_SENT_STATE = "OFERTA_ENVIADA"
TERMINAL_APPLICATION_STATES = {"CONTRATADA", "RECHAZADA", "RETIRADA"}
ACTIVE_INTERVIEW_STATES = {"PROGRAMADA", "CONFIRMADA"}


ALLOWED_APPLICATION_TRANSITIONS = {
    "ENVIADA": {"EN_REVISION", "RETIRADA"},
    "EN_REVISION": {"PRESELECCIONADA", "RECHAZADA", "RETIRADA"},
    "PRESELECCIONADA": {"ENTREVISTA", "RECHAZADA", "RETIRADA"},
    "ENTREVISTA": {OFFER_SENT_STATE, "RECHAZADA", "RETIRADA"},
    OFFER_SENT_STATE: {"CONTRATADA", "RECHAZADA", "RETIRADA"},
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
    if vacancy.estado_id != "PUBLICADA" or (
        vacancy.cierra_en is not None and vacancy.cierra_en <= now
    ):
        return False
    return Postulacion.objects.filter(
        plaza_id=vacancy.pk,
        estado_id="CONTRATADA",
    ).count() < vacancy.cantidad_vacantes


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
    notify_application_created(application)
    return application


@transaction.atomic
def transition_application(application_id, target_code, user, reason=None):
    target_code = target_code.upper()
    vacancy = None
    if target_code == "CONTRATADA":
        vacancy_id = Postulacion.objects.values_list("plaza_id", flat=True).get(
            pk=application_id
        )
        vacancy = Plaza.objects.select_for_update().get(pk=vacancy_id)
    application = Postulacion.objects.select_for_update().select_related("estado").get(
        pk=application_id
    )
    current_code = application.estado_id
    if target_code == OFFER_SENT_STATE and not OfertaLaboral.objects.filter(
        postulacion=application,
        estado_id="ENVIADA",
    ).exists():
        raise ValidationError(
            "Registra las condiciones y el vencimiento de la oferta antes de enviarla."
        )
    if target_code == "CONTRATADA" and current_code != OFFER_SENT_STATE:
        raise ValidationError(
            "La postulación debe tener una oferta aceptada antes de contratarla."
        )
    if target_code not in ALLOWED_APPLICATION_TRANSITIONS.get(current_code, set()):
        raise ValidationError(
            f"No se permite cambiar una postulación de {current_code} a {target_code}."
        )
    if target_code == "RETIRADA" and application.aspirante_id != user.pk:
        raise ValidationError("Solo el aspirante puede retirar su postulación.")
    if target_code != "RETIRADA" and not user.has_role("RRHH", "ADMINISTRADOR"):
        raise ValidationError("No tienes permiso para cambiar este estado.")
    if target_code == "CONTRATADA":
        if not OfertaLaboral.objects.select_for_update().filter(
            postulacion=application,
            estado_id="ACEPTADA",
        ).exists():
            raise ValidationError(
                "El aspirante debe aceptar la oferta antes de ser contratado."
            )
        hired_count = Postulacion.objects.filter(
            plaza_id=vacancy.pk,
            estado_id="CONTRATADA",
        ).count()
        if hired_count >= vacancy.cantidad_vacantes:
            raise ValidationError(
                "La plaza ya alcanzó la cantidad de vacantes disponible."
            )

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
    notify_application_status_changed(application, current_code, target_code, user)
    if target_code in TERMINAL_APPLICATION_STATES:
        _cancel_active_interviews(application.pk)
    if target_code in {"RECHAZADA", "RETIRADA"}:
        _cancel_active_offers(application.pk, now)
    if target_code == "CONTRATADA" and hired_count + 1 >= vacancy.cantidad_vacantes:
        if vacancy.estado_id in {"PUBLICADA", "PAUSADA"}:
            transition_vacancy(
                vacancy.pk,
                "CERRADA",
                user,
                "Cierre automático al completar la cantidad de vacantes.",
            )
        _resolve_remaining_applications(vacancy.pk, application.pk, user, now)
    return application


def _cancel_active_interviews(application_id):
    cancel_state = EstadoEntrevista.objects.get(codigo="CANCELADA")
    interviews = Entrevista.objects.select_for_update().select_related("estado").filter(
        postulacion_id=application_id,
        estado_id__in=ACTIVE_INTERVIEW_STATES,
    )
    for interview in interviews:
        previous_code = interview.estado_id
        interview.estado = cancel_state
        interview.save(update_fields=("estado",))
        notify_interview_status_changed(interview, previous_code, "CANCELADA")


def _cancel_active_offers(application_id, now):
    OfertaLaboral.objects.select_for_update().filter(
        postulacion_id=application_id,
        estado_id__in={"ENVIADA", "ACEPTADA"},
    ).update(
        estado_id="CANCELADA",
        actualizado_en=now,
    )


def _resolve_remaining_applications(vacancy_id, hired_application_id, user, now):
    remaining = list(
        Postulacion.objects.select_for_update()
        .select_related("estado", "aspirante__usuario", "plaza")
        .filter(plaza_id=vacancy_id)
        .exclude(pk=hired_application_id)
        .exclude(estado_id__in=TERMINAL_APPLICATION_STATES)
    )
    rejected_state = EstadoPostulacion.objects.get(codigo="RECHAZADA")
    reason = "La plaza completó la cantidad de vacantes disponibles."
    for application in remaining:
        previous_code = application.estado_id
        application.estado = rejected_state
        application.actualizado_en = now
        application.save(update_fields=("estado", "actualizado_en"))
        HistorialEstadoPostulacion.objects.create(
            postulacion=application,
            codigo_estado_anterior=previous_code,
            codigo_estado_nuevo="RECHAZADA",
            cambiado_por=user,
            motivo=reason,
            cambiado_en=now,
        )
        _cancel_active_interviews(application.pk)
        _cancel_active_offers(application.pk, now)
        notify_application_status_changed(
            application,
            previous_code,
            "RECHAZADA",
            user,
        )


@transaction.atomic
def create_offer(application_id, user, conditions, expires_at):
    if not user.has_role("RRHH", "ADMINISTRADOR"):
        raise ValidationError("No tienes permiso para enviar ofertas laborales.")
    application = (
        Postulacion.objects.select_for_update()
        .select_related("estado", "aspirante__usuario", "plaza")
        .get(pk=application_id)
    )
    if application.estado_id != "ENTREVISTA":
        raise ValidationError(
            "La postulación debe estar en entrevista para recibir una oferta."
        )
    now = timezone.now()
    if expires_at <= now:
        raise ValidationError("El vencimiento de la oferta debe estar en el futuro.")
    conditions = (conditions or "").strip()
    if not conditions:
        raise ValidationError("Las condiciones de la oferta son obligatorias.")
    if OfertaLaboral.objects.select_for_update().filter(
        postulacion=application,
        estado_id__in={"ENVIADA", "ACEPTADA"},
    ).exists():
        raise ValidationError("La postulación ya tiene una oferta activa.")

    offer = OfertaLaboral.objects.create(
        postulacion=application,
        creado_por=user,
        estado=EstadoOferta.objects.get(codigo="ENVIADA"),
        condiciones=conditions,
        vence_en=expires_at,
        enviada_en=now,
        creado_en=now,
        actualizado_en=now,
    )
    transition_application(
        application.pk,
        OFFER_SENT_STATE,
        user,
        "Oferta laboral enviada al aspirante.",
    )
    notify_offer_created(offer)
    return offer


@transaction.atomic
def respond_offer(offer_id, user, response_code):
    application_id = OfertaLaboral.objects.values_list(
        "postulacion_id", flat=True
    ).get(pk=offer_id)
    application = Postulacion.objects.select_for_update().select_related("estado").get(
        pk=application_id
    )
    offer = (
        OfertaLaboral.objects.select_for_update()
        .select_related("postulacion__aspirante__usuario", "postulacion__plaza")
        .get(pk=offer_id)
    )
    if application.aspirante.usuario_id != user.pk:
        raise ValidationError("Solo el aspirante puede responder esta oferta.")
    if offer.estado_id != "ENVIADA" or application.estado_id != OFFER_SENT_STATE:
        raise ValidationError("Esta oferta ya no admite respuestas.")

    now = timezone.now()
    if offer.vence_en <= now:
        offer.estado_id = "VENCIDA"
        offer.actualizado_en = now
        offer.save(update_fields=("estado", "actualizado_en"))
        _reject_application_from_offer(
            application,
            user,
            now,
            "La oferta laboral venció sin respuesta.",
        )
        offer.refresh_from_db()
        notify_offer_response(offer)
        return offer

    response_code = response_code.upper()
    if response_code not in {"ACEPTADA", "RECHAZADA"}:
        raise ValidationError("Selecciona aceptar o rechazar la oferta.")
    offer.estado_id = response_code
    offer.respuesta = response_code
    offer.respondida_en = now
    offer.actualizado_en = now
    offer.save(
        update_fields=("estado", "respuesta", "respondida_en", "actualizado_en")
    )
    if response_code == "RECHAZADA":
        _reject_application_from_offer(
            application,
            user,
            now,
            "Oferta laboral rechazada por el aspirante.",
        )
    offer.refresh_from_db()
    notify_offer_response(offer)
    return offer


def _reject_application_from_offer(application, user, now, reason):
    previous_code = application.estado_id
    application.estado = EstadoPostulacion.objects.get(codigo="RECHAZADA")
    application.actualizado_en = now
    application.save(update_fields=("estado", "actualizado_en"))
    HistorialEstadoPostulacion.objects.create(
        postulacion=application,
        codigo_estado_anterior=previous_code,
        codigo_estado_nuevo="RECHAZADA",
        cambiado_por=user,
        motivo=reason,
        cambiado_en=now,
    )
    _cancel_active_interviews(application.pk)


def expire_offers(application_id=None, now=None):
    now = now or timezone.now()
    expired = OfertaLaboral.objects.filter(
        estado_id="ENVIADA",
        vence_en__lte=now,
    )
    if application_id is not None:
        expired = expired.filter(postulacion_id=application_id)
    pending = list(expired.values_list("pk", "postulacion_id"))
    expired_count = 0
    for offer_id, target_application_id in pending:
        with transaction.atomic():
            application = (
                Postulacion.objects.select_for_update()
                .select_related("estado", "aspirante__usuario", "plaza")
                .get(pk=target_application_id)
            )
            offer = (
                OfertaLaboral.objects.select_for_update()
                .select_related("creado_por", "estado", "postulacion__plaza")
                .get(pk=offer_id)
            )
            if offer.estado_id != "ENVIADA" or offer.vence_en > now:
                continue
            offer.estado_id = "VENCIDA"
            offer.actualizado_en = now
            offer.save(update_fields=("estado", "actualizado_en"))
            if application.estado_id == OFFER_SENT_STATE:
                previous_code = application.estado_id
                _reject_application_from_offer(
                    application,
                    None,
                    now,
                    "La oferta laboral venció sin respuesta.",
                )
                application.refresh_from_db()
                notify_application_status_changed(
                    application,
                    previous_code,
                    "RECHAZADA",
                )
            offer.refresh_from_db()
            notify_offer_response(offer)
            expired_count += 1
    return expired_count


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
    notify_interview_scheduled(interview)
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
    notify_interview_status_changed(interview, current_code, target_code)
    return interview
