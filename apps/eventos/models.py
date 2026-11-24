"""Outbox transaccional (SPEC.md §5.5) y registro de tareas periódicas."""

from django.db import models


class EventoOutbox(models.Model):
    tipo = models.CharField(max_length=80, db_index=True)
    agregado = models.CharField(max_length=80)
    agregado_id = models.CharField(max_length=40)
    payload = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    procesado_en = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventos (outbox)"
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["id"],
                condition=models.Q(procesado_en__isnull=True),
                name="evento_pendiente_idx",
            )
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.tipo} {self.agregado}:{self.agregado_id}"


class EjecucionTarea(models.Model):
    """Última ejecución de cada tarea periódica del worker (evita repetirlas)."""

    nombre = models.CharField(max_length=80, unique=True)
    ultima_ejecucion = models.DateTimeField()
    ultimo_resultado = models.TextField(blank=True)

    class Meta:
        verbose_name = "ejecución de tarea"
        verbose_name_plural = "ejecuciones de tareas"

    def __str__(self) -> str:
        return f"{self.nombre} ({self.ultima_ejecucion:%Y-%m-%d %H:%M})"
