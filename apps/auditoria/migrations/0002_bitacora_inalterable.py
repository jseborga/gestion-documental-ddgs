"""La base de datos rechaza UPDATE y DELETE sobre la bitácora (ADR-06)."""

from django.db import migrations

CREAR = """
CREATE OR REPLACE FUNCTION auditoria_bitacora_inalterable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora es de solo agregado: % no está permitido', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER bitacora_sin_update_ni_delete
    BEFORE UPDATE OR DELETE ON auditoria_bitacora
    FOR EACH ROW EXECUTE FUNCTION auditoria_bitacora_inalterable();
"""

QUITAR = """
DROP TRIGGER IF EXISTS bitacora_sin_update_ni_delete ON auditoria_bitacora;
DROP FUNCTION IF EXISTS auditoria_bitacora_inalterable();
"""


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0001_initial")]

    operations = [migrations.RunSQL(CREAR, reverse_sql=QUITAR)]
