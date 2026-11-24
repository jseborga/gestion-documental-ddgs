from django import forms


class CodigoForm(forms.Form):
    codigo = forms.CharField(
        label="Código",
        max_length=20,
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "text", "autofocus": True}
        ),
    )
