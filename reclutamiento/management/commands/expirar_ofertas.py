from django.core.management.base import BaseCommand

from reclutamiento.applications import expire_offers


class Command(BaseCommand):
    help = "Marca ofertas vencidas y resuelve sus postulaciones de forma idempotente."

    def handle(self, *args, **options):
        total = expire_offers()
        self.stdout.write(self.style.SUCCESS(f"Ofertas vencidas procesadas: {total}."))
