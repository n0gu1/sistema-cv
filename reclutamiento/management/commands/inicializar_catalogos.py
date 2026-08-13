from django.core.management.base import BaseCommand
from django.db import transaction

from reclutamiento.models import (
    AreaEstudio,
    Departamento,
    EstadoPlaza,
    Habilidad,
    Idioma,
    ModalidadTrabajo,
    NivelEducativo,
    NivelHabilidad,
    NivelIdioma,
    PeriodoSalarial,
    Profesion,
    TipoEmpleo,
    TipoRequisito,
)


class Command(BaseCommand):
    help = "Inicializa de forma idempotente los catálogos necesarios para plazas."

    @transaction.atomic
    def handle(self, *args, **options):
        self._code_catalog(EstadoPlaza, (("BORRADOR", "Pendiente", {"es_final": False}), ("PUBLICADA", "Activa", {"es_final": False}), ("PAUSADA", "Pausada", {"es_final": False}), ("CERRADA", "Cerrada", {"es_final": True})))
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
        self.stdout.write(self.style.SUCCESS("Catálogos de plazas inicializados."))

    def _code_catalog(self, model, rows):
        for code, name, extra in rows:
            model.objects.update_or_create(codigo=code, defaults={"nombre": name, **extra})

    def _named_catalog(self, model, names, defaults=None):
        for name in names:
            model.objects.update_or_create(nombre=name, defaults=defaults or {})

    def _ranked_catalog(self, model, rows):
        for code, name, rank in rows:
            model.objects.update_or_create(codigo=code, defaults={"nombre": name, "orden_nivel": rank})
