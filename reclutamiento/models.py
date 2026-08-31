from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ModeloExistente(models.Model):
    class Meta:
        abstract = True
        managed = False


class RolUsuario(ModeloExistente):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "roles_usuario"
        verbose_name = "rol de usuario"
        verbose_name_plural = "roles de usuario"

    def __str__(self):
        return self.nombre


class Pais(ModeloExistente):
    codigo_iso = models.CharField(max_length=2, unique=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "paises"
        verbose_name = "país"
        verbose_name_plural = "países"

    def __str__(self):
        return self.nombre


class Region(ModeloExistente):
    pais = models.ForeignKey(Pais, models.PROTECT, db_column="pais_id")
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "regiones"
        verbose_name = "región"
        verbose_name_plural = "regiones"

    def __str__(self):
        return self.nombre


class Ciudad(ModeloExistente):
    region = models.ForeignKey(Region, models.PROTECT, db_column="region_id")
    nombre = models.CharField(max_length=120)

    class Meta(ModeloExistente.Meta):
        db_table = "ciudades"
        verbose_name = "ciudad"
        verbose_name_plural = "ciudades"

    def __str__(self):
        return self.nombre


class Departamento(ModeloExistente):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta(ModeloExistente.Meta):
        db_table = "departamentos"

    def __str__(self):
        return self.nombre


class Profesion(ModeloExistente):
    nombre = models.CharField(max_length=150, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "profesiones"
        verbose_name = "profesión"
        verbose_name_plural = "profesiones"

    def __str__(self):
        return self.nombre


class NivelEducativo(ModeloExistente):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    orden_nivel = models.SmallIntegerField(unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "niveles_educativos"

    def __str__(self):
        return self.nombre


class AreaEstudio(ModeloExistente):
    nombre = models.CharField(max_length=150, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "areas_estudio"

    def __str__(self):
        return self.nombre


class Institucion(ModeloExistente):
    nombre = models.CharField(max_length=180)
    ciudad = models.ForeignKey(
        Ciudad,
        models.SET_NULL,
        db_column="ciudad_id",
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "instituciones"
        verbose_name = "institución"
        verbose_name_plural = "instituciones"

    def __str__(self):
        return self.nombre


class CategoriaHabilidad(ModeloExistente):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "categorias_habilidades"

    def __str__(self):
        return self.nombre


class Habilidad(ModeloExistente):
    categoria = models.ForeignKey(
        CategoriaHabilidad,
        models.SET_NULL,
        db_column="categoria_id",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=150, unique=True)
    activo = models.BooleanField(default=True)

    class Meta(ModeloExistente.Meta):
        db_table = "habilidades"

    def __str__(self):
        return self.nombre


class NivelHabilidad(ModeloExistente):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80, unique=True)
    orden_nivel = models.SmallIntegerField(unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "niveles_habilidad"

    def __str__(self):
        return self.nombre


class Idioma(ModeloExistente):
    codigo_iso = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "idiomas"

    def __str__(self):
        return self.nombre


class NivelIdioma(ModeloExistente):
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=80, unique=True)
    orden_nivel = models.SmallIntegerField(unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "niveles_idioma"

    def __str__(self):
        return self.nombre


class Certificacion(ModeloExistente):
    nombre = models.CharField(max_length=180)
    organizacion_emisora = models.CharField(max_length=180)

    class Meta(ModeloExistente.Meta):
        db_table = "certificaciones"
        verbose_name = "certificación"
        verbose_name_plural = "certificaciones"

    def __str__(self):
        return self.nombre


class TipoEmpleo(ModeloExistente):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "tipos_empleo"

    def __str__(self):
        return self.nombre


class ModalidadTrabajo(ModeloExistente):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "modalidades_trabajo"

    def __str__(self):
        return self.nombre


class PeriodoSalarial(ModeloExistente):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "periodos_salariales"

    def __str__(self):
        return self.nombre


class ProveedorAlmacenamiento(ModeloExistente):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "proveedores_almacenamiento"

    def __str__(self):
        return self.nombre


class AdministradorUsuario(BaseUserManager):
    use_in_migrations = False

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser):
    email = models.EmailField(db_column="correo", max_length=254, unique=True)
    password = models.CharField(db_column="hash_contrasena", max_length=255)
    first_name = models.CharField(db_column="nombres", max_length=100)
    last_name = models.CharField(db_column="apellidos", max_length=100)
    is_active = models.BooleanField(db_column="activo", default=True)
    is_verified = models.BooleanField(db_column="verificado", default=False)
    last_login = models.DateTimeField(
        db_column="ultimo_acceso_en",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(db_column="creado_en", default=timezone.now)
    updated_at = models.DateTimeField(db_column="actualizado_en", default=timezone.now)

    objects = AdministradorUsuario()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "usuarios"
        managed = False
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.get_full_name() or self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    def role_codes(self):
        return set(
            UsuarioRol.objects.filter(usuario=self).values_list(
                "rol__codigo",
                flat=True,
            )
        )

    def has_role(self, *codes):
        return bool(self.role_codes().intersection(codes))

    @property
    def is_staff(self):
        return self.has_role("RRHH", "ADMINISTRADOR")

    @property
    def is_superuser(self):
        return self.has_role("ADMINISTRADOR")

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    # Aliases for the existing Spanish domain vocabulary.
    correo = property(lambda self: self.email)
    nombres = property(lambda self: self.first_name)
    apellidos = property(lambda self: self.last_name)
    activo = property(lambda self: self.is_active)
    verificado = property(lambda self: self.is_verified)
    ultimo_acceso_en = property(lambda self: self.last_login)


class UsuarioRol(ModeloExistente):
    pk = models.CompositePrimaryKey("usuario", "rol")
    usuario = models.ForeignKey(
        Usuario,
        models.CASCADE,
        db_column="usuario_id",
    )
    rol = models.ForeignKey(RolUsuario, models.PROTECT, db_column="rol_id")
    asignado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "usuarios_roles"


class PerfilAspirante(ModeloExistente):
    usuario = models.OneToOneField(
        Usuario,
        models.CASCADE,
        db_column="usuario_id",
        primary_key=True,
    )
    profesion = models.ForeignKey(
        Profesion,
        models.SET_NULL,
        db_column="profesion_id",
        blank=True,
        null=True,
    )
    profesion_texto = models.CharField(
        max_length=150,
        db_column="profesion_texto",
        blank=True,
        null=True,
    )
    ciudad = models.ForeignKey(
        Ciudad,
        models.SET_NULL,
        db_column="ciudad_id",
        blank=True,
        null=True,
    )
    ciudad_texto = models.CharField(
        max_length=120,
        db_column="ciudad_texto",
        blank=True,
        null=True,
    )
    telefono = models.CharField(max_length=30, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    resumen_profesional = models.TextField(blank=True, null=True)
    disponible_desde = models.DateField(blank=True, null=True)
    acepta_reubicacion = models.BooleanField(default=False)
    acepta_viajar = models.BooleanField(default=False)
    creado_en = models.DateTimeField()
    actualizado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "perfiles_aspirantes"

    @property
    def profesion_nombre(self):
        return self.profesion_texto or (
            self.profesion.nombre if self.profesion_id else None
        )

    @property
    def ciudad_nombre(self):
        return self.ciudad_texto or (self.ciudad.nombre if self.ciudad_id else None)


class PerfilPersonal(ModeloExistente):
    usuario = models.OneToOneField(
        Usuario,
        models.CASCADE,
        db_column="usuario_id",
        primary_key=True,
    )
    departamento = models.ForeignKey(
        Departamento,
        models.SET_NULL,
        db_column="departamento_id",
        blank=True,
        null=True,
    )
    cargo = models.CharField(max_length=120, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "perfiles_personal"


class ExperienciaLaboral(ModeloExistente):
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.CASCADE,
        db_column="aspirante_id",
    )
    profesion = models.ForeignKey(
        Profesion,
        models.SET_NULL,
        db_column="profesion_id",
        blank=True,
        null=True,
    )
    profesion_texto = models.CharField(
        max_length=150,
        db_column="profesion_texto",
        blank=True,
        null=True,
    )
    empresa = models.CharField(max_length=180)
    puesto = models.CharField(max_length=180)
    ciudad = models.ForeignKey(
        Ciudad,
        models.SET_NULL,
        db_column="ciudad_id",
        blank=True,
        null=True,
    )
    ciudad_texto = models.CharField(
        max_length=120,
        db_column="ciudad_texto",
        blank=True,
        null=True,
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "experiencias_laborales"

    @property
    def profesion_nombre(self):
        return self.profesion_texto or (
            self.profesion.nombre if self.profesion_id else None
        )

    @property
    def ciudad_nombre(self):
        return self.ciudad_texto or (self.ciudad.nombre if self.ciudad_id else None)


class FormacionAcademica(ModeloExistente):
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.CASCADE,
        db_column="aspirante_id",
    )
    institucion = models.ForeignKey(
        Institucion,
        models.PROTECT,
        db_column="institucion_id",
        blank=True,
        null=True,
    )
    institucion_texto = models.CharField(
        max_length=180,
        db_column="institucion_texto",
        blank=True,
        null=True,
    )
    nivel_educativo = models.ForeignKey(
        NivelEducativo,
        models.PROTECT,
        db_column="nivel_educativo_id",
        blank=True,
        null=True,
    )
    nivel_educativo_texto = models.CharField(
        max_length=100,
        db_column="nivel_educativo_texto",
        blank=True,
        null=True,
    )
    area_estudio = models.ForeignKey(
        AreaEstudio,
        models.SET_NULL,
        db_column="area_estudio_id",
        blank=True,
        null=True,
    )
    area_estudio_texto = models.CharField(
        max_length=150,
        db_column="area_estudio_texto",
        blank=True,
        null=True,
    )
    titulo_obtenido = models.CharField(max_length=180)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "formaciones_academicas"

    @property
    def institucion_nombre(self):
        return self.institucion_texto or (
            self.institucion.nombre if self.institucion_id else None
        )

    @property
    def nivel_educativo_nombre(self):
        return self.nivel_educativo_texto or (
            self.nivel_educativo.nombre if self.nivel_educativo_id else None
        )

    @property
    def area_estudio_nombre(self):
        return self.area_estudio_texto or (
            self.area_estudio.nombre if self.area_estudio_id else None
        )


class HabilidadAspirante(ModeloExistente):
    id = models.BigAutoField(primary_key=True)
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.CASCADE,
        db_column="aspirante_id",
    )
    habilidad = models.ForeignKey(
        Habilidad,
        models.PROTECT,
        db_column="habilidad_id",
        blank=True,
        null=True,
    )
    habilidad_texto = models.CharField(
        max_length=150,
        db_column="habilidad_texto",
        blank=True,
        null=True,
    )
    nivel_habilidad = models.ForeignKey(
        NivelHabilidad,
        models.SET_NULL,
        db_column="nivel_habilidad_id",
        blank=True,
        null=True,
    )
    nivel_habilidad_texto = models.CharField(
        max_length=80,
        db_column="nivel_habilidad_texto",
        blank=True,
        null=True,
    )
    anios_experiencia = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "habilidades_aspirantes"

    @property
    def habilidad_nombre(self):
        return self.habilidad_texto or (
            self.habilidad.nombre if self.habilidad_id else None
        )

    @property
    def nivel_habilidad_nombre(self):
        return self.nivel_habilidad_texto or (
            self.nivel_habilidad.nombre if self.nivel_habilidad_id else None
        )


class IdiomaAspirante(ModeloExistente):
    id = models.BigAutoField(primary_key=True)
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.CASCADE,
        db_column="aspirante_id",
    )
    idioma = models.ForeignKey(
        Idioma,
        models.PROTECT,
        db_column="idioma_id",
        blank=True,
        null=True,
    )
    idioma_texto = models.CharField(
        max_length=80,
        db_column="idioma_texto",
        blank=True,
        null=True,
    )
    nivel_idioma = models.ForeignKey(
        NivelIdioma,
        models.PROTECT,
        db_column="nivel_idioma_id",
        blank=True,
        null=True,
    )
    nivel_idioma_texto = models.CharField(
        max_length=80,
        db_column="nivel_idioma_texto",
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "idiomas_aspirantes"

    @property
    def idioma_nombre(self):
        return self.idioma_texto or (self.idioma.nombre if self.idioma_id else None)

    @property
    def nivel_idioma_nombre(self):
        return self.nivel_idioma_texto or (
            self.nivel_idioma.nombre if self.nivel_idioma_id else None
        )


class CertificacionAspirante(ModeloExistente):
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.CASCADE,
        db_column="aspirante_id",
    )
    certificacion = models.ForeignKey(
        Certificacion,
        models.PROTECT,
        db_column="certificacion_id",
        blank=True,
        null=True,
    )
    certificacion_texto = models.CharField(
        max_length=180,
        db_column="certificacion_texto",
        blank=True,
        null=True,
    )
    organizacion_emisora_texto = models.CharField(
        max_length=180,
        db_column="organizacion_emisora_texto",
        blank=True,
        null=True,
    )
    codigo_credencial = models.CharField(max_length=120, blank=True, null=True)
    url_credencial = models.TextField(blank=True, null=True)
    emitida_en = models.DateField(blank=True, null=True)
    vence_en = models.DateField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "certificaciones_aspirantes"

    @property
    def certificacion_nombre(self):
        return self.certificacion_texto or (
            self.certificacion.nombre if self.certificacion_id else None
        )

    @property
    def organizacion_emisora_nombre(self):
        return self.organizacion_emisora_texto or (
            self.certificacion.organizacion_emisora if self.certificacion_id else None
        )


class EstadoPlaza(ModeloExistente):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    es_final = models.BooleanField(default=False)

    class Meta(ModeloExistente.Meta):
        db_table = "estados_plaza"

    def __str__(self):
        return self.nombre


class Plaza(ModeloExistente):
    departamento = models.ForeignKey(
        Departamento,
        models.PROTECT,
        db_column="departamento_id",
        blank=True,
        null=True,
    )
    departamento_texto = models.CharField(
        max_length=120,
        db_column="departamento_texto",
        blank=True,
        null=True,
    )
    profesion = models.ForeignKey(
        Profesion,
        models.SET_NULL,
        db_column="profesion_id",
        blank=True,
        null=True,
    )
    profesion_texto = models.CharField(
        max_length=150,
        db_column="profesion_texto",
        blank=True,
        null=True,
    )
    creado_por = models.ForeignKey(
        Usuario,
        models.PROTECT,
        db_column="creado_por_id",
    )
    ciudad = models.ForeignKey(
        Ciudad,
        models.SET_NULL,
        db_column="ciudad_id",
        blank=True,
        null=True,
    )
    ciudad_texto = models.CharField(
        max_length=120,
        db_column="ciudad_texto",
        blank=True,
        null=True,
    )
    tipo_empleo = models.ForeignKey(
        TipoEmpleo,
        models.PROTECT,
        db_column="tipo_empleo_id",
        blank=True,
        null=True,
    )
    tipo_empleo_texto = models.CharField(
        max_length=80,
        db_column="tipo_empleo_texto",
        blank=True,
        null=True,
    )
    modalidad_trabajo = models.ForeignKey(
        ModalidadTrabajo,
        models.PROTECT,
        db_column="modalidad_trabajo_id",
        blank=True,
        null=True,
    )
    modalidad_trabajo_texto = models.CharField(
        max_length=80,
        db_column="modalidad_trabajo_texto",
        blank=True,
        null=True,
    )
    periodo_salarial = models.ForeignKey(
        PeriodoSalarial,
        models.PROTECT,
        db_column="periodo_salarial_id",
        blank=True,
        null=True,
    )
    periodo_salarial_texto = models.CharField(
        max_length=80,
        db_column="periodo_salarial_texto",
        blank=True,
        null=True,
    )
    estado = models.ForeignKey(
        EstadoPlaza,
        models.PROTECT,
        db_column="codigo_estado",
        default="BORRADOR",
    )
    titulo = models.CharField(max_length=180)
    descripcion = models.TextField()
    detalle_ubicacion = models.CharField(max_length=200, blank=True, null=True)
    salario_minimo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
    )
    salario_maximo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
    )
    codigo_moneda = models.CharField(max_length=3, blank=True, null=True)
    cantidad_vacantes = models.IntegerField(default=1)
    publicado_en = models.DateTimeField(blank=True, null=True)
    cierra_en = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField()
    actualizado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "plazas"

    def __str__(self):
        return self.titulo

    @property
    def departamento_nombre(self):
        return self.departamento_texto or (
            self.departamento.nombre if self.departamento_id else None
        )

    @property
    def profesion_nombre(self):
        return self.profesion_texto or (
            self.profesion.nombre if self.profesion_id else None
        )

    @property
    def ciudad_nombre(self):
        return self.ciudad_texto or (self.ciudad.nombre if self.ciudad_id else None)

    @property
    def tipo_empleo_nombre(self):
        return self.tipo_empleo_texto or (
            self.tipo_empleo.nombre if self.tipo_empleo_id else None
        )

    @property
    def modalidad_trabajo_nombre(self):
        return self.modalidad_trabajo_texto or (
            self.modalidad_trabajo.nombre if self.modalidad_trabajo_id else None
        )

    @property
    def periodo_salarial_nombre(self):
        return self.periodo_salarial_texto or (
            self.periodo_salarial.nombre if self.periodo_salarial_id else None
        )

    @property
    def esta_vencida(self):
        return (
            self.estado_id == "PUBLICADA"
            and self.cierra_en is not None
            and self.cierra_en <= timezone.now()
        )


class HistorialEstadoPlaza(ModeloExistente):
    plaza = models.ForeignKey(Plaza, models.CASCADE, db_column="plaza_id")
    codigo_estado_anterior = models.CharField(max_length=20, blank=True, null=True)
    codigo_estado_nuevo = models.CharField(max_length=20)
    cambiado_por = models.ForeignKey(
        Usuario,
        models.PROTECT,
        db_column="cambiado_por_id",
    )
    motivo = models.TextField(blank=True, null=True)
    cambiado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "historial_estados_plaza"


class TipoRequisito(ModeloExistente):
    codigo = models.CharField(max_length=30, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "tipos_requisito"

    def __str__(self):
        return self.nombre


class RequisitoPlaza(ModeloExistente):
    plaza = models.ForeignKey(Plaza, models.CASCADE, db_column="plaza_id")
    tipo = models.ForeignKey(
        TipoRequisito,
        models.PROTECT,
        db_column="codigo_tipo",
    )
    descripcion = models.TextField(blank=True, null=True)
    obligatorio = models.BooleanField(default=True)
    peso = models.DecimalField(max_digits=5, decimal_places=2)
    orden_visualizacion = models.SmallIntegerField(default=1)

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_plaza"


class RequisitoHabilidad(ModeloExistente):
    requisito = models.OneToOneField(
        RequisitoPlaza,
        models.CASCADE,
        db_column="requisito_id",
        primary_key=True,
    )
    habilidad = models.ForeignKey(
        Habilidad,
        models.PROTECT,
        db_column="habilidad_id",
        blank=True,
        null=True,
    )
    habilidad_texto = models.CharField(
        max_length=150,
        db_column="habilidad_texto",
        blank=True,
        null=True,
    )
    nivel_habilidad_minimo = models.ForeignKey(
        NivelHabilidad,
        models.PROTECT,
        db_column="nivel_habilidad_minimo_id",
        blank=True,
        null=True,
    )
    nivel_habilidad_minimo_texto = models.CharField(
        max_length=80,
        db_column="nivel_habilidad_minimo_texto",
        blank=True,
        null=True,
    )
    anios_minimos = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_habilidad"

    @property
    def habilidad_nombre(self):
        return self.habilidad_texto or (
            self.habilidad.nombre if self.habilidad_id else None
        )

    @property
    def nivel_habilidad_minimo_nombre(self):
        return self.nivel_habilidad_minimo_texto or (
            self.nivel_habilidad_minimo.nombre
            if self.nivel_habilidad_minimo_id
            else None
        )


class RequisitoIdioma(ModeloExistente):
    requisito = models.OneToOneField(
        RequisitoPlaza,
        models.CASCADE,
        db_column="requisito_id",
        primary_key=True,
    )
    idioma = models.ForeignKey(
        Idioma,
        models.PROTECT,
        db_column="idioma_id",
        blank=True,
        null=True,
    )
    idioma_texto = models.CharField(
        max_length=80,
        db_column="idioma_texto",
        blank=True,
        null=True,
    )
    nivel_idioma_minimo = models.ForeignKey(
        NivelIdioma,
        models.PROTECT,
        db_column="nivel_idioma_minimo_id",
        blank=True,
        null=True,
    )
    nivel_idioma_minimo_texto = models.CharField(
        max_length=80,
        db_column="nivel_idioma_minimo_texto",
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_idioma"

    @property
    def idioma_nombre(self):
        return self.idioma_texto or (self.idioma.nombre if self.idioma_id else None)

    @property
    def nivel_idioma_minimo_nombre(self):
        return self.nivel_idioma_minimo_texto or (
            self.nivel_idioma_minimo.nombre
            if self.nivel_idioma_minimo_id
            else None
        )


class RequisitoCertificacion(ModeloExistente):
    requisito = models.OneToOneField(
        RequisitoPlaza,
        models.CASCADE,
        db_column="requisito_id",
        primary_key=True,
    )
    certificacion = models.ForeignKey(
        Certificacion,
        models.PROTECT,
        db_column="certificacion_id",
        blank=True,
        null=True,
    )
    certificacion_texto = models.CharField(
        max_length=180,
        db_column="certificacion_texto",
        blank=True,
        null=True,
    )
    debe_estar_vigente = models.BooleanField(default=True)

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_certificacion"

    @property
    def certificacion_nombre(self):
        return self.certificacion_texto or (
            self.certificacion.nombre if self.certificacion_id else None
        )


class RequisitoEducacion(ModeloExistente):
    requisito = models.OneToOneField(
        RequisitoPlaza,
        models.CASCADE,
        db_column="requisito_id",
        primary_key=True,
    )
    nivel_educativo_minimo = models.ForeignKey(
        NivelEducativo,
        models.PROTECT,
        db_column="nivel_educativo_minimo_id",
        blank=True,
        null=True,
    )
    nivel_educativo_texto = models.CharField(
        max_length=100,
        db_column="nivel_educativo_texto",
        blank=True,
        null=True,
    )
    area_estudio = models.ForeignKey(
        AreaEstudio,
        models.PROTECT,
        db_column="area_estudio_id",
        blank=True,
        null=True,
    )
    area_estudio_texto = models.CharField(
        max_length=150,
        db_column="area_estudio_texto",
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_educacion"

    @property
    def nivel_educativo_minimo_nombre(self):
        return self.nivel_educativo_texto or (
            self.nivel_educativo_minimo.nombre
            if self.nivel_educativo_minimo_id
            else None
        )

    @property
    def area_estudio_nombre(self):
        return self.area_estudio_texto or (
            self.area_estudio.nombre if self.area_estudio_id else None
        )


class RequisitoExperiencia(ModeloExistente):
    requisito = models.OneToOneField(
        RequisitoPlaza,
        models.CASCADE,
        db_column="requisito_id",
        primary_key=True,
    )
    profesion = models.ForeignKey(
        Profesion,
        models.PROTECT,
        db_column="profesion_id",
        blank=True,
        null=True,
    )
    profesion_texto = models.CharField(
        max_length=150,
        db_column="profesion_texto",
        blank=True,
        null=True,
    )
    meses_minimos = models.IntegerField()

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_experiencia"

    @property
    def profesion_nombre(self):
        return self.profesion_texto or (
            self.profesion.nombre if self.profesion_id else None
        )


class RequisitoDisponibilidad(ModeloExistente):
    requisito = models.OneToOneField(
        RequisitoPlaza,
        models.CASCADE,
        db_column="requisito_id",
        primary_key=True,
    )
    requerido_desde = models.DateField(blank=True, null=True)
    requiere_reubicacion = models.BooleanField(default=False)
    requiere_viajar = models.BooleanField(default=False)
    descripcion_horario = models.CharField(max_length=200, blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "requisitos_disponibilidad"


class Curriculo(ModeloExistente):
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.CASCADE,
        db_column="aspirante_id",
    )
    proveedor_almacenamiento = models.ForeignKey(
        ProveedorAlmacenamiento,
        models.PROTECT,
        db_column="proveedor_almacenamiento_id",
    )
    clave_objeto = models.CharField(max_length=1024)
    nombre_archivo_original = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=100, default="application/pdf")
    tamano_bytes = models.BigIntegerField()
    suma_sha256 = models.CharField(max_length=64)
    duplicado_de = models.ForeignKey(
        "self",
        models.SET_NULL,
        db_column="duplicado_de_id",
        blank=True,
        null=True,
    )
    cargado_en = models.DateTimeField()
    activo = models.BooleanField(default=True)

    class Meta(ModeloExistente.Meta):
        db_table = "curriculos"


class ModeloIA(ModeloExistente):
    proveedor = models.CharField(max_length=100)
    nombre = models.CharField(max_length=150)
    version = models.CharField(max_length=80)

    class Meta(ModeloExistente.Meta):
        db_table = "modelos_ia"

    def __str__(self):
        return f"{self.proveedor}: {self.nombre} {self.version}"


class MotorAnalisis(ModeloExistente):
    modelo_ia = models.ForeignKey(
        ModeloIA,
        models.PROTECT,
        db_column="modelo_ia_id",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=120)
    version = models.CharField(max_length=80)
    version_instruccion = models.CharField(max_length=80, blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "motores_analisis"


class EstadoProcesamiento(ModeloExistente):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    es_final = models.BooleanField(default=False)

    class Meta(ModeloExistente.Meta):
        db_table = "estados_procesamiento"

    def __str__(self):
        return self.nombre


class AnalisisCV(ModeloExistente):
    curriculo = models.ForeignKey(Curriculo, models.CASCADE, db_column="curriculo_id")
    motor_analisis = models.ForeignKey(
        MotorAnalisis,
        models.PROTECT,
        db_column="motor_analisis_id",
    )
    estado = models.ForeignKey(
        EstadoProcesamiento,
        models.PROTECT,
        db_column="codigo_estado",
        default="PENDIENTE",
    )
    texto_extraido = models.TextField(blank=True, null=True)
    resumen_profesional = models.TextField(blank=True, null=True)
    meses_experiencia_calculados = models.IntegerField(blank=True, null=True)
    iniciado_en = models.DateTimeField(blank=True, null=True)
    completado_en = models.DateTimeField(blank=True, null=True)
    mensaje_error = models.TextField(blank=True, null=True)
    vigente = models.BooleanField(default=False)
    creado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "analisis_cv"


class DatosPersonalesAnalisisCV(ModeloExistente):
    analisis = models.OneToOneField(
        AnalisisCV,
        models.CASCADE,
        db_column="analisis_id",
        primary_key=True,
    )
    nombre_completo = models.CharField(max_length=200, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    profesion_texto = models.CharField(max_length=180, blank=True, null=True)
    ciudad_texto = models.CharField(max_length=180, blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "datos_personales_analisis_cv"


class ExperienciaAnalisisCV(ModeloExistente):
    analisis = models.ForeignKey(AnalisisCV, models.CASCADE, db_column="analisis_id")
    profesion = models.ForeignKey(
        Profesion,
        models.SET_NULL,
        db_column="profesion_id",
        blank=True,
        null=True,
    )
    empresa = models.CharField(max_length=180, blank=True, null=True)
    puesto = models.CharField(max_length=180)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    confianza = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "experiencias_analisis_cv"


class EducacionAnalisisCV(ModeloExistente):
    analisis = models.ForeignKey(AnalisisCV, models.CASCADE, db_column="analisis_id")
    institucion_texto = models.CharField(max_length=180)
    nivel_educativo = models.ForeignKey(
        NivelEducativo,
        models.SET_NULL,
        db_column="nivel_educativo_id",
        blank=True,
        null=True,
    )
    area_estudio = models.ForeignKey(
        AreaEstudio,
        models.SET_NULL,
        db_column="area_estudio_id",
        blank=True,
        null=True,
    )
    titulo_obtenido = models.CharField(max_length=180, blank=True, null=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    confianza = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "educaciones_analisis_cv"


class HabilidadAnalisisCV(ModeloExistente):
    analisis = models.ForeignKey(AnalisisCV, models.CASCADE, db_column="analisis_id")
    habilidad = models.ForeignKey(
        Habilidad,
        models.SET_NULL,
        db_column="habilidad_id",
        blank=True,
        null=True,
    )
    nombre_detectado = models.CharField(max_length=150)
    confianza = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )
    evidencia = models.TextField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "habilidades_analisis_cv"


class IdiomaAnalisisCV(ModeloExistente):
    analisis = models.ForeignKey(AnalisisCV, models.CASCADE, db_column="analisis_id")
    idioma = models.ForeignKey(
        Idioma,
        models.SET_NULL,
        db_column="idioma_id",
        blank=True,
        null=True,
    )
    nombre_detectado = models.CharField(max_length=80)
    nivel_idioma = models.ForeignKey(
        NivelIdioma,
        models.SET_NULL,
        db_column="nivel_idioma_id",
        blank=True,
        null=True,
    )
    confianza = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "idiomas_analisis_cv"


class CertificacionAnalisisCV(ModeloExistente):
    analisis = models.ForeignKey(AnalisisCV, models.CASCADE, db_column="analisis_id")
    certificacion = models.ForeignKey(
        Certificacion,
        models.SET_NULL,
        db_column="certificacion_id",
        blank=True,
        null=True,
    )
    nombre_detectado = models.CharField(max_length=180)
    emitida_en = models.DateField(blank=True, null=True)
    vence_en = models.DateField(blank=True, null=True)
    confianza = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )

    class Meta(ModeloExistente.Meta):
        db_table = "certificaciones_analisis_cv"


class EstadoPostulacion(ModeloExistente):
    codigo = models.CharField(max_length=30, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    es_final = models.BooleanField(default=False)

    class Meta(ModeloExistente.Meta):
        db_table = "estados_postulacion"

    def __str__(self):
        return self.nombre


class Postulacion(ModeloExistente):
    plaza = models.ForeignKey(Plaza, models.PROTECT, db_column="plaza_id")
    aspirante = models.ForeignKey(
        PerfilAspirante,
        models.PROTECT,
        db_column="aspirante_id",
    )
    curriculo = models.ForeignKey(Curriculo, models.PROTECT, db_column="curriculo_id")
    estado = models.ForeignKey(
        EstadoPostulacion,
        models.PROTECT,
        db_column="codigo_estado",
        default="ENVIADA",
    )
    carta_presentacion = models.TextField(blank=True, null=True)
    postulado_en = models.DateTimeField()
    retirado_en = models.DateTimeField(blank=True, null=True)
    actualizado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "postulaciones"


class EstadoOferta(ModeloExistente):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    es_final = models.BooleanField(default=False)

    class Meta(ModeloExistente.Meta):
        db_table = "estados_oferta"

    def __str__(self):
        return self.nombre


class OfertaLaboral(ModeloExistente):
    postulacion = models.ForeignKey(
        Postulacion,
        models.CASCADE,
        db_column="postulacion_id",
    )
    creado_por = models.ForeignKey(
        Usuario,
        models.PROTECT,
        db_column="creado_por_id",
    )
    estado = models.ForeignKey(
        EstadoOferta,
        models.PROTECT,
        db_column="codigo_estado",
        default="ENVIADA",
    )
    condiciones = models.TextField()
    respuesta = models.CharField(max_length=20, blank=True, null=True)
    vence_en = models.DateTimeField()
    enviada_en = models.DateTimeField()
    respondida_en = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField()
    actualizado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "ofertas_laborales"


class HistorialEstadoPostulacion(ModeloExistente):
    postulacion = models.ForeignKey(
        Postulacion,
        models.CASCADE,
        db_column="postulacion_id",
    )
    codigo_estado_anterior = models.CharField(max_length=30, blank=True, null=True)
    codigo_estado_nuevo = models.CharField(max_length=30)
    cambiado_por = models.ForeignKey(
        Usuario,
        models.SET_NULL,
        db_column="cambiado_por_id",
        blank=True,
        null=True,
    )
    motivo = models.TextField(blank=True, null=True)
    cambiado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "historial_estados_postulacion"


class EvaluacionPostulacion(ModeloExistente):
    postulacion = models.ForeignKey(
        Postulacion,
        models.CASCADE,
        db_column="postulacion_id",
    )
    analisis_cv = models.ForeignKey(
        AnalisisCV,
        models.PROTECT,
        db_column="analisis_cv_id",
    )
    motor_analisis = models.ForeignKey(
        MotorAnalisis,
        models.PROTECT,
        db_column="motor_analisis_id",
    )
    estado = models.ForeignKey(
        EstadoProcesamiento,
        models.PROTECT,
        db_column="codigo_estado",
        default="PENDIENTE",
    )
    porcentaje_compatibilidad = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
    fortalezas = models.TextField(blank=True, null=True)
    recomendaciones_mejora = models.TextField(blank=True, null=True)
    iniciado_en = models.DateTimeField(blank=True, null=True)
    completado_en = models.DateTimeField(blank=True, null=True)
    mensaje_error = models.TextField(blank=True, null=True)
    vigente = models.BooleanField(default=False)
    creado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "evaluaciones_postulacion"


class ResultadoRequisitoEvaluacion(ModeloExistente):
    pk = models.CompositePrimaryKey("evaluacion", "requisito")
    evaluacion = models.ForeignKey(
        EvaluacionPostulacion,
        models.CASCADE,
        db_column="evaluacion_id",
    )
    requisito = models.ForeignKey(
        RequisitoPlaza,
        models.PROTECT,
        db_column="requisito_id",
    )
    cumplido = models.BooleanField()
    porcentaje_puntuacion = models.DecimalField(max_digits=5, decimal_places=2)
    evidencia = models.TextField(blank=True, null=True)
    explicacion = models.TextField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "resultados_requisitos_evaluacion"


class EstadoEntrevista(ModeloExistente):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    es_final = models.BooleanField(default=False)

    class Meta(ModeloExistente.Meta):
        db_table = "estados_entrevista"

    def __str__(self):
        return self.nombre


class Entrevista(ModeloExistente):
    postulacion = models.ForeignKey(
        Postulacion,
        models.CASCADE,
        db_column="postulacion_id",
    )
    creado_por = models.ForeignKey(
        Usuario,
        models.PROTECT,
        db_column="creado_por_id",
    )
    estado = models.ForeignKey(
        EstadoEntrevista,
        models.PROTECT,
        db_column="codigo_estado",
        default="PROGRAMADA",
    )
    inicia_en = models.DateTimeField()
    termina_en = models.DateTimeField()
    zona_horaria = models.CharField(max_length=80)
    detalle_ubicacion = models.CharField(max_length=200, blank=True, null=True)
    url_reunion = models.TextField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField()

    class Meta(ModeloExistente.Meta):
        db_table = "entrevistas"

    def _in_scheduled_timezone(self, value):
        if timezone.is_naive(value):
            value = timezone.make_aware(value)
        try:
            zone = ZoneInfo(self.zona_horaria)
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.localtime(value)
        return timezone.localtime(value, zone)

    @property
    def inicia_en_local(self):
        return self._in_scheduled_timezone(self.inicia_en)

    @property
    def termina_en_local(self):
        return self._in_scheduled_timezone(self.termina_en)


class TipoNotificacion(ModeloExistente):
    codigo = models.CharField(max_length=40, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "tipos_notificacion"

    def __str__(self):
        return self.nombre


class CanalNotificacion(ModeloExistente):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)

    class Meta(ModeloExistente.Meta):
        db_table = "canales_notificacion"

    def __str__(self):
        return self.nombre


class EstadoEntrega(ModeloExistente):
    codigo = models.CharField(max_length=20, primary_key=True)
    nombre = models.CharField(max_length=80, unique=True)
    es_final = models.BooleanField(default=False)

    class Meta(ModeloExistente.Meta):
        db_table = "estados_entrega"

    def __str__(self):
        return self.nombre


class Notificacion(ModeloExistente):
    usuario_destinatario = models.ForeignKey(
        Usuario,
        models.CASCADE,
        db_column="usuario_destinatario_id",
    )
    tipo = models.ForeignKey(
        TipoNotificacion,
        models.PROTECT,
        db_column="codigo_tipo",
    )
    postulacion = models.ForeignKey(
        Postulacion,
        models.CASCADE,
        db_column="postulacion_id",
        blank=True,
        null=True,
    )
    entrevista = models.ForeignKey(
        Entrevista,
        models.CASCADE,
        db_column="entrevista_id",
        blank=True,
        null=True,
    )
    titulo = models.CharField(max_length=180)
    mensaje = models.TextField()
    creado_en = models.DateTimeField()
    leido_en = models.DateTimeField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "notificaciones"


class EntregaNotificacion(ModeloExistente):
    notificacion = models.ForeignKey(
        Notificacion,
        models.CASCADE,
        db_column="notificacion_id",
    )
    canal = models.ForeignKey(
        CanalNotificacion,
        models.PROTECT,
        db_column="codigo_canal",
    )
    estado = models.ForeignKey(
        EstadoEntrega,
        models.PROTECT,
        db_column="codigo_estado",
        default="PENDIENTE",
    )
    direccion_destino = models.CharField(max_length=320, blank=True, null=True)
    programado_en = models.DateTimeField()
    enviado_en = models.DateTimeField(blank=True, null=True)
    id_mensaje_proveedor = models.CharField(max_length=255, blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "entregas_notificacion"


class IntentoEntregaNotificacion(ModeloExistente):
    entrega = models.ForeignKey(
        EntregaNotificacion,
        models.CASCADE,
        db_column="entrega_id",
    )
    intentado_en = models.DateTimeField()
    exitoso = models.BooleanField()
    mensaje_error = models.TextField(blank=True, null=True)

    class Meta(ModeloExistente.Meta):
        db_table = "intentos_entrega_notificacion"
