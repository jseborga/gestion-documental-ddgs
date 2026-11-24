from django.urls import path

from . import views

app_name = "institutos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("mapa/", views.mapa, name="mapa"),
    path("geojson/", views.geojson, name="geojson"),
    path("<int:pk>/", views.ficha, name="ficha"),
    path("<int:pk>/ubicacion/", views.registrar_ubicacion, name="registrar_ubicacion"),
]
