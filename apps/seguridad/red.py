"""IP del cliente detrás de proxies (EasyPanel/Traefik u otro proxy inverso)."""

import ipaddress

from django.conf import settings


def ip_cliente(request) -> str | None:
    """IP real del cliente.

    Con `PROXIES_CONFIABLES = n > 0`, toma la n-ésima dirección desde el final de
    X-Forwarded-For: cada proxy confiable agrega una, así que las anteriores pueden
    venir falsificadas por el cliente y se ignoran. Con 0 usa REMOTE_ADDR.
    """
    n = getattr(settings, "PROXIES_CONFIABLES", 0)
    candidata = request.META.get("REMOTE_ADDR")
    if n > 0:
        cadena = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")]
        cadena = [p for p in cadena if p]
        if len(cadena) >= n:
            candidata = cadena[-n]
    try:
        return str(ipaddress.ip_address(candidata)) if candidata else None
    except ValueError:
        return None
