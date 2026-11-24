"""Catálogos institucionales (SPEC.md §5.1). La escritura pasa por `services.py`."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ModeloBase(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Unidad(ModeloBase):
    class Nivel(models.TextChoices):
        EJECUTIVO = "ejecutivo", "Ejecutivo"
        DESCONCENTRADO = "desconcentrado", "Desconcentrado"
        OPERATIVO = "operativo", "Operativo"

    sigla = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=200)
    nivel = models.CharField(max_length=20, choices=Nivel.choices, default=Nivel.EJECUTIVO)
    padre = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="hijas"
    )
    prefijo_cite = models.CharField(
        max_length=80,
        blank=True,
        help_text="Ej. GADLP/SDGS/DDGS. Vacío si la unidad no emite CITE.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "unidad"
        verbose_name_plural = "unidades"
        ordering = ["sigla"]

    def __str__(self) -> str:
        return self.sigla


class Cargo(ModeloBase):
    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, related_name="cargos")
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=150)
    puede_firmar = models.BooleanField(default=False)
    es_ventanilla = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["unidad__sigla", "codigo"]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.unidad.sigla})"


class Persona(ModeloBase):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="persona",
    )
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    nombre_corto = models.CharField(max_length=60, blank=True, help_text='Ej. "Ing. M. N."')
    profesion = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["apellidos", "nombres"]
        constraints = [
            models.UniqueConstraint(
                fields=["email"], condition=~Q(email=""), name="persona_email_unico"
            )
        ]

    def __str__(self) -> str:
        return self.nombre_corto or f"{self.nombres} {self.apellidos}"


class OcupacionCargo(ModeloBase):
    class Tipo(models.TextChoices):
        TITULAR = "titular", "Titular"
        INTERINO = "interino", "Interino"
        SUPLENTE = "suplente", "Suplente"

    persona = models.ForeignKey(Persona, on_delete=models.PROTECT, related_name="ocupaciones")
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="ocupaciones")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    desde = models.DateField()
    hasta = models.DateField(null=True, blank=True, help_text="Vacío = vigente.")
    acto_designacion = models.CharField(
        max_length=150, blank=True, help_text="Memorándum o resolución de designación."
    )

    class Meta:
        verbose_name = "ocupación de cargo"
        verbose_name_plural = "ocupaciones de cargo"
        ordering = ["-desde"]
        constraints = [
            models.CheckConstraint(
                condition=Q(hasta__isnull=True) | Q(hasta__gte=F("desde")),
                name="ocupacion_hasta_no_anterior_a_desde",
            ),
            # Red de seguridad en la base: un solo titular abierto por cargo.
            # El solapamiento con periodos cerrados lo valida services.asignar_cargo.
            models.UniqueConstraint(
                fields=["cargo"],
                condition=Q(tipo="titular", hasta__isnull=True),
                name="un_titular_abierto_por_cargo",
            ),
        ]
        indexes = [models.Index(fields=["persona", "desde", "hasta"])]

    def __str__(self) -> str:
        return f"{self.persona} — {self.cargo} ({self.get_tipo_display()})"


class InstitucionExterna(ModeloBase):
    class Tipo(models.TextChoices):
        GAM = "gam", "Gobierno autónomo municipal"
        INSTITUTO = "instituto", "Instituto técnico tecnológico"
        CONTRATISTA = "contratista", "Empresa contratista"
        SUPERVISION = "supervision", "Supervisión"
        MINISTERIO = "ministerio", "Ministerio"
        ENTIDAD_DEPARTAMENTAL = "entidad_departamental", "Entidad departamental"
        OTRA = "otra", "Otra"

    codigo = models.CharField(max_length=40, unique=True)
    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    nombre = models.CharField(max_length=250)
    sigla = models.CharField(max_length=40, blank=True)
    autoridad_nombre = models.CharField(max_length=150, blank=True)
    autoridad_cargo = models.CharField(max_length=100, blank=True)
    municipio = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "institución externa"
        verbose_name_plural = "instituciones externas"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.sigla or self.nombre


class Proceso(ModeloBase):
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=150)
    padre = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="subprocesos"
    )
    requiere_proyecto = models.BooleanField(default=False)
    plazo_dias_defecto = models.PositiveSmallIntegerField(
        default=5, help_text="Días hábiles. Provisional hasta contar con la tabla de plazos."
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]

    def __str__(self) -> str:
        return self.nombre


class Proyecto(ModeloBase):
    class Tipo(models.TextChoices):
        CONSTRUCCION = "construccion", "Construcción"
        REFACCION = "refaccion", "Refacción"
        EQUIPAMIENTO = "equipamiento", "Equipamiento"
        ESTUDIO = "estudio", "Estudio"
        PROGRAMA = "programa", "Programa"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        SIN_DATO = "sin_dato", "Sin dato"
        PROGRAMADO = "programado", "Programado (por ejecutar)"
        PREINVERSION = "preinversion", "Preinversión"
        CONTRATACION = "contratacion", "Contratación"
        EN_EJECUCION = "en_ejecucion", "En ejecución"
        PARALIZADA = "paralizada", "Paralizada"
        RECEPCION_PROVISIONAL = "recepcion_provisional", "Recepción provisional"
        RECEPCION_DEFINITIVA = "recepcion_definitiva", "Recepción definitiva"
        SIN_CIERRE_FINANCIERO = (
            "concluida_sin_cierre_financiero",
            "Concluida sin cierre financiero",
        )
        CONCLUIDA = "concluida", "Concluida"
        CERRADA = "cerrada", "Cerrada"

    unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, related_name="proyectos")
    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=300)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.OTRO)
    instituto = models.ForeignKey(
        InstitucionExterna,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="proyectos",
        limit_choices_to={"tipo": InstitucionExterna.Tipo.INSTITUTO},
    )
    municipio = models.CharField(max_length=100, blank=True)
    contrato_ref = models.CharField(max_length=60, blank=True, help_text="Ej. LPN/34/2025")
    codigo_sisin = models.CharField(max_length=30, blank=True)
    gestion_inicio = models.PositiveSmallIntegerField(null=True, blank=True)
    gestion_fin = models.PositiveSmallIntegerField(null=True, blank=True)
    presupuesto_bs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    ejecutado_bs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=35, choices=Estado.choices, default=Estado.PREINVERSION)
    estado_detalle = models.TextField(
        blank=True, help_text="Texto del estado tal como llegó de la fuente."
    )
    cargo_fiscal = models.ForeignKey(
        Cargo,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="proyectos_fiscalizados",
    )

    class Meta:
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(
                condition=Q(presupuesto_bs__isnull=True) | Q(presupuesto_bs__gte=0),
                name="proyecto_presupuesto_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(ejecutado_bs__isnull=True) | Q(ejecutado_bs__gte=0),
                name="proyecto_ejecutado_no_negativo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} — {self.nombre}"


class Feriado(ModeloBase):
    class Ambito(models.TextChoices):
        NACIONAL = "nacional", "Nacional"
        DEPARTAMENTAL = "departamental", "Departamental"
        INSTITUCIONAL = "institucional", "Institucional"

    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=120)
    ambito = models.CharField(max_length=15, choices=Ambito.choices)

    class Meta:
        ordering = ["fecha"]

    def __str__(self) -> str:
        return f"{self.fecha:%d/%m/%Y} {self.nombre}"
