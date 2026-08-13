from django.urls import path

from hello.views import (
    analisis,
    aspirantes,
    cambiar_contrasena,
    cerrar_sesion,
    dashboard,
    index,
    nueva_plaza,
    plazas,
    portal,
    reenviar_verificacion,
    registrar_aspirante,
    restablecer_contrasena,
    salud,
    solicitar_recuperacion,
    verificar_correo,
)

urlpatterns = [
    path("", index, name="index"),
    path("dashboard/", dashboard, name="dashboard"),
    path("plazas/", plazas, name="plazas"),
    path("plazas/nueva/", nueva_plaza, name="nueva_plaza"),
    path("aspirantes/", aspirantes, name="aspirantes"),
    path("analisis/", analisis, name="analisis"),
    path("portal/", portal, name="portal"),
    path("cuenta/registro/", registrar_aspirante, name="registrar_aspirante"),
    path(
        "cuenta/reenviar-verificacion/",
        reenviar_verificacion,
        name="reenviar_verificacion",
    ),
    path("cuenta/salir/", cerrar_sesion, name="cerrar_sesion"),
    path(
        "cuenta/cambiar-contrasena/",
        cambiar_contrasena,
        name="cambiar_contrasena",
    ),
    path(
        "cuenta/recuperar/",
        solicitar_recuperacion,
        name="solicitar_recuperacion",
    ),
    path(
        "cuenta/restablecer/<uidb64>/<token>/",
        restablecer_contrasena,
        name="restablecer_contrasena",
    ),
    path(
        "cuenta/verificar/<uidb64>/<token>/",
        verificar_correo,
        name="verificar_correo",
    ),
    path("salud/", salud, name="salud"),
]
