from django.conf import settings
from django.db import models


class SesionUsuario(models.Model):
    """Sesiones abiertas por usuario, para la pantalla "mis sesiones" (§2.2)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sesiones_abiertas"
    )
    clave_sesion = models.CharField(max_length=40, unique=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    agente = models.CharField(max_length=255, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sesión de usuario"
        verbose_name_plural = "sesiones de usuario"
        ordering = ["-inicio"]

    def __str__(self) -> str:
        return f"{self.usuario} desde {self.ip} ({self.inicio:%Y-%m-%d %H:%M})"
