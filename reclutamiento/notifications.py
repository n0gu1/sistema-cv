import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import DatabaseError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from reclutamiento.models import (
    CanalNotificacion,
    EntregaNotificacion,
    EstadoEntrega,
    EstadoEntrevista,
    EstadoPostulacion,
    IntentoEntregaNotificacion,
    Notificacion,
    TipoNotificacion,
)


logger = logging.getLogger(__name__)

CONFIRMATION_TYPE = "CONFIRMACION_POSTULACION"
STATUS_CHANGE_TYPE = "CAMBIO_ESTADO"
INTERVIEW_INVITATION_TYPE = "INVITACION_ENTREVISTA"
OFFER_TYPE = "OFERTA_LABORAL"
OFFER_RESPONSE_TYPE = "RESPUESTA_OFERTA"


def _catalog(model, code):
    return model.objects.get(codigo=code)


def create_notification(
    *,
    recipient,
    type_code,
    title,
    message,
    application=None,
    interview=None,
):
    now = timezone.now()
    notification = Notificacion.objects.create(
        usuario_destinatario=recipient,
        tipo=_catalog(TipoNotificacion, type_code),
        postulacion=application,
        entrevista=interview,
        titulo=title,
        mensaje=message,
        creado_en=now,
    )

    EntregaNotificacion.objects.create(
        notificacion=notification,
        canal=_catalog(CanalNotificacion, "APLICACION"),
        estado=_catalog(EstadoEntrega, "ENVIADO"),
        programado_en=now,
        enviado_en=now,
    )
    email_delivery = EntregaNotificacion.objects.create(
        notificacion=notification,
        canal=_catalog(CanalNotificacion, "CORREO"),
        estado=_catalog(EstadoEntrega, "PENDIENTE"),
        direccion_destino=recipient.email,
        programado_en=now,
    )
    transaction.on_commit(
        lambda delivery_id=email_delivery.pk: deliver_notification_email(delivery_id),
        # Un flujo confirmado no debe convertirse en HTTP 500 por el correo.
        robust=True,
    )
    return notification


def _record_delivery_failure(delivery_id, error):
    try:
        with transaction.atomic():
            delivery = EntregaNotificacion.objects.select_for_update().get(
                pk=delivery_id
            )
            if delivery.estado_id in {"ENVIADO", "FALLIDO"}:
                return
            delivery.estado_id = "FALLIDO"
            delivery.save(update_fields=("estado",))
            IntentoEntregaNotificacion.objects.create(
                entrega=delivery,
                intentado_en=timezone.now(),
                exitoso=False,
                mensaje_error=str(error),
            )
    except EntregaNotificacion.DoesNotExist:
        return
    except Exception:
        logger.exception(
            "No se pudo registrar el fallo de entrega por correo id=%s", delivery_id
        )


def deliver_notification_email(delivery_id):
    try:
        return _deliver_notification_email(delivery_id)
    except Exception as error:
        _record_delivery_failure(delivery_id, error)
        logger.exception(
            "No se pudo procesar la entrega de notificación por correo id=%s",
            delivery_id,
        )
        return False


def _deliver_notification_email(delivery_id):
    try:
        with transaction.atomic():
            delivery = (
                EntregaNotificacion.objects.select_for_update()
                .select_related(
                    "notificacion__usuario_destinatario",
                    "notificacion__tipo",
                    "notificacion__entrevista",
                )
                .get(pk=delivery_id)
            )
            if delivery.estado_id == "ENVIADO":
                return True
            delivery.estado_id = "PROCESANDO"
            delivery.save(update_fields=("estado",))
            notification = delivery.notificacion
    except EntregaNotificacion.DoesNotExist:
        return False

    try:
        text_body = render_to_string(
            "emails/notificacion.txt", {"notification": notification}
        )
        html_body = render_to_string(
            "emails/notificacion.html", {"notification": notification}
        )
        message = EmailMultiAlternatives(
            subject=notification.titulo,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.direccion_destino],
        )
        message.attach_alternative(html_body, "text/html")
        if not message.send():
            raise RuntimeError("El backend de correo no aceptó el mensaje.")
    except Exception as error:
        _record_delivery_failure(delivery_id, error)
        logger.exception(
            "No se pudo entregar la notificación por correo id=%s", delivery_id
        )
        return False

    with transaction.atomic():
        delivery = EntregaNotificacion.objects.select_for_update().get(pk=delivery_id)
        delivery.estado_id = "ENVIADO"
        delivery.enviado_en = timezone.now()
        delivery.save(update_fields=("estado", "enviado_en"))
        IntentoEntregaNotificacion.objects.create(
            entrega=delivery,
            intentado_en=timezone.now(),
            exitoso=True,
        )
    return True


def notify_application_created(application):
    vacancy = application.plaza
    return create_notification(
        recipient=application.aspirante.usuario,
        type_code=CONFIRMATION_TYPE,
        title="Postulación recibida",
        message=(
            f"Recibimos tu postulación para «{vacancy.titulo}». "
            "Te avisaremos cuando avance el proceso."
        ),
        application=application,
    )


def notify_application_status_changed(
    application, previous_code, current_code, actor=None
):
    recipient = application.aspirante.usuario
    if actor is not None and actor.pk == recipient.pk:
        return None
    previous_status = _catalog(EstadoPostulacion, previous_code)
    current_status = application.estado
    return create_notification(
        recipient=recipient,
        type_code=STATUS_CHANGE_TYPE,
        title="Actualización de tu postulación",
        message=(
            f"Tu postulación para «{application.plaza.titulo}» cambió de "
            f"«{previous_status.nombre}» a «{current_status.nombre}»."
        ),
        application=application,
    )


def notify_interview_scheduled(interview):
    application = interview.postulacion
    start = interview.inicia_en_local.strftime("%d/%m/%Y %H:%M")
    location = interview.detalle_ubicacion or "Reunión virtual"
    meeting_url = f" Enlace: {interview.url_reunion}" if interview.url_reunion else ""
    return create_notification(
        recipient=application.aspirante.usuario,
        type_code=INTERVIEW_INVITATION_TYPE,
        title="Invitación a entrevista",
        message=(
            f"Tienes una entrevista para «{application.plaza.titulo}» el "
            f"{start} ({interview.zona_horaria}). Lugar: {location}."
            f"{meeting_url}"
        ),
        application=application,
        interview=interview,
    )


def notify_interview_status_changed(interview, previous_code, current_code):
    previous_status = _catalog(EstadoEntrevista, previous_code)
    current_status = interview.estado
    application = interview.postulacion
    return create_notification(
        recipient=application.aspirante.usuario,
        type_code=STATUS_CHANGE_TYPE,
        title="Actualización de entrevista",
        message=(
            f"La entrevista para «{application.plaza.titulo}» cambió de "
            f"«{previous_status.nombre}» a «{current_status.nombre}»."
        ),
        application=application,
        interview=interview,
    )


def notify_offer_created(offer):
    application = offer.postulacion
    return create_notification(
        recipient=application.aspirante.usuario,
        type_code=OFFER_TYPE,
        title="Nueva oferta laboral",
        message=(
            f"Recibiste una oferta para «{application.plaza.titulo}». "
            f"Puedes responderla hasta el {offer.vence_en:%d/%m/%Y %H:%M}."
        ),
        application=application,
    )


def notify_offer_response(offer):
    return create_notification(
        recipient=offer.creado_por,
        type_code=OFFER_RESPONSE_TYPE,
        title="Respuesta a oferta laboral",
        message=(
            f"La oferta para «{offer.postulacion.plaza.titulo}» ahora está "
            f"en estado «{offer.estado.nombre}»."
        ),
        application=offer.postulacion,
    )


def unread_notification_count(user):
    if not user or not user.is_authenticated:
        return 0
    try:
        return Notificacion.objects.filter(
            usuario_destinatario=user,
            leido_en__isnull=True,
        ).count()
    except DatabaseError:
        # Some lightweight test setups omit the optional notification tables.
        return 0
