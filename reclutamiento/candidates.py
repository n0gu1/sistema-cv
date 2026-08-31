import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from reclutamiento.models import Curriculo, PerfilAspirante, ProveedorAlmacenamiento
from reclutamiento.storage import (
    B2_PROVIDER_CODE,
    delete_backblaze_object,
    upload_backblaze_object,
)


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
                profile.ciudad_id,
                profile.telefono,
                profile.direccion,
                profile.resumen_profesional,
                profile.disponible_desde,
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


@transaction.atomic
def save_profile_record(form, profile):
    record = form.save(commit=False)
    record.aspirante = profile
    record.save()
    return record


def _private_curriculum_root():
    return Path(settings.PRIVATE_UPLOAD_ROOT) / "curriculos"


def _curriculum_provider():
    provider_code = B2_PROVIDER_CODE if settings.BACKBLAZE_ENABLED else "LOCAL_PRIVADO"
    provider = ProveedorAlmacenamiento.objects.filter(codigo=provider_code).first()
    if provider is None:
        raise ValidationError(
            f"Falta el proveedor {provider_code}. Ejecuta inicializar_catalogos."
        )
    return provider


def _backblaze_object_key(relative_key):
    prefix = settings.BACKBLAZE_OBJECT_PREFIX.strip("/")
    return f"{prefix}/{relative_key}" if prefix else relative_key


@transaction.atomic
def save_curriculum(uploaded_file, profile):
    provider = _curriculum_provider()
    use_backblaze = provider.codigo == B2_PROVIDER_CODE

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
    storage_key = _backblaze_object_key(relative_key) if use_backblaze else relative_key
    destination = None
    upload_attempted = False
    try:
        if use_backblaze:
            upload_attempted = True
            upload_backblaze_object(uploaded_file, storage_key, checksum)
        else:
            destination = _private_curriculum_root() / relative_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as target:
                for chunk in uploaded_file.chunks():
                    target.write(chunk)
        now = timezone.now()
        Curriculo.objects.filter(aspirante=profile, activo=True).update(activo=False)
        return Curriculo.objects.create(
            aspirante=profile,
            proveedor_almacenamiento=provider,
            clave_objeto=storage_key,
            nombre_archivo_original=uploaded_file.name[:255],
            tipo_mime="application/pdf",
            tamano_bytes=uploaded_file.size,
            suma_sha256=checksum,
            duplicado_de=duplicate,
            cargado_en=now,
            activo=True,
        )
    except Exception:
        if use_backblaze and upload_attempted:
            delete_backblaze_object(storage_key)
        elif destination is not None:
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
