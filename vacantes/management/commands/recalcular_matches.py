from django.core.management.base import BaseCommand

from vacantes.scoring import recalcular_matches_todos


class Command(BaseCommand):
    help = (
        "HU-06: recalcula y persiste el ranking de 'Matches de hoy' para todos los "
        "perfiles con CV cargado. Es la misma lógica que dispara "
        "POST /api/recalcular-matches (el endpoint que llama el workflow de n8n) — "
        "este comando existe para poder probarla sin depender de que n8n esté corriendo."
    )

    def handle(self, *args, **options):
        resultado = recalcular_matches_todos()
        self.stdout.write(
            self.style.SUCCESS(
                f"{resultado['fecha']}: {resultado['perfiles_procesados']} perfiles procesados, "
                f"{resultado['matches_guardados']} matches guardados."
            )
        )
