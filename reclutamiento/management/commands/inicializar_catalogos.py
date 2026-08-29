from django.core.management.base import BaseCommand
from django.db import connection, transaction

from reclutamiento.models import (
    AreaEstudio,
    Certificacion,
    Ciudad,
    Departamento,
    EstadoEntrevista,
    EstadoPlaza,
    EstadoPostulacion,
    Habilidad,
    Idioma,
    Institucion,
    ModalidadTrabajo,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    PeriodoSalarial,
    Pais,
    Profesion,
    ProveedorAlmacenamiento,
    Region,
    TipoEmpleo,
    TipoRequisito,
)


class Command(BaseCommand):
    help = "Inicializa de forma idempotente los catálogos principales del sistema."

    @transaction.atomic
    def handle(self, *args, **options):
        self.available_tables = set(connection.introspection.table_names())
        self._code_catalog(EstadoPlaza, (("BORRADOR", "Pendiente", {"es_final": False}), ("PUBLICADA", "Activa", {"es_final": False}), ("PAUSADA", "Pausada", {"es_final": False}), ("CERRADA", "Cerrada", {"es_final": True})))
        if self._has_table(EstadoPostulacion):
            self._code_catalog(EstadoPostulacion, (("ENVIADA", "Enviada", {"es_final": False}), ("EN_REVISION", "En revisión", {"es_final": False}), ("PRESELECCIONADA", "Preseleccionada", {"es_final": False}), ("ENTREVISTA", "Entrevista", {"es_final": False}), ("OFERTA_ENVIADA", "Oferta enviada", {"es_final": False}), ("CONTRATADA", "Contratada", {"es_final": True}), ("RECHAZADA", "Rechazada", {"es_final": True}), ("RETIRADA", "Retirada", {"es_final": True})))
        if self._has_table(EstadoEntrevista):
            self._code_catalog(EstadoEntrevista, (("PROGRAMADA", "Programada", {"es_final": False}), ("CONFIRMADA", "Confirmada", {"es_final": False}), ("COMPLETADA", "Completada", {"es_final": True}), ("CANCELADA", "Cancelada", {"es_final": True}), ("NO_ASISTIO", "No asistió", {"es_final": True})))
        self._code_catalog(TipoRequisito, (("HABILIDAD", "Habilidad", {}), ("IDIOMA", "Idioma", {}), ("CERTIFICACION", "Certificación", {}), ("EDUCACION", "Educación", {}), ("EXPERIENCIA", "Experiencia", {}), ("DISPONIBILIDAD", "Disponibilidad", {})))
        self._code_catalog(TipoEmpleo, (("TIEMPO_COMPLETO", "Tiempo completo", {}), ("MEDIO_TIEMPO", "Medio tiempo", {}), ("CONTRATO", "Por contrato", {}), ("TEMPORAL", "Temporal", {})))
        self._code_catalog(ModalidadTrabajo, (("REMOTO", "Remoto", {}), ("HIBRIDO", "Híbrido", {}), ("PRESENCIAL", "Presencial", {})))
        self._code_catalog(PeriodoSalarial, (("HORA", "Por hora", {}), ("MES", "Mensual", {}), ("ANIO", "Anual", {})))
        self._named_catalog(Departamento, ("Tecnología", "Producto", "Datos", "Marketing", "Operaciones"), {"activo": True})
        self._named_catalog(Profesion, ("Ingeniería de software", "Diseño de producto", "Análisis de datos", "Marketing digital", "Administración"))
        self._ranked_catalog(NivelEducativo, (("SECUNDARIA", "Educación secundaria", 1), ("TECNICO", "Técnico universitario", 2), ("LICENCIATURA", "Licenciatura o ingeniería", 3), ("MAESTRIA", "Maestría", 4), ("DOCTORADO", "Doctorado", 5)))
        self._ranked_catalog(NivelHabilidad, (("BASICO", "Básico", 1), ("INTERMEDIO", "Intermedio", 2), ("AVANZADO", "Avanzado", 3), ("EXPERTO", "Experto", 4)))
        self._ranked_catalog(NivelIdioma, (("A1", "A1 · Principiante", 1), ("A2", "A2 · Básico", 2), ("B1", "B1 · Intermedio", 3), ("B2", "B2 · Intermedio alto", 4), ("C1", "C1 · Avanzado", 5), ("C2", "C2 · Dominio", 6)))
        self._named_catalog(AreaEstudio, ("Ciencias de la computación", "Ingeniería en sistemas", "Diseño", "Administración de empresas", "Estadística y matemáticas"))
        self._named_catalog(Habilidad, ("Python", "Django", "PostgreSQL", "JavaScript", "Figma", "Power BI", "AWS", "Docker", "Comunicación", "Liderazgo"), {"activo": True})
        for code, name in (("es", "Español"), ("en", "Inglés"), ("pt", "Portugués")):
            Idioma.objects.update_or_create(codigo_iso=code, defaults={"nombre": name})
        country, _ = Pais.objects.update_or_create(
            codigo_iso="GT", defaults={"nombre": "Guatemala"}
        )
        region, _ = Region.objects.update_or_create(
            pais=country,
            nombre="Guatemala",
            defaults={"codigo": "GU"},
        )
        city, _ = Ciudad.objects.update_or_create(
            region=region,
            nombre="Ciudad de Guatemala",
        )
        if self._has_table(Institucion):
            for name in (
                "Universidad de San Carlos de Guatemala",
                "Universidad Rafael Landívar",
                "Universidad del Valle de Guatemala",
            ):
                Institucion.objects.update_or_create(nombre=name, ciudad=city)
        if self._has_table(Certificacion):
            for name, organization in (
                ("AWS Certified Cloud Practitioner", "Amazon Web Services"),
                ("Professional Scrum Master I", "Scrum.org"),
                ("Google Data Analytics", "Google"),
            ):
                Certificacion.objects.update_or_create(
                    nombre=name,
                    organizacion_emisora=organization,
                )
        if self._has_table(ProveedorAlmacenamiento):
            for code, name in (
                ("LOCAL_PRIVADO", "Almacenamiento privado local"),
                ("BACKBLAZE_B2", "Almacenamiento privado Backblaze B2"),
            ):
                ProveedorAlmacenamiento.objects.update_or_create(
                    codigo=code,
                    defaults={"nombre": name},
                )
        self.stdout.write(self.style.SUCCESS("Catálogos del sistema inicializados."))

    def _has_table(self, model):
        return model._meta.db_table in self.available_tables

    def _code_catalog(self, model, rows):
        for code, name, extra in rows:
            model.objects.update_or_create(codigo=code, defaults={"nombre": name, **extra})

    def _named_catalog(self, model, names, defaults=None):
        for name in names:
            model.objects.update_or_create(nombre=name, defaults=defaults or {})

    def _ranked_catalog(self, model, rows):
        for code, name, rank in rows:
            model.objects.update_or_create(codigo=code, defaults={"nombre": name, "orden_nivel": rank})
