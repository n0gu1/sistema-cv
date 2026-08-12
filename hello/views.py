from django.db import connection
from django.http import HttpResponse, JsonResponse


def index(request):
    return HttpResponse("Hola, mundo!")


def salud(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    return JsonResponse({"aplicacion": "disponible", "base_de_datos": "conectada"})
