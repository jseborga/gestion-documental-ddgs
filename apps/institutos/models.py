"""Institutos técnicos tecnológicos (docs/modulo-institutos.md §3).

Los datos personales (autoridades y teléfonos) viven en su propia tabla y solo los ve
quien opera la unidad. La ubicación vigente se copia en el instituto para que la lista
y el mapa se resuelvan en una consulta; el historial queda en `Ubicacion`.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import InstitucionExterna, ModeloBase, Unidad


class Precision(models.TextChoices):
    GPS_SITIO = "gps_sitio", "GPS en el sitio"
    VERIFICADA_MAPA = "verificada_mapa", "Verificada en mapa"
    APROXIMADA = "aproximada_localidad", "Aproximada (localidad o municipio)"
    PENDIENTE = "pendiente", "Pendiente"


class Instituto(ModeloBase):
    class Dependencia(models.TextChoices):
        FISCAL = "fiscal", "Fiscal"
        CONVENIO = "convenio", "De convenio"
        PRIVADO = "privado", "Privado"
        SIN_DATO = "sin_dato", "Sin dato"

    institucion = models.OneToOneField(
        InstitucionExterna, on_delete=models.PROTECT, related_name="instituto"
    )
    unidad = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        related_name="institutos",
        help_text="Unidad responsable del seguimiento (define quién ve la ficha).",
    )
    numero = models.PositiveIntegerField(
        null=True, blank=True, unique=True, help_text="N° en la planilla de origen."
    )
    nombre = models.CharField(max_length=250)
    sede_principal = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="subsedes"
    )
    es_subsede = models.BooleanField(default=False)
    region = models.CharField(max_length=60, blank=True, db_index=True)
    provincia = models.CharField(max_length=80, blank=True, db_index=True)
    municipio = models.CharField(max_length=80, blank=True, db_index=True)
    direccion = models.CharField(max_length=300, blank=True)
    situacion = models.CharField(max_length=200, blank=True)
    dependencia = models.CharField(
        max_length=10, choices=Dependencia.choices, default=Dependencia.SIN_DATO
    )
    dependencia_texto = models.CharField(max_length=150, blank=True)
    clasificacion = models.CharField(max_length=15, default="interno")
    # Ubicación vigente (copia de la última `Ubicacion`)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    precision = models.CharField(
        max_length=25, choices=Precision.choices, default=Precision.PENDIENTE
    )

    class Meta:
        ordering = ["numero", "nombre"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(lat__isnull=True) & Q(lon__isnull=True))
                | (Q(lat__gte=-90) & Q(lat__lte=90) & Q(lon__gte=-180) & Q(lon__lte=180)),
                name="instituto_coordenadas_validas",
            )
        ]

    def __str__(self) -> str:
        return self.nombre

    # --- RecursoProtegido (apps.seguridad.permisos) ---------------------------------
    def cargos_con_acceso(self) -> set[int]:
        return set()

    def cargos_responsables(self) -> set[int]:
        # Edita la ficha el personal de la unidad, salvo la ventanilla.
        return set(
            self.unidad.cargos.filter(activo=True, es_ventanilla=False).values_list("pk", flat=True)
        )

    def cargos_firmantes(self) -> set[int]:
        return set()

    @property
    def tiene_ubicacion(self) -> bool:
        return self.lat is not None and self.lon is not None


class Ubicacion(models.Model):
    instituto = models.ForeignKey(Instituto, on_delete=models.CASCADE, related_name="ubicaciones")
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lon = models.DecimalField(max_digits=9, decimal_places=6)
    precision = models.CharField(max_length=25, choices=Precision.choices)
    fuente = models.CharField(max_length=200, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ubicación"
        verbose_name_plural = "ubicaciones"
        ordering = ["-creado_en", "-id"]

    def __str__(self) -> str:
        return f"{self.instituto} ({self.lat}, {self.lon})"


class AutoridadInstituto(ModeloBase):
    """Dato personal: visible solo para quien puede editar la ficha."""

    instituto = models.ForeignKey(Instituto, on_delete=models.CASCADE, related_name="autoridades")
    nombre = models.CharField(max_length=150)
    cargo = models.CharField(max_length=80, default="Rector(a)")
    telefono = models.CharField(max_length=40, blank=True)
    vigente = models.BooleanField(default=True)

    class Meta:
        verbose_name = "autoridad del instituto"
        verbose_name_plural = "autoridades de institutos"

    def __str__(self) -> str:
        return f"{self.cargo}: {self.nombre}"


class ResolucionMinisterial(ModeloBase):
    instituto = models.ForeignKey(Instituto, on_delete=models.CASCADE, related_name="resoluciones")
    texto = models.CharField(max_length=300)
    anio = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "resolución ministerial"
        verbose_name_plural = "resoluciones ministeriales"
        constraints = [
            models.UniqueConstraint(fields=["instituto", "texto"], name="rm_unica_por_instituto")
        ]

    def __str__(self) -> str:
        return self.texto


class DerechoPropietario(ModeloBase):
    class Estado(models.TextChoices):
        A_NOMBRE_ENTIDAD = "a_nombre_entidad", "A nombre de la entidad"
        EN_PROCESO_CON_FOLIO = "en_proceso_con_folio", "En proceso, con folio real"
        EN_PROCESO_SIN_ANTECEDENTES = "en_proceso_sin_antecedentes", "En proceso, sin antecedentes"
        OTRO = "otro", "Otro"
        SIN_DATO = "sin_dato", "Sin dato"

    instituto = models.OneToOneField(
        Instituto, on_delete=models.CASCADE, related_name="derecho_propietario"
    )
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.SIN_DATO)
    folio_real = models.CharField(max_length=40, blank=True, db_index=True)
    detalle = models.TextField(blank=True)

    class Meta:
        verbose_name = "derecho propietario"
        verbose_name_plural = "derechos propietarios"

    def __str__(self) -> str:
        return f"{self.instituto}: {self.get_estado_display()}"

    @property
    def apto_para_inversion(self) -> bool:
        """Inversión solo con derecho propietario a nombre de la entidad (DD 100, 20.II)."""
        return self.estado == self.Estado.A_NOMBRE_ENTIDAD


class Matricula(ModeloBase):
    instituto = models.ForeignKey(Instituto, on_delete=models.CASCADE, related_name="matriculas")
    anio = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField(null=True, blank=True)
    estudiantes = models.PositiveIntegerField()
    fuente = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "matrícula"
        ordering = ["-anio", "-mes"]
        constraints = [
            models.UniqueConstraint(
                fields=["instituto", "anio", "mes", "fuente"],
                name="matricula_unica",
                nulls_distinct=False,  # sin mes también cuenta como duplicado
            ),
            models.CheckConstraint(
                condition=Q(mes__isnull=True) | (Q(mes__gte=1) & Q(mes__lte=12)),
                name="matricula_mes_valido",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.instituto} {self.anio}: {self.estudiantes}"


class Carrera(ModeloBase):
    instituto = models.ForeignKey(Instituto, on_delete=models.CASCADE, related_name="carreras")
    nombre = models.CharField(max_length=200)
    vigente = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["instituto", "nombre"], name="carrera_unica")
        ]

    def __str__(self) -> str:
        return self.nombre


class TechoPresupuestario(ModeloBase):
    instituto = models.ForeignKey(Instituto, on_delete=models.CASCADE, related_name="techos")
    gestion = models.PositiveSmallIntegerField()
    monto_bs = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "techo presupuestario"
        verbose_name_plural = "techos presupuestarios"
        ordering = ["-gestion"]
        constraints = [
            models.UniqueConstraint(fields=["instituto", "gestion"], name="techo_unico"),
            models.CheckConstraint(
                condition=Q(monto_bs__gte=Decimal("0")), name="techo_no_negativo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.instituto} {self.gestion}: Bs {self.monto_bs}"


class ObservacionDato(ModeloBase):
    """Inconsistencias de los datos de origen, para que la Dirección las resuelva."""

    instituto = models.ForeignKey(
        Instituto, null=True, blank=True, on_delete=models.CASCADE, related_name="observaciones"
    )
    texto = models.CharField(max_length=500)
    origen = models.CharField(max_length=30, default="importacion")
    resuelta = models.BooleanField(default=False)
    respuesta = models.TextField(blank=True)

    class Meta:
        verbose_name = "observación de datos"
        verbose_name_plural = "observaciones de datos"
        ordering = ["resuelta", "instituto__numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["instituto", "texto", "origen"],
                name="observacion_unica",
                nulls_distinct=False,
            )
        ]

    def __str__(self) -> str:
        return self.texto[:80]
