from django import template
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


register = template.Library()

_secure_url_validator = URLValidator(schemes=("http", "https"))

STATE_LABELS = {
    "BORRADOR": "Borrador",
    "PUBLICADA": "Publicada",
    "PAUSADA": "Pausada",
    "CERRADA": "Cerrada",
    "ENVIADA": "Enviada",
    "EN_REVISION": "En revisión",
    "PRESELECCIONADA": "Preseleccionada",
    "ENTREVISTA": "Entrevista",
    "OFERTA_ENVIADA": "Oferta enviada",
    "CONTRATADA": "Contratada",
    "RECHAZADA": "Rechazada",
    "RETIRADA": "Retirada",
    "PROGRAMADA": "Programada",
    "CONFIRMADA": "Confirmada",
    "COMPLETADA": "Completada",
    "CANCELADA": "Cancelada",
    "NO_ASISTIO": "No asistió",
}


@register.filter
def readable_status(value):
    if value is None:
        return ""
    code = str(value)
    return STATE_LABELS.get(code, code.replace("_", " ").capitalize())


@register.filter
def safe_external_url(value):
    """Return only absolute HTTP(S) URLs that are safe to place in hrefs."""
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        _secure_url_validator(value)
    except ValidationError:
        return ""
    return value
