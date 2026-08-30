from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, F, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiTypes,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from reclutamiento.ai_analysis import (
    AnalysisError,
    enqueue_application_analysis,
    get_current_evaluation,
)
from reclutamiento.api_filters import ApplicantFilter, ApplicationFilter, VacancyFilter
from reclutamiento.api_permissions import (
    ApplicantAccessPermission,
    ApplicantProfilePermission,
    PublicVacancyPermission,
    StaffOnlyPermission,
    CatalogWritePermission,
)
from reclutamiento.api_serializers import (
    AnalysisActionSerializer,
    AnalysisJobSerializer,
    AnalysisSerializer,
    ApplicantSerializer,
    ApplicationAnalysisSerializer,
    ApplicationCreateSerializer,
    ApplicationSerializer,
    ApplicationStateSerializer,
    CatalogSerializer,
    CertificationCatalogSerializer,
    CityCatalogWriteSerializer,
    EvaluationDetailSerializer,
    InstitutionCatalogSerializer,
    ProfessionCatalogSerializer,
    OfferCreateSerializer,
    OfferResponseSerializer,
    OfferSerializer,
    SkillCatalogSerializer,
    VacancySerializer,
)
from reclutamiento.applications import (
    create_offer,
    expire_offers,
    respond_offer,
    transition_application,
)
from reclutamiento.models import (
    AnalisisCV,
    AreaEstudio,
    Certificacion,
    Ciudad,
    Departamento,
    EstadoPlaza,
    EstadoPostulacion,
    Habilidad,
    Idioma,
    Institucion,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    ModalidadTrabajo,
    OfertaLaboral,
    PerfilAspirante,
    Plaza,
    Postulacion,
    Profesion,
    RequisitoPlaza,
    TipoEmpleo,
)


def _is_staff(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "has_role", lambda *roles: False)(
            "RRHH", "ADMINISTRADOR"
        )
    )


def _vacancy_queryset():
    requirement_queryset = RequisitoPlaza.objects.select_related(
        "tipo",
        "requisitohabilidad__habilidad",
        "requisitohabilidad__nivel_habilidad_minimo",
        "requisitoidioma__idioma",
        "requisitoidioma__nivel_idioma_minimo",
        "requisitocertificacion__certificacion",
        "requisitoeducacion__nivel_educativo_minimo",
        "requisitoeducacion__area_estudio",
        "requisitoexperiencia__profesion",
    )
    return Plaza.objects.select_related(
        "departamento",
        "profesion",
        "creado_por",
        "ciudad__region__pais",
        "tipo_empleo",
        "modalidad_trabajo",
        "periodo_salarial",
        "estado",
    ).prefetch_related(
        Prefetch("requisitoplaza_set", queryset=requirement_queryset)
    )


@extend_schema_view(
    list=extend_schema(tags=["Plazas"]),
    retrieve=extend_schema(tags=["Plazas"]),
)
class VacancyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VacancySerializer
    permission_classes = (PublicVacancyPermission,)
    filterset_class = VacancyFilter
    ordering_fields = (
        "titulo",
        "publicado_en",
        "actualizado_en",
        "salario_minimo",
    )
    ordering = ("-publicado_en", "-actualizado_en")

    def get_queryset(self):
        queryset = _vacancy_queryset()
        if _is_staff(self.request.user):
            return queryset
        return queryset.filter(estado_id="PUBLICADA").filter(
            Q(cierra_en__isnull=True) | Q(cierra_en__gt=timezone.now())
        ).annotate(
            hired_count=Count(
                "postulacion",
                filter=Q(postulacion__estado_id="CONTRATADA"),
                distinct=True,
            )
        ).filter(hired_count__lt=F("cantidad_vacantes"))


def _applicant_queryset():
    return PerfilAspirante.objects.select_related(
        "usuario",
        "profesion",
        "ciudad__region__pais",
    ).prefetch_related(
        "experiencialaboral_set__profesion",
        "experiencialaboral_set__ciudad__region__pais",
        "formacionacademica_set__institucion__ciudad__region__pais",
        "formacionacademica_set__nivel_educativo",
        "formacionacademica_set__area_estudio",
        "habilidadaspirante_set__habilidad",
        "habilidadaspirante_set__nivel_habilidad",
        "idiomaaspirante_set__idioma",
        "idiomaaspirante_set__nivel_idioma",
        "certificacionaspirante_set__certificacion",
        "curriculo_set__proveedor_almacenamiento",
    )


@extend_schema_view(
    list=extend_schema(tags=["Aspirantes"]),
    retrieve=extend_schema(
        tags=["Aspirantes"],
        parameters=[
            OpenApiParameter(
                "id",
                OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ],
    ),
)
class ApplicantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApplicantSerializer
    permission_classes = (ApplicantProfilePermission,)
    filterset_class = ApplicantFilter
    ordering_fields = ("usuario__last_name", "usuario__first_name", "actualizado_en")
    ordering = ("usuario__last_name", "usuario__first_name")

    def get_queryset(self):
        queryset = _applicant_queryset()
        if _is_staff(self.request.user):
            return queryset
        if not self.request.user.is_authenticated:
            return queryset.none()
        return queryset.filter(usuario=self.request.user)


def _application_queryset():
    return Postulacion.objects.select_related(
        "plaza__estado",
        "plaza__departamento",
        "plaza__ciudad__region__pais",
        "aspirante__usuario",
        "aspirante__profesion",
        "aspirante__ciudad__region__pais",
        "curriculo__proveedor_almacenamiento",
        "estado",
    )


@extend_schema_view(
    list=extend_schema(tags=["Postulaciones"]),
    retrieve=extend_schema(tags=["Postulaciones"]),
)
class ApplicationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ApplicationSerializer
    permission_classes = (ApplicantAccessPermission,)
    filterset_class = ApplicationFilter
    ordering_fields = ("postulado_en", "actualizado_en", "estado_id")
    ordering = ("-actualizado_en", "-pk")

    def get_queryset(self):
        if self.request.user.is_authenticated:
            expire_offers()
        queryset = _application_queryset()
        if _is_staff(self.request.user):
            return queryset
        if not self.request.user.is_authenticated:
            return queryset.none()
        return queryset.filter(aspirante__usuario=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return ApplicationCreateSerializer
        if self.action == "estado":
            return ApplicationStateSerializer
        if self.action == "ofertas" and self.request.method == "POST":
            return OfferCreateSerializer
        if self.action == "responder_oferta":
            return OfferResponseSerializer
        if self.action == "analisis" and self.request.method == "POST":
            return AnalysisActionSerializer
        return ApplicationSerializer

    @extend_schema(
        request=ApplicationCreateSerializer,
        responses={status.HTTP_201_CREATED: ApplicationSerializer},
        tags=["Postulaciones"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        response_serializer = ApplicationSerializer(
            application,
            context=self.get_serializer_context(),
        )
        headers = self.get_success_headers(serializer.data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @extend_schema(
        request=OfferCreateSerializer,
        responses={200: OfferSerializer(many=True), 201: OfferSerializer},
        tags=["Postulaciones"],
    )
    @action(detail=True, methods=["get", "post"], url_path="ofertas")
    def ofertas(self, request, *args, **kwargs):
        application = self.get_object()
        if request.method == "GET":
            offers = OfertaLaboral.objects.filter(postulacion=application).select_related(
                "estado", "creado_por"
            ).order_by("-creado_en")
            return Response(OfferSerializer(offers, many=True).data)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            offer = create_offer(
                application.pk,
                request.user,
                serializer.validated_data["condiciones"],
                serializer.validated_data["vence_en"],
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(OfferSerializer(offer).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=OfferResponseSerializer,
        responses={200: OfferSerializer},
        tags=["Postulaciones"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="ofertas/responder",
    )
    def responder_oferta(self, request, *args, **kwargs):
        application = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer = serializer.validated_data["oferta"]
        if offer.postulacion_id != application.pk:
            raise ValidationError({"oferta_id": "La oferta no pertenece a la postulación."})
        try:
            offer = respond_offer(
                offer.pk,
                request.user,
                serializer.validated_data["respuesta"],
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(OfferSerializer(offer).data)

    @extend_schema(
        request=ApplicationStateSerializer,
        responses={200: ApplicationSerializer},
        tags=["Postulaciones"],
    )
    @action(detail=True, methods=["post"], url_path="estado")
    def estado(self, request, *args, **kwargs):
        application = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            application = transition_application(
                application.pk,
                serializer.validated_data["estado"],
                request.user,
                serializer.validated_data.get("motivo"),
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        application = _application_queryset().get(pk=application.pk)
        return Response(
            ApplicationSerializer(
                application,
                context=self.get_serializer_context(),
            ).data
        )

    @extend_schema(
        request=None,
        responses={200: ApplicationAnalysisSerializer},
        methods=["GET"],
        tags=["Postulaciones"],
    )
    @extend_schema(
        request=AnalysisActionSerializer,
        responses={202: AnalysisJobSerializer, 200: AnalysisJobSerializer},
        methods=["POST"],
        tags=["Postulaciones"],
    )
    @action(detail=True, methods=["get", "post"], url_path="analisis")
    def analisis(self, request, *args, **kwargs):
        application = self.get_object()
        if request.method == "GET":
            evaluation = get_current_evaluation(application)
            analysis = evaluation.analisis_cv if evaluation else (
                AnalisisCV.objects.select_related("estado")
                .filter(curriculo=application.curriculo, vigente=True)
                .order_by("-creado_en")
                .first()
            )
            status_record = evaluation or analysis
            data = {
                "status": getattr(status_record, "estado_id", "SIN_ANALISIS"),
                "analysis": analysis,
                "evaluation": evaluation,
            }
            return Response(
                ApplicationAnalysisSerializer(
                    data,
                    context=self.get_serializer_context(),
                ).data
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = enqueue_application_analysis(
                application,
                force=serializer.validated_data["force"],
            )
        except AnalysisError as error:
            raise ValidationError({"detail": str(error)}) from error
        response_status = status.HTTP_202_ACCEPTED
        if job.state == "COMPLETADO" or job.synchronous:
            response_status = status.HTTP_200_OK
        elif job.state == "FALLIDO":
            response_status = status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            AnalysisJobSerializer(job).data,
            status=response_status,
        )

    def get_permissions(self):
        if self.action == "analisis" or (
            self.action == "ofertas" and self.request.method == "POST"
        ):
            return [StaffOnlyPermission()]
        return super().get_permissions()


class CatalogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CatalogSerializer
    permission_classes = (AllowAny,)
    pagination_class = None
    ordering_fields = ("nombre",)
    ordering = ("nombre",)


class ManagedCatalogViewSet(viewsets.ModelViewSet):
    serializer_class = CatalogSerializer
    write_serializer_class = None
    permission_classes = (CatalogWritePermission,)
    pagination_class = None
    ordering_fields = ("nombre",)
    ordering = ("nombre",)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return self.write_serializer_class
        return self.serializer_class

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as error:
            raise ValidationError(
                {"detail": "El registro está en uso y no puede eliminarse."}
            ) from error


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class DepartmentCatalogViewSet(CatalogViewSet):
    queryset = Departamento.objects.filter(activo=True)


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class ProfessionCatalogViewSet(ManagedCatalogViewSet):
    queryset = Profesion.objects.all()
    write_serializer_class = ProfessionCatalogSerializer


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class SkillCatalogViewSet(ManagedCatalogViewSet):
    queryset = Habilidad.objects.all()
    write_serializer_class = SkillCatalogSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if _is_staff(self.request.user) else queryset.filter(activo=True)


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class LanguageCatalogViewSet(CatalogViewSet):
    queryset = Idioma.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class EmploymentTypeCatalogViewSet(CatalogViewSet):
    queryset = TipoEmpleo.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class WorkModeCatalogViewSet(CatalogViewSet):
    queryset = ModalidadTrabajo.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class EducationLevelCatalogViewSet(CatalogViewSet):
    queryset = NivelEducativo.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class SkillLevelCatalogViewSet(CatalogViewSet):
    queryset = NivelHabilidad.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class LanguageLevelCatalogViewSet(CatalogViewSet):
    queryset = NivelIdioma.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class StudyAreaCatalogViewSet(CatalogViewSet):
    queryset = AreaEstudio.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class CityCatalogViewSet(ManagedCatalogViewSet):
    queryset = Ciudad.objects.select_related("region__pais").all()
    write_serializer_class = CityCatalogWriteSerializer


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class CertificationCatalogViewSet(ManagedCatalogViewSet):
    queryset = Certificacion.objects.all()
    write_serializer_class = CertificationCatalogSerializer


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class InstitutionCatalogViewSet(ManagedCatalogViewSet):
    queryset = Institucion.objects.select_related("ciudad").all()
    write_serializer_class = InstitutionCatalogSerializer


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class VacancyStatusCatalogViewSet(CatalogViewSet):
    queryset = EstadoPlaza.objects.all()


@extend_schema_view(list=extend_schema(tags=["Catálogos"]), retrieve=extend_schema(tags=["Catálogos"]))
class ApplicationStatusCatalogViewSet(CatalogViewSet):
    queryset = EstadoPostulacion.objects.all()
