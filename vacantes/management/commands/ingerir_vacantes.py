from collections.abc import Callable
from pathlib import Path

from django.core.management.base import BaseCommand

from vacantes.fuentes import FuenteVacantes
from vacantes.fuentes.fixture import FuenteFixture
from vacantes.fuentes.magneto_detalle import FuenteMagnetoDetalle
from vacantes.services import ingerir

RUTA_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "vacantes_magneto.json"
TERMINOS_POR_DEFECTO = ["analista de datos", "desarrollador", "auxiliar contable", "asesor comercial",
                        "auxiliar administrativo", "diseñador grafico"]

# Registro de estrategias: agregar una fuente nueva (p. ej. el MCP de Magneto en la Fase 3) es agregar una línea.
FUENTES: dict[str, Callable[[dict], FuenteVacantes]] = {
    "fixture": lambda opciones: FuenteFixture(RUTA_FIXTURE),
    "magneto": lambda opciones: FuenteMagnetoDetalle(opciones["terminos"], opciones["por_termino"]),
}


class Command(BaseCommand):
    help = "Ingiere vacantes (texto completo + requisitos) desde una fuente. Solo reescribe las que cambiaron."

    def add_arguments(self, parser):
        parser.add_argument("--fuente", choices=sorted(FUENTES), default="fixture")
        parser.add_argument("--terminos", nargs="+", default=TERMINOS_POR_DEFECTO)
        parser.add_argument("--por-termino", type=int, default=5)

    def handle(self, *args, fuente, **opciones):
        self.stdout.write(str(ingerir(FUENTES[fuente](opciones))))
