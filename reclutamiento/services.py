from django.db import transaction
from django.utils import timezone

from reclutamiento.models import PerfilAspirante, RolUsuario, UsuarioRol


@transaction.atomic
def register_applicant(form):
    user = form.save()
    applicant_role = RolUsuario.objects.get(codigo="ASPIRANTE")
    UsuarioRol.objects.create(
        usuario=user,
        rol=applicant_role,
        asignado_en=timezone.now(),
    )
    PerfilAspirante.objects.create(
        usuario=user,
        acepta_reubicacion=False,
        acepta_viajar=False,
        creado_en=timezone.now(),
        actualizado_en=timezone.now(),
    )
    return user
