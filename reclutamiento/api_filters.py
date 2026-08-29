from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from reclutamiento.models import PerfilAspirante, Plaza, Postulacion


class VacancyFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_query", label="Texto libre")
    estado = filters.CharFilter(field_name="estado_id")
    departamento = filters.NumberFilter(field_name="departamento_id")
    profesion = filters.NumberFilter(field_name="profesion_id")
    ciudad = filters.NumberFilter(field_name="ciudad_id")
    tipo_empleo = filters.NumberFilter(field_name="tipo_empleo_id")
    modalidad = filters.NumberFilter(field_name="modalidad_trabajo_id")
    abierta = filters.BooleanFilter(method="filter_open")

    class Meta:
        model = Plaza
        fields = (
            "q",
            "estado",
            "departamento",
            "profesion",
            "ciudad",
            "tipo_empleo",
            "modalidad",
            "abierta",
        )

    def filter_query(self, queryset, name, value):
        return queryset.filter(
            Q(titulo__icontains=value)
            | Q(descripcion__icontains=value)
            | Q(departamento__nombre__icontains=value)
            | Q(profesion__nombre__icontains=value)
        )

    def filter_open(self, queryset, name, value):
        open_query = Q(estado_id="PUBLICADA") & (
            Q(cierra_en__isnull=True) | Q(cierra_en__gt=timezone.now())
        )
        return queryset.filter(open_query) if value else queryset.exclude(open_query)


class ApplicantFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_query", label="Texto libre")
    profesion = filters.NumberFilter(field_name="profesion_id")
    ciudad = filters.NumberFilter(field_name="ciudad_id")
    acepta_viajar = filters.BooleanFilter()
    acepta_reubicacion = filters.BooleanFilter()

    class Meta:
        model = PerfilAspirante
        fields = (
            "q",
            "profesion",
            "ciudad",
            "acepta_viajar",
            "acepta_reubicacion",
        )

    def filter_query(self, queryset, name, value):
        return queryset.filter(
            Q(usuario__first_name__icontains=value)
            | Q(usuario__last_name__icontains=value)
            | Q(usuario__email__icontains=value)
            | Q(resumen_profesional__icontains=value)
        )


class ApplicationFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_query", label="Texto libre")
    estado = filters.CharFilter(field_name="estado_id")
    plaza = filters.NumberFilter(field_name="plaza_id")
    aspirante = filters.NumberFilter(field_name="aspirante_id")
    actualizado_desde = filters.DateFilter(
        field_name="actualizado_en", lookup_expr="date__gte"
    )
    actualizado_hasta = filters.DateFilter(
        field_name="actualizado_en", lookup_expr="date__lte"
    )

    class Meta:
        model = Postulacion
        fields = (
            "q",
            "estado",
            "plaza",
            "aspirante",
            "actualizado_desde",
            "actualizado_hasta",
        )

    def filter_query(self, queryset, name, value):
        return queryset.filter(
            Q(aspirante__usuario__first_name__icontains=value)
            | Q(aspirante__usuario__last_name__icontains=value)
            | Q(aspirante__usuario__email__icontains=value)
            | Q(plaza__titulo__icontains=value)
        )
