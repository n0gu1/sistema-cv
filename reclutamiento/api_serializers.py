from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from reclutamiento.ai_analysis import get_current_evaluation
from reclutamiento.applications import create_application
from reclutamiento.candidates import get_applicant_profile, profile_completion
from reclutamiento.models import (
    AnalisisCV,
    AreaEstudio,
    Certificacion,
    CertificacionAspirante,
    CertificacionAnalisisCV,
    Ciudad,
    Curriculo,
    DatosPersonalesAnalisisCV,
    Departamento,
    EducacionAnalisisCV,
    Entrevista,
    EvaluacionPostulacion,
    ExperienciaAnalisisCV,
    ExperienciaLaboral,
    FormacionAcademica,
    Habilidad,
    HabilidadAspirante,
    HabilidadAnalisisCV,
    Idioma,
    IdiomaAspirante,
    IdiomaAnalisisCV,
    Institucion,
    ModalidadTrabajo,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    OfertaLaboral,
    PeriodoSalarial,
    PerfilAspirante,
    Plaza,
    Postulacion,
    Profesion,
    RequisitoCertificacion,
    RequisitoDisponibilidad,
    RequisitoEducacion,
    RequisitoExperiencia,
    RequisitoHabilidad,
    RequisitoIdioma,
    RequisitoPlaza,
    ResultadoRequisitoEvaluacion,
    TipoEmpleo,
)


class CatalogSerializer(serializers.Serializer):
    id = serializers.JSONField(read_only=True, source="pk")
    codigo = serializers.SerializerMethodField()
    nombre = serializers.CharField(read_only=True)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_codigo(self, obj):
        return getattr(obj, "codigo", None)


class ProfessionCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profesion
        fields = ("id", "nombre")


class InstitutionCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institucion
        fields = ("id", "nombre", "ciudad")

    def validate(self, attrs):
        queryset = Institucion.objects.filter(
            nombre__iexact=attrs.get("nombre", getattr(self.instance, "nombre", "")),
            ciudad=attrs.get("ciudad", getattr(self.instance, "ciudad", None)),
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("La institución ya existe en esa ciudad.")
        return attrs


class SkillCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habilidad
        fields = ("id", "nombre", "categoria", "activo")


class CityCatalogWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ciudad
        fields = ("id", "nombre", "region")

    def validate(self, attrs):
        queryset = Ciudad.objects.filter(
            nombre__iexact=attrs.get("nombre", getattr(self.instance, "nombre", "")),
            region=attrs.get("region", getattr(self.instance, "region", None)),
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("La ciudad ya existe en esa región.")
        return attrs


class CertificationCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificacion
        fields = ("id", "nombre", "organizacion_emisora")

    def validate(self, attrs):
        queryset = Certificacion.objects.filter(
            nombre__iexact=attrs.get("nombre", getattr(self.instance, "nombre", "")),
            organizacion_emisora__iexact=attrs.get(
                "organizacion_emisora",
                getattr(self.instance, "organizacion_emisora", ""),
            ),
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("La certificación ya existe.")
        return attrs


class UserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, source="pk")
    email = serializers.EmailField(read_only=True)
    nombres = serializers.CharField(source="first_name", read_only=True)
    apellidos = serializers.CharField(source="last_name", read_only=True)
    nombre_completo = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_nombre_completo(self, obj):
        return obj.get_full_name()


class CitySerializer(serializers.ModelSerializer):
    region = CatalogSerializer(read_only=True)

    class Meta:
        model = Ciudad
        fields = ("id", "nombre", "region")


class CurriculumSerializer(serializers.ModelSerializer):
    proveedor = CatalogSerializer(source="proveedor_almacenamiento", read_only=True)

    class Meta:
        model = Curriculo
        fields = (
            "id",
            "nombre_archivo_original",
            "tipo_mime",
            "tamano_bytes",
            "suma_sha256",
            "proveedor",
            "cargado_en",
            "activo",
        )


class ApplicantSummarySerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="usuario_id")
    usuario = UserSummarySerializer(read_only=True)
    profesion = serializers.CharField(
        source="profesion_nombre", read_only=True, allow_null=True
    )
    ciudad = serializers.CharField(
        source="ciudad_nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = PerfilAspirante
        fields = ("id", "usuario", "profesion", "ciudad", "telefono")


class ExperienceSerializer(serializers.ModelSerializer):
    profesion = serializers.CharField(
        source="profesion_nombre", read_only=True, allow_null=True
    )
    ciudad = serializers.CharField(
        source="ciudad_nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = ExperienciaLaboral
        fields = (
            "id",
            "profesion",
            "empresa",
            "puesto",
            "ciudad",
            "fecha_inicio",
            "fecha_fin",
            "descripcion",
        )


class EducationSerializer(serializers.ModelSerializer):
    institucion = serializers.CharField(
        source="institucion_nombre", read_only=True, allow_null=True
    )
    nivel_educativo = serializers.CharField(
        source="nivel_educativo_nombre", read_only=True, allow_null=True
    )
    area_estudio = serializers.CharField(
        source="area_estudio_nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = FormacionAcademica
        fields = (
            "id",
            "institucion",
            "nivel_educativo",
            "area_estudio",
            "titulo_obtenido",
            "fecha_inicio",
            "fecha_fin",
        )

class ApplicantSkillSerializer(serializers.ModelSerializer):
    habilidad = serializers.CharField(
        source="habilidad_nombre", read_only=True, allow_null=True
    )
    nivel_habilidad = serializers.CharField(
        source="nivel_habilidad_nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = HabilidadAspirante
        fields = ("id", "habilidad", "nivel_habilidad", "anios_experiencia")


class ApplicantLanguageSerializer(serializers.ModelSerializer):
    idioma = serializers.CharField(
        source="idioma_nombre", read_only=True, allow_null=True
    )
    nivel_idioma = serializers.CharField(
        source="nivel_idioma_nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = IdiomaAspirante
        fields = ("id", "idioma", "nivel_idioma")


class ApplicantCertificationSerializer(serializers.ModelSerializer):
    certificacion = serializers.CharField(
        source="certificacion_nombre", read_only=True, allow_null=True
    )
    organizacion_emisora = serializers.CharField(
        source="organizacion_emisora_nombre", read_only=True, allow_null=True
    )

    class Meta:
        model = CertificacionAspirante
        fields = (
            "id",
            "certificacion",
            "organizacion_emisora",
            "codigo_credencial",
            "url_credencial",
            "emitida_en",
            "vence_en",
        )


class ApplicantSerializer(ApplicantSummarySerializer):
    completitud = serializers.SerializerMethodField()
    experiencias = serializers.SerializerMethodField()
    formacion = serializers.SerializerMethodField()
    habilidades = serializers.SerializerMethodField()
    idiomas = serializers.SerializerMethodField()
    certificaciones = serializers.SerializerMethodField()
    curriculos_activos = serializers.SerializerMethodField()

    class Meta(ApplicantSummarySerializer.Meta):
        fields = ApplicantSummarySerializer.Meta.fields + (
            "direccion",
            "resumen_profesional",
            "disponible_desde",
            "acepta_reubicacion",
            "acepta_viajar",
            "completitud",
            "experiencias",
            "formacion",
            "habilidades",
            "idiomas",
            "certificaciones",
            "curriculos_activos",
            "creado_en",
            "actualizado_en",
        )

    @extend_schema_field(serializers.DictField())
    def get_completitud(self, obj):
        percentage, sections = profile_completion(obj)
        return {"porcentaje": percentage, "secciones": sections}

    @extend_schema_field(ExperienceSerializer(many=True))
    def get_experiencias(self, obj):
        return ExperienceSerializer(
            obj.experiencialaboral_set.all(), many=True
        ).data

    @extend_schema_field(EducationSerializer(many=True))
    def get_formacion(self, obj):
        return EducationSerializer(obj.formacionacademica_set.all(), many=True).data

    @extend_schema_field(ApplicantSkillSerializer(many=True))
    def get_habilidades(self, obj):
        return ApplicantSkillSerializer(
            obj.habilidadaspirante_set.all(), many=True
        ).data

    @extend_schema_field(ApplicantLanguageSerializer(many=True))
    def get_idiomas(self, obj):
        return ApplicantLanguageSerializer(obj.idiomaaspirante_set.all(), many=True).data

    @extend_schema_field(ApplicantCertificationSerializer(many=True))
    def get_certificaciones(self, obj):
        return ApplicantCertificationSerializer(
            obj.certificacionaspirante_set.all(), many=True
        ).data

    @extend_schema_field(CurriculumSerializer(many=True))
    def get_curriculos_activos(self, obj):
        return CurriculumSerializer(
            obj.curriculo_set.filter(activo=True), many=True
        ).data

class SkillRequirementSerializer(serializers.ModelSerializer):
    habilidad = CatalogSerializer(read_only=True)
    nivel_habilidad_minimo = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = RequisitoHabilidad
        fields = ("habilidad", "nivel_habilidad_minimo", "anios_minimos")


class LanguageRequirementSerializer(serializers.ModelSerializer):
    idioma = CatalogSerializer(read_only=True)
    nivel_idioma_minimo = CatalogSerializer(read_only=True)

    class Meta:
        model = RequisitoIdioma
        fields = ("idioma", "nivel_idioma_minimo")


class CertificationRequirementSerializer(serializers.ModelSerializer):
    certificacion = CatalogSerializer(read_only=True)

    class Meta:
        model = RequisitoCertificacion
        fields = ("certificacion", "debe_estar_vigente")


class EducationRequirementSerializer(serializers.ModelSerializer):
    nivel_educativo_minimo = CatalogSerializer(read_only=True)
    area_estudio = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = RequisitoEducacion
        fields = ("nivel_educativo_minimo", "area_estudio")


class ExperienceRequirementSerializer(serializers.ModelSerializer):
    profesion = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = RequisitoExperiencia
        fields = ("profesion", "meses_minimos")


class AvailabilityRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequisitoDisponibilidad
        fields = (
            "requerido_desde",
            "requiere_reubicacion",
            "requiere_viajar",
            "descripcion_horario",
        )


class RequirementSerializer(serializers.ModelSerializer):
    tipo = CatalogSerializer(read_only=True)
    detalle = serializers.SerializerMethodField()

    class Meta:
        model = RequisitoPlaza
        fields = (
            "id",
            "tipo",
            "descripcion",
            "obligatorio",
            "peso",
            "orden_visualizacion",
            "detalle",
        )

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_detalle(self, obj):
        detail_serializers = {
            "HABILIDAD": ("requisitohabilidad", SkillRequirementSerializer),
            "IDIOMA": ("requisitoidioma", LanguageRequirementSerializer),
            "CERTIFICACION": (
                "requisitocertificacion",
                CertificationRequirementSerializer,
            ),
            "EDUCACION": ("requisitoeducacion", EducationRequirementSerializer),
            "EXPERIENCIA": (
                "requisitoexperiencia",
                ExperienceRequirementSerializer,
            ),
            "DISPONIBILIDAD": (
                "requisitodisponibilidad",
                AvailabilityRequirementSerializer,
            ),
        }
        relation, serializer_class = detail_serializers.get(obj.tipo_id, (None, None))
        detail = getattr(obj, relation, None) if relation else None
        return serializer_class(detail).data if detail else None


class VacancySummarySerializer(serializers.ModelSerializer):
    estado = CatalogSerializer(read_only=True)
    departamento = CatalogSerializer(read_only=True)
    ciudad = CitySerializer(read_only=True, allow_null=True)

    class Meta:
        model = Plaza
        fields = ("id", "titulo", "estado", "departamento", "ciudad")


class VacancySerializer(VacancySummarySerializer):
    profesion = CatalogSerializer(read_only=True, allow_null=True)
    creado_por = UserSummarySerializer(read_only=True)
    tipo_empleo = CatalogSerializer(read_only=True)
    modalidad_trabajo = CatalogSerializer(read_only=True)
    periodo_salarial = CatalogSerializer(read_only=True, allow_null=True)
    requisitos = serializers.SerializerMethodField()

    class Meta(VacancySummarySerializer.Meta):
        fields = VacancySummarySerializer.Meta.fields + (
            "profesion",
            "creado_por",
            "tipo_empleo",
            "modalidad_trabajo",
            "periodo_salarial",
            "descripcion",
            "detalle_ubicacion",
            "salario_minimo",
            "salario_maximo",
            "codigo_moneda",
            "cantidad_vacantes",
            "publicado_en",
            "cierra_en",
            "creado_en",
            "actualizado_en",
            "requisitos",
        )

    @extend_schema_field(RequirementSerializer(many=True))
    def get_requisitos(self, obj):
        return RequirementSerializer(obj.requisitoplaza_set.all(), many=True).data


class EvaluationSummarySerializer(serializers.ModelSerializer):
    estado = CatalogSerializer(read_only=True)

    class Meta:
        model = EvaluacionPostulacion
        fields = (
            "id",
            "estado",
            "analisis_cv_id",
            "porcentaje_compatibilidad",
            "fortalezas",
            "recomendaciones_mejora",
            "iniciado_en",
            "completado_en",
            "mensaje_error",
            "creado_en",
        )


class InterviewSerializer(serializers.ModelSerializer):
    estado = CatalogSerializer(read_only=True)
    creado_por = UserSummarySerializer(read_only=True)

    class Meta:
        model = Entrevista
        fields = (
            "id",
            "estado",
            "inicia_en",
            "termina_en",
            "zona_horaria",
            "detalle_ubicacion",
            "url_reunion",
            "notas",
            "creado_por",
            "creado_en",
        )


class OfferSerializer(serializers.ModelSerializer):
    estado = CatalogSerializer(read_only=True)
    creado_por = UserSummarySerializer(read_only=True)

    class Meta:
        model = OfertaLaboral
        fields = (
            "id",
            "estado",
            "condiciones",
            "respuesta",
            "vence_en",
            "enviada_en",
            "respondida_en",
            "creado_por",
        )


class OfferCreateSerializer(serializers.Serializer):
    condiciones = serializers.CharField(max_length=8000)
    vence_en = serializers.DateTimeField()


class OfferResponseSerializer(serializers.Serializer):
    oferta_id = serializers.PrimaryKeyRelatedField(
        source="oferta",
        queryset=OfertaLaboral.objects.all(),
    )
    respuesta = serializers.ChoiceField(choices=("ACEPTADA", "RECHAZADA"))


class ApplicationSerializer(serializers.ModelSerializer):
    plaza = VacancySummarySerializer(read_only=True)
    aspirante = ApplicantSummarySerializer(read_only=True)
    curriculo = CurriculumSerializer(read_only=True)
    estado = CatalogSerializer(read_only=True)
    evaluacion = serializers.SerializerMethodField()
    entrevistas = serializers.SerializerMethodField()
    ofertas = serializers.SerializerMethodField()

    class Meta:
        model = Postulacion
        fields = (
            "id",
            "plaza",
            "aspirante",
            "curriculo",
            "estado",
            "carta_presentacion",
            "postulado_en",
            "retirado_en",
            "actualizado_en",
            "evaluacion",
            "entrevistas",
            "ofertas",
        )

    @extend_schema_field(EvaluationSummarySerializer(allow_null=True))
    def get_evaluacion(self, obj):
        evaluation = get_current_evaluation(obj)
        return EvaluationSummarySerializer(evaluation).data if evaluation else None

    @extend_schema_field(InterviewSerializer(many=True))
    def get_entrevistas(self, obj):
        return InterviewSerializer(
            obj.entrevista_set.select_related("estado", "creado_por").all(),
            many=True,
        ).data

    @extend_schema_field(OfferSerializer(many=True))
    def get_ofertas(self, obj):
        return OfferSerializer(
            obj.ofertalaboral_set.select_related("estado", "creado_por").order_by(
                "-creado_en"
            ),
            many=True,
        ).data


class ApplicationCreateSerializer(serializers.Serializer):
    plaza_id = serializers.PrimaryKeyRelatedField(
        source="plaza",
        queryset=Plaza.objects.all(),
        write_only=True,
    )
    carta_presentacion = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def create(self, validated_data):
        request = self.context["request"]
        profile = get_applicant_profile(request.user)
        try:
            return create_application(
                validated_data["plaza"].pk,
                profile,
                validated_data.get("carta_presentacion"),
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error


class ApplicationStateSerializer(serializers.Serializer):
    estado = serializers.CharField(max_length=30)
    motivo = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_estado(self, value):
        return value.strip().upper()


class AnalysisActionSerializer(serializers.Serializer):
    force = serializers.BooleanField(required=False, default=False)


class AnalysisPersonalDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatosPersonalesAnalisisCV
        fields = (
            "nombre_completo",
            "correo",
            "telefono",
            "profesion_texto",
            "ciudad_texto",
        )


class AnalysisExperienceSerializer(serializers.ModelSerializer):
    profesion = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = ExperienciaAnalisisCV
        fields = (
            "id",
            "profesion",
            "empresa",
            "puesto",
            "fecha_inicio",
            "fecha_fin",
            "descripcion",
            "confianza",
        )


class AnalysisEducationSerializer(serializers.ModelSerializer):
    nivel_educativo = CatalogSerializer(read_only=True, allow_null=True)
    area_estudio = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = EducacionAnalisisCV
        fields = (
            "id",
            "institucion_texto",
            "nivel_educativo",
            "area_estudio",
            "titulo_obtenido",
            "fecha_inicio",
            "fecha_fin",
            "confianza",
        )


class AnalysisSkillSerializer(serializers.ModelSerializer):
    habilidad = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = HabilidadAnalisisCV
        fields = ("id", "habilidad", "nombre_detectado", "confianza", "evidencia")


class AnalysisLanguageSerializer(serializers.ModelSerializer):
    idioma = CatalogSerializer(read_only=True, allow_null=True)
    nivel_idioma = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = IdiomaAnalisisCV
        fields = (
            "id",
            "idioma",
            "nombre_detectado",
            "nivel_idioma",
            "confianza",
        )


class AnalysisCertificationSerializer(serializers.ModelSerializer):
    certificacion = CatalogSerializer(read_only=True, allow_null=True)

    class Meta:
        model = CertificacionAnalisisCV
        fields = (
            "id",
            "certificacion",
            "nombre_detectado",
            "emitida_en",
            "vence_en",
            "confianza",
        )


class AnalysisSerializer(serializers.ModelSerializer):
    estado = CatalogSerializer(read_only=True)
    datos_personales = serializers.SerializerMethodField()
    experiencias = serializers.SerializerMethodField()
    formacion = serializers.SerializerMethodField()
    habilidades = serializers.SerializerMethodField()
    idiomas = serializers.SerializerMethodField()
    certificaciones = serializers.SerializerMethodField()

    class Meta:
        model = AnalisisCV
        fields = (
            "id",
            "curriculo_id",
            "motor_analisis_id",
            "estado",
            "resumen_profesional",
            "meses_experiencia_calculados",
            "iniciado_en",
            "completado_en",
            "mensaje_error",
            "vigente",
            "creado_en",
            "datos_personales",
            "experiencias",
            "formacion",
            "habilidades",
            "idiomas",
            "certificaciones",
        )

    @extend_schema_field(AnalysisPersonalDataSerializer(allow_null=True))
    def get_datos_personales(self, obj):
        data = DatosPersonalesAnalisisCV.objects.filter(analisis=obj).first()
        return AnalysisPersonalDataSerializer(data).data if data else None

    @extend_schema_field(AnalysisExperienceSerializer(many=True))
    def get_experiencias(self, obj):
        return AnalysisExperienceSerializer(
            ExperienciaAnalisisCV.objects.filter(analisis=obj).select_related("profesion"),
            many=True,
        ).data

    @extend_schema_field(AnalysisEducationSerializer(many=True))
    def get_formacion(self, obj):
        return AnalysisEducationSerializer(
            EducacionAnalisisCV.objects.filter(analisis=obj).select_related(
                "nivel_educativo", "area_estudio"
            ),
            many=True,
        ).data

    @extend_schema_field(AnalysisSkillSerializer(many=True))
    def get_habilidades(self, obj):
        return AnalysisSkillSerializer(
            HabilidadAnalisisCV.objects.filter(analisis=obj).select_related("habilidad"),
            many=True,
        ).data

    @extend_schema_field(AnalysisLanguageSerializer(many=True))
    def get_idiomas(self, obj):
        return AnalysisLanguageSerializer(
            IdiomaAnalisisCV.objects.filter(analisis=obj).select_related(
                "idioma", "nivel_idioma"
            ),
            many=True,
        ).data

    @extend_schema_field(AnalysisCertificationSerializer(many=True))
    def get_certificaciones(self, obj):
        return AnalysisCertificationSerializer(
            CertificacionAnalisisCV.objects.filter(analisis=obj).select_related(
                "certificacion"
            ),
            many=True,
        ).data


class RequirementResultSerializer(serializers.ModelSerializer):
    requisito = serializers.SerializerMethodField()

    class Meta:
        model = ResultadoRequisitoEvaluacion
        fields = (
            "requisito",
            "cumplido",
            "porcentaje_puntuacion",
            "evidencia",
            "explicacion",
        )

    @extend_schema_field(serializers.DictField())
    def get_requisito(self, obj):
        return {
            "id": obj.requisito_id,
            "tipo": CatalogSerializer(obj.requisito.tipo).data,
            "descripcion": obj.requisito.descripcion,
            "obligatorio": obj.requisito.obligatorio,
        }


class EvaluationDetailSerializer(EvaluationSummarySerializer):
    estado = CatalogSerializer(read_only=True)
    analisis = AnalysisSerializer(source="analisis_cv", read_only=True)
    resultados = serializers.SerializerMethodField()

    class Meta(EvaluationSummarySerializer.Meta):
        fields = EvaluationSummarySerializer.Meta.fields + ("analisis", "resultados")

    @extend_schema_field(RequirementResultSerializer(many=True))
    def get_resultados(self, obj):
        return RequirementResultSerializer(
            ResultadoRequisitoEvaluacion.objects.filter(evaluacion=obj).select_related(
                "requisito__tipo"
            ),
            many=True,
        ).data


class AnalysisJobSerializer(serializers.Serializer):
    application_id = serializers.IntegerField()
    analysis_id = serializers.IntegerField()
    evaluation_id = serializers.IntegerField()
    state = serializers.CharField()
    queued = serializers.BooleanField()
    already_queued = serializers.BooleanField()
    synchronous = serializers.BooleanField()
    task_id = serializers.CharField(allow_null=True)


class ApplicationAnalysisSerializer(serializers.Serializer):
    status = serializers.CharField()
    analysis = AnalysisSerializer(allow_null=True)
    evaluation = EvaluationDetailSerializer(allow_null=True)
