"""Borra las sugerencias del Taller anterior, que proponía texto escrito por el sistema (resúmenes y reescrituras). El
Taller actual solo pregunta, y lo que se copia es la respuesta del candidato (revisión independiente, hallazgo 6)."""

from django.db import migrations

PREFIJO_PREGUNTA = "¿Has trabajado con «"


def borrar_sugerencias_del_taller_anterior(apps, schema_editor):
    SugerenciaCV = apps.get_model("matching", "SugerenciaCV")
    SugerenciaCV.objects.exclude(tipo="requisito", propuesta__startswith=PREFIJO_PREGUNTA).delete()


class Migration(migrations.Migration):
    dependencies = [("matching", "0007_decision_huella")]
    operations = [migrations.RunPython(borrar_sugerencias_del_taller_anterior, migrations.RunPython.noop)]
