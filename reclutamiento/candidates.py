import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from reclutamiento.models import Curriculo, PerfilAspirante, ProveedorAlmacenamiento


PROFILE_SECTIONS = (
    "datos",
    "experiencia",
    "formacion",
    "habilidades",
    "idiomas",
    "certificaciones",
    "curriculo",
)


def get_applicant_profile(user):
    now = timezone.now()
    profile, _ = PerfilAspirante.objects.get_or_create(
        usuario=user,
        defaults={
            "acepta_reubicacion": False,
            "acepta_viajar": False,
            "creado_en": now,
            "actualizado_en": now,
        },
    )
    return profile


def profile_completion(profile):
    completed = {
        "datos": all(
            (
                profile.usuario.first_name,
                profile.usuario.last_name,
                profile.profesion_id,
                profile.telefono,
                profile.resumen_profesional,
            )
        ),
        "experiencia": profile.experiencialaboral_set.exists(),
        "formacion": profile.formacionacademica_set.exists(),
        "habilidades": profile.habilidadaspirante_set.exists(),
        "idiomas": profile.idiomaaspirante_set.exists(),
        "certificaciones": profile.certificacionaspirante_set.exists(),
        "curriculo": profile.curriculo_set.filter(activo=True).exists(),
    }
    percentage = round(sum(completed.values()) * 100 / len(PROFILE_SECTIONS))
    return percentage, completed


@transaction.atomic
def save_profile(form, user):
    now = timezone.now()
    profile = form.save(commit=False)
    profile.actualizado_en = now
    profile.save()
    user.first_name = form.cleaned_data["first_name"].strip()
    user.last_name = form.cleaned_data["last_name"].strip()
    user.updated_at = now
    user.save(update_fields=("first_name", "last_name", "updated_at"))
    return profile


def save_profile_record(form, profile):
    record = form.save(commit=False)
    record.aspirante = profile
    record.save()
    return record


def _private_curriculum_root():
    return Path(settings.PRIVATE_UPLOAD_ROOT) / "curriculos"


@transaction.atomic
def save_curriculum(uploaded_file, profile):
    provider = ProveedorAlmacenamiento.objects.filter(codigo="LOCAL_PRIVADO").first()
    if provider is None:
        raise ValidationError(
            "Falta el proveedor LOCAL_PRIVADO. Ejecuta inicializar_catalogos."
        )

    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    checksum = digest.hexdigest()
    duplicate = Curriculo.objects.filter(
        aspirante=profile,
        suma_sha256=checksum,
    ).first()

    relative_key = f"{profile.pk}/{uuid.uuid4().hex}.pdf"
    destination = _private_curriculum_root() / relative_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as target:
            for chunk in uploaded_file.chunks():
                target.write(chunk)
        now = timezone.now()
        Curriculo.objects.filter(aspirante=profile, activo=True).update(activo=False)
        return Curriculo.objects.create(
            aspirante=profile,
            proveedor_almacenamiento=provider,
            clave_objeto=relative_key,
            nombre_archivo_original=uploaded_file.name[:255],
            tipo_mime="application/pdf",
            tamano_bytes=uploaded_file.size,
            suma_sha256=checksum,
            duplicado_de=duplicate,
            cargado_en=now,
            activo=True,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def curriculum_path(curriculum):
    if curriculum.proveedor_almacenamiento.codigo != "LOCAL_PRIVADO":
        raise ValidationError("Este currículo se encuentra en almacenamiento externo.")
    root = _private_curriculum_root().resolve()
    path = (root / curriculum.clave_objeto).resolve()
    if root not in path.parents or not path.is_file():
        raise ValidationError("El archivo del currículo no está disponible.")
    return path
