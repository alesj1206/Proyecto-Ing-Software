from django.core.management.base import BaseCommand

from matching.ia import obtener_embedder
from matching.vectores import embeber_vacantes


class Command(BaseCommand):
    help = "Calcula los vectores de las vacantes nuevas o modificadas (carga el modelo de embeddings)."

    def handle(self, *args, **options):
        self.stdout.write(f"vacantes embebidas: {embeber_vacantes(obtener_embedder())}")
