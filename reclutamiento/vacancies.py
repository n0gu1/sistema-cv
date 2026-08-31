from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from reclutamiento.models import (
    EstadoPlaza,
    HistorialEstadoPlaza,
    Plaza,
    Postulacion,
    RequisitoCertificacion,
    RequisitoDisponibilidad,
    RequisitoEducacion,
    RequisitoExperiencia,
    RequisitoHabilidad,
    RequisitoIdioma,
    RequisitoPlaza,
    ResultadoRequisitoEvaluacion,
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
                initial["profesion"] = detail.profesion_nombre
        elif kind == "EDUCACION":
            detail = RequisitoEducacion.objects.filter(requisito=requirement).first()
            if detail:
                initial["nivel_educativo"] = detail.nivel_educativo_minimo_nombre
                initial["area_estudio"] = detail.area_estudio_nombre
        elif kind == "HABILIDAD":
            detail = RequisitoHabilidad.objects.filter(requisito=requirement).first()
            if detail:
                target = mandatory_skills if requirement.obligatorio else desired_skills
                target.append(detail.habilidad_nombre)
        elif kind == "IDIOMA":
            detail = RequisitoIdioma.objects.filter(requisito=requirement).first()
            if detail:
                initial["idioma"] = detail.idioma_nombre
                initial["nivel_idioma"] = detail.nivel_idioma_minimo_nombre
        elif kind == "CERTIFICACION":
            detail = RequisitoCertificacion.objects.filter(requisito=requirement).first()
            if detail:
                certifications.append(detail.certificacion_nombre)
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
                {
                    "meses_minimos": years * 12,
                    "profesion": None,
                    "profesion_texto": cleaned_data.get("profesion"),
                },
            )
        )
    education = cleaned_data.get("nivel_educativo")
    if education:
        specs.append(
            (
                "EDUCACION",
                True,
                f"Nivel educativo mínimo: {education}.",
                {
                    "nivel_educativo_minimo": None,
                    "nivel_educativo_texto": education,
                    "area_estudio": None,
                    "area_estudio_texto": cleaned_data.get("area_estudio"),
                },
            )
        )
    for skill in cleaned_data.get("habilidades_obligatorias") or []:
        specs.append(
            (
                "HABILIDAD",
                True,
                f"Habilidad obligatoria: {skill}.",
                {"habilidad": None, "habilidad_texto": skill},
            )
        )
    for skill in cleaned_data.get("habilidades_deseables") or []:
        specs.append(
            (
                "HABILIDAD",
                False,
                f"Habilidad deseable: {skill}.",
                {"habilidad": None, "habilidad_texto": skill},
            )
        )
    language = cleaned_data.get("idioma")
    if language:
        language_level = cleaned_data.get("nivel_idioma")
        specs.append(
            (
                "IDIOMA",
                True,
                f"{language}: {language_level}." if language_level else f"{language}.",
                {
                    "idioma": None,
                    "idioma_texto": language,
                    "nivel_idioma_minimo": None,
                    "nivel_idioma_minimo_texto": language_level,
                },
            )
        )
    for certification in cleaned_data.get("certificaciones") or []:
        specs.append(
            (
                "CERTIFICACION",
                False,
                f"Certificación: {certification}.",
                {
                    "certificacion": None,
                    "certificacion_texto": certification,
                    "debe_estar_vigente": True,
                },
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
    _replace_requirement_specs(vacancy, _requirement_specs(cleaned_data))


def _replace_requirement_specs(vacancy, specs):
    if ResultadoRequisitoEvaluacion.objects.filter(
        requisito__plaza=vacancy
    ).exists():
        raise ValidationError(
            "Los requisitos ya tienen evaluaciones asociadas y no pueden reemplazarse."
        )
    try:
        RequisitoPlaza.objects.filter(plaza=vacancy).delete()
    except ProtectedError as error:
        raise ValidationError(
            "Los requisitos ya tienen evaluaciones asociadas y no pueden reemplazarse."
        ) from error

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
def save_vacancy(form, user, publish=False, publish_reason=None):
    now = timezone.now()
    vacancy = form.save(commit=False)
    creating = vacancy.pk is None
    if not creating:
        locked_vacancy = Plaza.objects.select_for_update().get(pk=vacancy.pk)
        hired_count = Postulacion.objects.filter(
            plaza=locked_vacancy,
            estado_id="CONTRATADA",
        ).count()
        if form.cleaned_data["cantidad_vacantes"] < hired_count:
            raise ValidationError(
                "La cantidad de vacantes no puede ser menor que las contrataciones existentes."
            )
    if creating:
        vacancy.creado_por = user
        vacancy.creado_en = now
        vacancy.estado = EstadoPlaza.objects.get(codigo="BORRADOR")
    vacancy.actualizado_en = now
    vacancy.save()
    if creating:
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
        transition_vacancy(
            vacancy.pk,
            "PUBLICADA",
            user,
            publish_reason or "Publicación inicial.",
        )
        vacancy.refresh_from_db()
    return vacancy


def get_requirement_editor_initial(vacancy):
    general = get_vacancy_form_initial(vacancy)
    skills = []
    languages = []
    certifications = []
    requirements = RequisitoPlaza.objects.filter(plaza=vacancy).select_related("tipo")
    for requirement in requirements:
        if requirement.tipo_id == "HABILIDAD":
            detail = RequisitoHabilidad.objects.filter(requisito=requirement).first()
            if detail:
                skills.append(
                    {
                        "habilidad": detail.habilidad_nombre,
                        "nivel_habilidad_minimo": detail.nivel_habilidad_minimo_nombre,
                        "anios_minimos": detail.anios_minimos,
                        "obligatorio": requirement.obligatorio,
                    }
                )
        elif requirement.tipo_id == "IDIOMA":
            detail = RequisitoIdioma.objects.filter(requisito=requirement).first()
            if detail:
                languages.append(
                    {
                        "idioma": detail.idioma_nombre,
                        "nivel_idioma_minimo": detail.nivel_idioma_minimo_nombre,
                        "obligatorio": requirement.obligatorio,
                    }
                )
        elif requirement.tipo_id == "CERTIFICACION":
            detail = RequisitoCertificacion.objects.filter(requisito=requirement).first()
            if detail:
                certifications.append(
                    {
                        "certificacion": detail.certificacion_nombre,
                        "obligatorio": requirement.obligatorio,
                        "debe_estar_vigente": detail.debe_estar_vigente,
                    }
                )
    return general, skills, languages, certifications


def _active_form_data(formset):
    return [
        form.cleaned_data
        for form in formset.forms
        if form.cleaned_data and not form.cleaned_data.get("DELETE")
    ]


@transaction.atomic
def save_vacancy_requirements(
    vacancy_id,
    general_form,
    skill_formset,
    language_formset,
    certification_formset,
):
    vacancy = Plaza.objects.select_for_update().get(pk=vacancy_id)
    specs = [
        spec
        for spec in _requirement_specs(general_form.cleaned_data)
        if spec[0] not in {"HABILIDAD", "IDIOMA", "CERTIFICACION"}
    ]
    for data in _active_form_data(skill_formset):
        skill = data["habilidad"]
        specs.append(
            (
                "HABILIDAD",
                data["obligatorio"],
                f"Habilidad: {skill}.",
                {
                    "habilidad": None,
                    "habilidad_texto": skill,
                    "nivel_habilidad_minimo": None,
                    "nivel_habilidad_minimo_texto": data.get("nivel_habilidad_minimo"),
                    "anios_minimos": data.get("anios_minimos"),
                },
            )
        )
    for data in _active_form_data(language_formset):
        language = data["idioma"]
        level = data["nivel_idioma_minimo"]
        specs.append(
            (
                "IDIOMA",
                data["obligatorio"],
                f"{language}: {level}.",
                {
                    "idioma": None,
                    "idioma_texto": language,
                    "nivel_idioma_minimo": None,
                    "nivel_idioma_minimo_texto": level,
                },
            )
        )
    for data in _active_form_data(certification_formset):
        certification = data["certificacion"]
        specs.append(
            (
                "CERTIFICACION",
                data["obligatorio"],
                f"Certificación: {certification}.",
                {
                    "certificacion": None,
                    "certificacion_texto": certification,
                    "debe_estar_vigente": data["debe_estar_vigente"],
                },
            )
        )
    if vacancy.estado_id == "PUBLICADA" and not specs:
        raise ValidationError("Una plaza publicada debe conservar al menos un requisito.")
    _replace_requirement_specs(vacancy, specs)
    vacancy.actualizado_en = timezone.now()
    vacancy.save(update_fields=("actualizado_en",))
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
    if target_code == "PUBLICADA" and Postulacion.objects.filter(
        plaza=vacancy,
        estado_id="CONTRATADA",
    ).count() >= vacancy.cantidad_vacantes:
        raise ValidationError("La plaza no tiene vacantes disponibles para publicar.")
    if (
        target_code == "PUBLICADA"
        and vacancy.cierra_en is not None
        and vacancy.cierra_en <= timezone.now()
    ):
        raise ValidationError(
            "No se puede reactivar una plaza cuya fecha de cierre ya venció."
        )

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
