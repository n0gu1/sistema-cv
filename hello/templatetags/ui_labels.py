from django import template


register = template.Library()

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
