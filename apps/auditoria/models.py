"""Bitácora append-only (SPEC.md §5.4). La base de datos impide UPDATE y DELETE."""

from django.conf import settings
from django.db import models


class Bitacora(models.Model):
    class Categoria(models.TextChoices):
        NEGOCIO = "negocio", "Negocio"
        SEGURIDAD = "seguridad", "Seguridad"

    categoria = models.CharField(
        max_length=10, choices=Categoria.choices, default=Categoria.NEGOCIO, db_index=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,  # la fila nunca se toca aunque se borre el usuario
        db_constraint=False,
        related_name="+",
    )
    actor_nombre = models.CharField(
        max_length=150, blank=True, help_text="Copia del usuario al momento del hecho."
    )
    accion = models.CharField(max_length=80, db_index=True)
    objeto_tipo = models.CharField(max_length=80, blank=True)
    objeto_id = models.CharField(max_length=40, blank=True)
    antes = models.JSONField(null=True, blank=True)
    despues = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "registro de bitácora"
        verbose_name_plural = "bitácora"
        ordering = ["-creado_en", "-id"]
        indexes = [models.Index(fields=["objeto_tipo", "objeto_id"])]

    def __str__(self) -> str:
        return f"{self.creado_en:%Y-%m-%d %H:%M} {self.accion} {self.objeto_tipo}:{self.objeto_id}"
