"""Verifica la conexión al almacenamiento S3 y crea el bucket si no existe."""

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Comprueba el bucket configurado (S3_BUCKET) y lo crea si falta."

    def handle(self, *args, **opciones):
        if not settings.S3_ENDPOINT:
            self.stdout.write("Almacenamiento local (sin S3 configurado): nada que preparar.")
            return
        bucket = settings.STORAGES["default"]["OPTIONS"]["bucket_name"]
        cliente = default_storage.connection.meta.client
        try:
            cliente.head_bucket(Bucket=bucket)
            self.stdout.write(self.style.SUCCESS(f"Bucket '{bucket}' disponible."))
            return
        except ClientError as error:
            codigo = str(error.response.get("Error", {}).get("Code", ""))
            if codigo not in ("404", "NoSuchBucket", "NotFound"):
                raise CommandError(
                    f"No se pudo acceder al bucket '{bucket}' (código {codigo}). "
                    "Revise S3_ACCESS_KEY, S3_SECRET_KEY y los permisos de esa identidad."
                ) from error
        except BotoCoreError as error:
            raise CommandError(
                f"No se pudo conectar a {settings.S3_ENDPOINT}: {error}. Revise S3_ENDPOINT "
                "y que el servicio de SeaweedFS esté en la misma red de Docker."
            ) from error
        try:
            cliente.create_bucket(Bucket=bucket)
        except (ClientError, BotoCoreError) as error:
            raise CommandError(
                f"El bucket '{bucket}' no existe y no se pudo crear: {error}. "
                "Créelo en SeaweedFS o use una identidad con permiso de administración."
            ) from error
        self.stdout.write(self.style.SUCCESS(f"Bucket '{bucket}' creado."))
