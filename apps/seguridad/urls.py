from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "seguridad"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="entrar"),
    path("salir/", auth_views.LogoutView.as_view(), name="salir"),
    path("2fa/verificar/", views.verificar, name="verificar"),
    path("2fa/configurar/", views.configurar_2fa, name="configurar_2fa"),
    path("2fa/codigos/", views.regenerar_codigos, name="regenerar_codigos"),
    path("sesiones/", views.mis_sesiones, name="mis_sesiones"),
]
