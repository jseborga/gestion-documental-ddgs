from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.seguridad import views as seguridad_views

# El admin usa el mismo inicio de sesión (con bloqueo por intentos y segundo factor).
admin.site.login = RedirectView.as_view(pattern_name="seguridad:entrar", query_string=True)
admin.site.site_header = "Gestión documental: administración"
admin.site.site_title = "Administración"

urlpatterns = [
    path("", seguridad_views.inicio, name="inicio"),
    path("seguridad/", include("apps.seguridad.urls")),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.api.urls")),
]
