from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from reclutamiento.models import (
    EstadoPlaza,
    HistorialEstadoPlaza,
    Plaza,
    RequisitoCertificacion,
    RequisitoDisponibilidad,
    RequisitoEducacion,
    RequisitoExperiencia,
    RequisitoHabilidad,
    RequisitoIdioma,
    RequisitoPlaza,
    TipoRequisito,
)


ALLOWED_TRANSITIONS = {
    "BORRADOR": {"PUBLICADA", "CERRADA"},
    "PUBLICADA": {"PAUSADA", "CERRADA"},
    "PAUSADA": {"PUBLICADA", "CERRADA"},
    "CERRADA": set(),
}


def get_vacancy_form_initial(vacancy):
    initial = {}
    requirements = RequisitoPlaza.objects.filter(plaza=vacancy).select_related("tipo")
    mandatory_skills = []
    desired_skills = []
    certifications = []
    for requirement in requirements:
        kind = requirement.tipo_id
        if kind == "EXPERIENCIA":
            detail = RequisitoExperiencia.objects.filter(requisito=requirement).first()
            if detail:
                initial["anios_experiencia"] = detail.meses_minimos // 12
        elif kind == "EDUCACION":
            detail = RequisitoEducacion.objects.filter(requisito=requirement).first()
            if detail:
                initial["nivel_educativo"] = detail.nivel_educativo_minimo_id
                initial["area_estudio"] = detail.area_estudio_id
        elif kind == "HABILIDAD":
            detail = RequisitoHabilidad.objects.filter(requisito=requirement).first()
            if detail:
                target = mandatory_skills if requirement.obligatorio else desired_skills
                target.append(detail.habilidad_id)
        elif kind == "IDIOMA":
            detail = RequisitoIdioma.objects.filter(requisito=requirement).first()
            if detail:
                initial["idioma"] = detail.idioma_id
                initial["nivel_idioma"] = detail.nivel_idioma_minimo_id
        elif kind == "CERTIFICACION":
            detail = RequisitoCertificacion.objects.filter(requisito=requirement).first()
            if detail:
                certifications.append(detail.certificacion_id)
        elif kind == "DISPONIBILIDAD":
            detail = RequisitoDisponibilidad.objects.filter(requisito=requirement).first()
            if detail:
                initial.update(
                    {
                        "disponible_desde": detail.requerido_desde,
                        "requiere_viajar": detail.requiere_viajar,
                        "requiere_reubicacion": detail.requiere_reubicacion,
                        "descripcion_horario": detail.descripcion_horario,
                    }
                )
    initial["habilidades_obligatorias"] = mandatory_skills
    initial["habilidades_deseables"] = desired_skills
    initial["certificaciones"] = certifications
    return initial


def _requirement_specs(cleaned_data):
    specs = []
    years = cleaned_data.get("anios_experiencia")
    if years is not None:
        specs.append(
            (
                "EXPERIENCIA",
                True,
                f"Mínimo {years} años de experiencia.",
                {"meses_minimos": years * 12, "profesion": cleaned_data.get("profesion")},
            )
        )
    education = cleaned_data.get("nivel_educativo")
    if education:
        specs.append(
            (
                "EDUCACION",
                True,
                f"Nivel educativo mínimo: {education.nombre}.",
                {
                    "nivel_educativo_minimo": education,
                    "area_estudio": cleaned_data.get("area_estudio"),
                },
            )
        )
    for skill in cleaned_data.get("habilidades_obligatorias") or []:
        specs.append(
            (
                "HABILIDAD",
                True,
                f"Habilidad obligatoria: {skill.nombre}.",
                {"habilidad": skill},
            )
        )
    for skill in cleaned_data.get("habilidades_deseables") or []:
        specs.append(
            (
                "HABILIDAD",
                False,
                f"Habilidad deseable: {skill.nombre}.",
                {"habilidad": skill},
            )
        )
    language = cleaned_data.get("idioma")
    if language:
        specs.append(
            (
                "IDIOMA",
                True,
                f"{language.nombre}: {cleaned_data['nivel_idioma'].nombre}.",
                {"idioma": language, "nivel_idioma_minimo": cleaned_data["nivel_idioma"]},
            )
        )
    for certification in cleaned_data.get("certificaciones") or []:
        specs.append(
            (
                "CERTIFICACION",
                False,
                f"Certificación: {certification.nombre}.",
                {"certificacion": certification, "debe_estar_vigente": True},
            )
        )
    if any(
        cleaned_data.get(field)
        for field in (
            "disponible_desde",
            "requiere_viajar",
            "requiere_reubicacion",
            "descripcion_horario",
        )
    ):
        specs.append(
            (
                "DISPONIBILIDAD",
                True,
                cleaned_data.get("descripcion_horario") or "Disponibilidad requerida.",
                {
                    "requerido_desde": cleaned_data.get("disponible_desde"),
                    "requiere_viajar": cleaned_data.get("requiere_viajar", False),
                    "requiere_reubicacion": cleaned_data.get(
                        "requiere_reubicacion", False
                    ),
                    "descripcion_horario": cleaned_data.get("descripcion_horario") or None,
                },
            )
        )
    return specs


DETAIL_MODELS = {
    "EXPERIENCIA": RequisitoExperiencia,
    "EDUCACION": RequisitoEducacion,
    "HABILIDAD": RequisitoHabilidad,
    "IDIOMA": RequisitoIdioma,
    "CERTIFICACION": RequisitoCertificacion,
    "DISPONIBILIDAD": RequisitoDisponibilidad,
}


def _replace_requirements(vacancy, cleaned_data):
    try:
        RequisitoPlaza.objects.filter(plaza=vacancy).delete()
    except ProtectedError as error:
        raise ValidationError(
            "Los requisitos ya tienen evaluaciones asociadas y no pueden reemplazarse."
        ) from error

    specs = _requirement_specs(cleaned_data)
    if not specs:
        return
    base_weight = (Decimal("100.00") / len(specs)).quantize(Decimal("0.01"))
    allocated = Decimal("0.00")
    kinds = {kind.codigo: kind for kind in TipoRequisito.objects.all()}
    missing_kinds = {spec[0] for spec in specs}.difference(kinds)
    if missing_kinds:
        raise ValidationError(
            "Faltan tipos de requisito en los catálogos: "
            + ", ".join(sorted(missing_kinds))
        )
    for index, (kind_code, mandatory, description, detail_data) in enumerate(specs, 1):
        weight = (
            Decimal("100.00") - allocated if index == len(specs) else base_weight
        )
        requirement = RequisitoPlaza.objects.create(
            plaza=vacancy,
            tipo=kinds[kind_code],
            descripcion=description,
            obligatorio=mandatory,
            peso=weight,
            orden_visualizacion=index,
        )
        DETAIL_MODELS[kind_code].objects.create(
            requisito=requirement,
            **detail_data,
        )
        allocated += weight


@transaction.atomic
def save_vacancy(form, user, publish=False):
    now = timezone.now()
    vacancy = form.save(commit=False)
    creating = vacancy.pk is None
    if creating:
        vacancy.creado_por = user
        vacancy.creado_en = now
        vacancy.estado = EstadoPlaza.objects.get(codigo="BORRADOR")
    vacancy.actualizado_en = now
    vacancy.save()
    _replace_requirements(vacancy, form.cleaned_data)
    if creating:
        HistorialEstadoPlaza.objects.create(
            plaza=vacancy,
            codigo_estado_anterior=None,
            codigo_estado_nuevo="BORRADOR",
            cambiado_por=user,
            motivo="Creación de la plaza.",
            cambiado_en=now,
        )
    if publish:
        transition_vacancy(vacancy.pk, "PUBLICADA", user, "Publicación inicial.")
        vacancy.refresh_from_db()
    return vacancy


@transaction.atomic
def transition_vacancy(vacancy_id, target_code, user, reason=None):
    vacancy = Plaza.objects.select_for_update().select_related("estado").get(
        pk=vacancy_id
    )
    current_code = vacancy.estado_id
    if target_code not in ALLOWED_TRANSITIONS.get(current_code, set()):
        raise ValidationError(
            f"No se permite cambiar una plaza de {current_code} a {target_code}."
        )
    if target_code == "PUBLICADA" and not RequisitoPlaza.objects.filter(
        plaza=vacancy
    ).exists():
        raise ValidationError("Agrega al menos un requisito antes de publicar.")

    now = timezone.now()
    vacancy.estado = EstadoPlaza.objects.get(codigo=target_code)
    vacancy.actualizado_en = now
    if target_code == "PUBLICADA" and vacancy.publicado_en is None:
        vacancy.publicado_en = now
    if target_code == "CERRADA":
        vacancy.cierra_en = now
    vacancy.save(
        update_fields=("estado", "actualizado_en", "publicado_en", "cierra_en")
    )
    HistorialEstadoPlaza.objects.create(
        plaza=vacancy,
        codigo_estado_anterior=current_code,
        codigo_estado_nuevo=target_code,
        cambiado_por=user,
        motivo=(reason or "").strip() or None,
        cambiado_en=now,
    )
    return vacancy
