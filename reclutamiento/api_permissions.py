from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_staff(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "has_role", lambda *roles: False)(
            "RRHH", "ADMINISTRADOR"
        )
    )


def _is_applicant(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "has_role", lambda *roles: False)("ASPIRANTE")
    )


class PublicVacancyPermission(BasePermission):
    """Anyone may read the public vacancy catalogue; staff may manage it."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or _is_staff(request.user)


class StaffOnlyPermission(BasePermission):
    def has_permission(self, request, view):
        return _is_staff(request.user)


class ApplicantAccessPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if view.action == "create":
            return _is_applicant(user)
        return _is_staff(user) or _is_applicant(user)

    def has_object_permission(self, request, view, obj):
        return _is_staff(request.user) or obj.aspirante.usuario_id == request.user.pk


class ApplicantProfilePermission(BasePermission):
    def has_permission(self, request, view):
        return _is_staff(request.user) or _is_applicant(request.user)

    def has_object_permission(self, request, view, obj):
        return _is_staff(request.user) or obj.usuario_id == request.user.pk
