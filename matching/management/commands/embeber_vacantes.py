from django.core.management.base import BaseCommand

from matching.ia import obtener_embedder, obtener_embedder_cobertura
from matching.vectores import embeber_vacantes


class Command(BaseCommand):
    help = "Calcula los vectores de las vacantes nuevas o modificadas (carga los modelos de búsqueda y de cobertura)."

    def handle(self, *args, **options):
        self.stdout.write(f"vacantes embebidas: {embeber_vacantes(obtener_embedder(), cobertura=obtener_embedder_cobertura())}")
