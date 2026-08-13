from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from reclutamiento.models import RolUsuario, Usuario, UsuarioRol


class Command(BaseCommand):
    help = "Crea un usuario verificado y le asigna un rol del sistema."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--nombres", required=True)
        parser.add_argument("--apellidos", required=True)
        parser.add_argument(
            "--rol",
            required=True,
            choices=("ADMINISTRADOR", "RRHH", "ASPIRANTE"),
        )
        parser.add_argument("--password")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise CommandError("Ya existe un usuario con ese correo.")

        password = options["password"] or self._prompt_password()
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        role = RolUsuario.objects.filter(codigo=options["rol"]).first()
        if role is None:
            raise CommandError(f"El rol {options['rol']} no existe en la base de datos.")

        user = Usuario.objects.create_user(
            email=email,
            password=password,
            first_name=options["nombres"].strip(),
            last_name=options["apellidos"].strip(),
            is_active=True,
            is_verified=True,
        )
        UsuarioRol.objects.create(usuario=user, rol=role, asignado_en=timezone.now())
        self.stdout.write(self.style.SUCCESS(f"Usuario {email} creado con rol {role.codigo}."))

    def _prompt_password(self):
        import getpass

        password = getpass.getpass("Contraseña: ")
        confirmation = getpass.getpass("Confirmar contraseña: ")
        if password != confirmation:
            raise CommandError("Las contraseñas no coinciden.")
        return password
