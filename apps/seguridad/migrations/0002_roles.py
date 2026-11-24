"""Crea los roles del sistema como grupos de Django (SPEC.md §7)."""

from django.db import migrations

ROLES = ["administrador", "director", "ventanilla", "tecnico", "consulta", "auditor"]


def crear(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nombre in ROLES:
        Group.objects.get_or_create(name=nombre)


def quitar(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [("seguridad", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]

    operations = [migrations.RunPython(crear, quitar)]
