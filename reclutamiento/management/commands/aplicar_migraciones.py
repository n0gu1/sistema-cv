import hashlib
from pathlib import Path

from django.conf import settings
from django.core import management
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


MIGRATIONS_DIRECTORY = "database/migraciones"
MIGRATION_TABLE = "esquema_migraciones"
MIGRATION_LOCK_NAME = "nexo_talento_schema_migrations"


class Command(BaseCommand):
    help = "Aplica las migraciones SQL versionadas del esquema PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--instalar-esquema",
            action="store_true",
            help="Instala schema.sql y migracion_espanol.sql si la base esta vacia.",
        )
        parser.add_argument(
            "--inicializar-catalogos",
            action="store_true",
            help="Ejecuta inicializar_catalogos despues de aplicar las migraciones.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError(
                "aplicar_migraciones requiere una base de datos PostgreSQL."
            )

        if options["instalar_esquema"]:
            self._install_reference_schema_if_needed()

        migrations = self._migration_files()
        self._ensure_migration_table()
        applied = 0
        for path in migrations:
            if self._apply_migration(path):
                applied += 1

        if options["inicializar_catalogos"]:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    [MIGRATION_LOCK_NAME],
                )
                management.call_command("inicializar_catalogos", verbosity=0)

        self.stdout.write(
            self.style.SUCCESS(
                f"Migraciones verificadas: {len(migrations)}; nuevas: {applied}."
            )
        )

    def _migration_files(self):
        directory = Path(settings.BASE_DIR) / MIGRATIONS_DIRECTORY
        paths = sorted(directory.glob("*.sql"))
        if not paths:
            raise CommandError(f"No hay migraciones SQL en {directory}.")

        versions = set()
        for path in paths:
            version = path.name.split("_", 1)[0]
            if not version.isdigit():
                raise CommandError(
                    f"El archivo de migracion debe comenzar con un numero: {path.name}."
                )
            if version in versions:
                raise CommandError(f"Version de migracion duplicada: {version}.")
            versions.add(version)
        return paths

    def _ensure_migration_table(self):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                    version VARCHAR(20) PRIMARY KEY,
                    archivo VARCHAR(255) NOT NULL UNIQUE,
                    suma_sha256 CHAR(64) NOT NULL,
                    aplicada_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

    def _apply_migration(self, path):
        version = path.name.split("_", 1)[0]
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                [MIGRATION_LOCK_NAME],
            )
            cursor.execute(
                f"SELECT archivo, suma_sha256 FROM {MIGRATION_TABLE} WHERE version = %s",
                [version],
            )
            applied = cursor.fetchone()
            if applied:
                if applied != (path.name, checksum):
                    raise CommandError(
                        f"La migracion {version} fue modificada despues de aplicarse."
                    )
                return False

            cursor.execute(sql)
            cursor.execute(
                f"""
                INSERT INTO {MIGRATION_TABLE}
                    (version, archivo, suma_sha256)
                VALUES (%s, %s, %s)
                """,
                [version, path.name, checksum],
            )

        self.stdout.write(f"Aplicada migracion {path.name}.")
        return True

    def _install_reference_schema_if_needed(self):
        tables = set(connection.introspection.table_names())
        if "roles_usuario" in tables:
            self.stdout.write("El esquema en espanol ya existe; se omite la instalacion base.")
            return

        database_directory = Path(settings.BASE_DIR) / "database"
        if "roles" in tables:
            self._execute_script(database_directory / "migracion_espanol.sql")
            self.stdout.write("Esquema en ingles traducido al esquema en espanol.")
            return

        framework_tables = {
            table
            for table in tables
            if table.startswith("auth_") or table.startswith("django_")
        }
        if tables - framework_tables:
            raise CommandError(
                "La base contiene tablas parciales; no se instala schema.sql automaticamente."
            )

        self._execute_script(database_directory / "schema.sql")
        self._execute_script(database_directory / "migracion_espanol.sql")
        self.stdout.write("schema.sql y migracion_espanol.sql aplicados.")

    def _execute_script(self, path):
        if not path.is_file():
            raise CommandError(f"No existe el script SQL requerido: {path}.")
        with connection.cursor() as cursor:
            cursor.execute(path.read_text(encoding="utf-8"))
