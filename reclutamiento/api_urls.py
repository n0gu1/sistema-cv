from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from reclutamiento.api_views import (
    ApplicantViewSet,
    ApplicationStatusCatalogViewSet,
    ApplicationViewSet,
    CertificationCatalogViewSet,
    CityCatalogViewSet,
    DepartmentCatalogViewSet,
    EducationLevelCatalogViewSet,
    EmploymentTypeCatalogViewSet,
    LanguageCatalogViewSet,
    LanguageLevelCatalogViewSet,
    ProfessionCatalogViewSet,
    SkillCatalogViewSet,
    SkillLevelCatalogViewSet,
    StudyAreaCatalogViewSet,
    VacancyStatusCatalogViewSet,
    VacancyViewSet,
    WorkModeCatalogViewSet,
)


router = DefaultRouter()
router.register("plazas", VacancyViewSet, basename="api-plaza")
router.register("aspirantes", ApplicantViewSet, basename="api-aspirante")
router.register("postulaciones", ApplicationViewSet, basename="api-postulacion")
router.register("catalogos/departamentos", DepartmentCatalogViewSet, basename="api-departamento")
router.register("catalogos/profesiones", ProfessionCatalogViewSet, basename="api-profesion")
router.register("catalogos/habilidades", SkillCatalogViewSet, basename="api-habilidad")
router.register("catalogos/idiomas", LanguageCatalogViewSet, basename="api-idioma")
router.register("catalogos/tipos-empleo", EmploymentTypeCatalogViewSet, basename="api-tipo-empleo")
router.register("catalogos/modalidades", WorkModeCatalogViewSet, basename="api-modalidad")
router.register("catalogos/niveles-educativos", EducationLevelCatalogViewSet, basename="api-nivel-educativo")
router.register("catalogos/niveles-habilidad", SkillLevelCatalogViewSet, basename="api-nivel-habilidad")
router.register("catalogos/niveles-idioma", LanguageLevelCatalogViewSet, basename="api-nivel-idioma")
router.register("catalogos/areas-estudio", StudyAreaCatalogViewSet, basename="api-area-estudio")
router.register("catalogos/ciudades", CityCatalogViewSet, basename="api-ciudad")
router.register("catalogos/certificaciones", CertificationCatalogViewSet, basename="api-certificacion")
router.register("catalogos/estados-plaza", VacancyStatusCatalogViewSet, basename="api-estado-plaza")
router.register("catalogos/estados-postulacion", ApplicationStatusCatalogViewSet, basename="api-estado-postulacion")


urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="api-schema"),
        name="api-redoc",
    ),
    path("", include(router.urls)),
]
