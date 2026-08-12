from django.urls import path

from hello.views import index, salud

urlpatterns = [
    path("", index, name="index"),
    path("salud/", salud, name="salud"),
]
