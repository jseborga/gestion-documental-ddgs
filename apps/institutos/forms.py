from django import forms

from .models import DerechoPropietario, Precision
from .selectors import SEMAFORO


class FiltroForm(forms.Form):
    q = forms.CharField(required=False, max_length=80, label="Buscar")
    region = forms.ChoiceField(required=False, label="Región")
    provincia = forms.ChoiceField(required=False, label="Provincia")
    estado = forms.ChoiceField(
        required=False, label="Situación", choices=[("", "Todas"), *SEMAFORO.items()]
    )
    derecho = forms.ChoiceField(
        required=False,
        label="Derecho propietario",
        choices=[("", "Todos"), *DerechoPropietario.Estado.choices],
    )
    sin_ubicacion = forms.BooleanField(required=False, label="Solo sin ubicación")

    def __init__(self, *args, regiones=(), provincias=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["region"].choices = [("", "Todas"), *((r, r) for r in regiones)]
        self.fields["provincia"].choices = [("", "Todas"), *((p, p) for p in provincias)]


class UbicacionForm(forms.Form):
    coordenadas = forms.CharField(
        label="Coordenadas o enlace de Google Maps",
        max_length=2000,
        help_text="Ej.: -16.4955, -68.1336 o el enlace completo de Google Maps.",
    )
    precision = forms.ChoiceField(
        label="Precisión",
        choices=[c for c in Precision.choices if c[0] != Precision.PENDIENTE],
        initial=Precision.VERIFICADA_MAPA,
    )
    fuente = forms.CharField(label="Fuente", max_length=200, required=False)
