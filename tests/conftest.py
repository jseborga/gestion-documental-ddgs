import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice


def verificar_cliente(client, usuario):
    """Inicia sesión y marca el segundo factor como verificado (como tras ingresar el código)."""
    dispositivo = TOTPDevice.objects.filter(user=usuario, confirmed=True).first()
    if dispositivo is None:
        dispositivo = TOTPDevice.objects.create(user=usuario, name="prueba", confirmed=True)
    client.force_login(usuario)
    sesion = client.session
    sesion["otp_device_id"] = dispositivo.persistent_id
    sesion.save()
    return client


@pytest.fixture
def admin_client(db, admin_user, client):
    """Superusuario con segundo factor verificado (reemplaza el de pytest-django)."""
    return verificar_cliente(client, admin_user)
