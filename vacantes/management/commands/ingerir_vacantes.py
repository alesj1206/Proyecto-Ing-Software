from pathlib import Path

from django.core.management.base import BaseCommand

from vacantes.fuentes.fixture import FuenteFixture
from vacantes.fuentes.magneto_detalle import FuenteMagnetoDetalle
from vacantes.services import ingerir

RUTA_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "vacantes_magneto.json"
TERMINOS_POR_DEFECTO = ["analista de datos", "desarrollador", "auxiliar contable", "asesor comercial",
                        "auxiliar administrativo", "diseñador grafico"]


class Command(BaseCommand):
    help = "Ingiere vacantes (texto completo + requisitos) desde una fuente. Solo reescribe las que cambiaron."

    def add_arguments(self, parser):
        parser.add_argument("--fuente", choices=["fixture", "magneto"], default="fixture")
        parser.add_argument("--terminos", nargs="+", default=TERMINOS_POR_DEFECTO)
        parser.add_argument("--por-termino", type=int, default=5)

    def handle(self, *args, fuente, terminos, por_termino, **options):
        estrategia = FuenteFixture(RUTA_FIXTURE) if fuente == "fixture" else FuenteMagnetoDetalle(terminos, por_termino)
        self.stdout.write(str(ingerir(estrategia)))
