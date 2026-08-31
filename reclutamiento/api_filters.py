from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from reclutamiento.models import PerfilAspirante, Plaza, Postulacion


class VacancyFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_query", label="Texto libre")
    estado = filters.CharFilter(field_name="estado_id")
    departamento = filters.CharFilter(method="filter_department")
    profesion = filters.CharFilter(method="filter_profession")
    ciudad = filters.CharFilter(method="filter_city")
    tipo_empleo = filters.CharFilter(method="filter_employment_type")
    modalidad = filters.CharFilter(method="filter_work_mode")
    periodo_salarial = filters.CharFilter(method="filter_salary_period")
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
            "periodo_salarial",
            "abierta",
        )

    def filter_query(self, queryset, name, value):
        return queryset.filter(
            Q(titulo__icontains=value)
            | Q(descripcion__icontains=value)
            | Q(departamento_texto__icontains=value)
            | Q(departamento__nombre__icontains=value)
            | Q(profesion_texto__icontains=value)
            | Q(profesion__nombre__icontains=value)
            | Q(ciudad_texto__icontains=value)
            | Q(ciudad__nombre__icontains=value)
            | Q(tipo_empleo_texto__icontains=value)
            | Q(tipo_empleo__nombre__icontains=value)
            | Q(modalidad_trabajo_texto__icontains=value)
            | Q(modalidad_trabajo__nombre__icontains=value)
            | Q(periodo_salarial_texto__icontains=value)
            | Q(periodo_salarial__nombre__icontains=value)
        )

    def _filter_vacancy_value(self, queryset, value, relation_field, text_field):
        query = Q(**{f"{text_field}__icontains": value}) | Q(
            **{f"{relation_field}__nombre__icontains": value}
        )
        if value.isdigit():
            query |= Q(**{f"{relation_field}_id": value})
        return queryset.filter(query)

    def filter_department(self, queryset, name, value):
        return self._filter_vacancy_value(
            queryset, value, "departamento", "departamento_texto"
        )

    def filter_profession(self, queryset, name, value):
        return self._filter_vacancy_value(
            queryset, value, "profesion", "profesion_texto"
        )

    def filter_city(self, queryset, name, value):
        return self._filter_vacancy_value(queryset, value, "ciudad", "ciudad_texto")

    def filter_employment_type(self, queryset, name, value):
        return self._filter_vacancy_value(
            queryset, value, "tipo_empleo", "tipo_empleo_texto"
        )

    def filter_work_mode(self, queryset, name, value):
        return self._filter_vacancy_value(
            queryset, value, "modalidad_trabajo", "modalidad_trabajo_texto"
        )

    def filter_salary_period(self, queryset, name, value):
        return self._filter_vacancy_value(
            queryset, value, "periodo_salarial", "periodo_salarial_texto"
        )

    def filter_open(self, queryset, name, value):
        open_query = Q(estado_id="PUBLICADA") & (
            Q(cierra_en__isnull=True) | Q(cierra_en__gt=timezone.now())
        )
        return queryset.filter(open_query) if value else queryset.exclude(open_query)


class ApplicantFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_query", label="Texto libre")
    profesion = filters.CharFilter(method="filter_profession")
    ciudad = filters.CharFilter(method="filter_city")
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
            | Q(profesion_texto__icontains=value)
            | Q(profesion__nombre__icontains=value)
            | Q(ciudad_texto__icontains=value)
            | Q(ciudad__nombre__icontains=value)
        )

    def filter_profession(self, queryset, name, value):
        query = Q(profesion_texto__icontains=value) | Q(
            profesion__nombre__icontains=value
        )
        if value.isdigit():
            query |= Q(profesion_id=value)
        return queryset.filter(query)

    def filter_city(self, queryset, name, value):
        query = Q(ciudad_texto__icontains=value) | Q(ciudad__nombre__icontains=value)
        if value.isdigit():
            query |= Q(ciudad_id=value)
        return queryset.filter(query)


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
