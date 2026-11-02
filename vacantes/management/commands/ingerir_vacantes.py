from collections.abc import Callable
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from vacantes.fuentes import FuenteVacantes
from vacantes.fuentes.fixture import FuenteFixture
from vacantes.fuentes.magneto_detalle import TERMINOS_POR_DEFECTO, FuenteMagnetoDetalle
from vacantes.models import Vacante
from vacantes.services import ingerir

RUTA_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "vacantes_magneto.json"

def _ya_cargadas() -> frozenset[str]:
    """Ids numéricos de Magneto de las vacantes ya guardadas."""
    ids = Vacante.objects.filter(id__startswith="mag-").values_list("id", flat=True)
    return frozenset(i.removeprefix("mag-") for i in ids)


# Registro de estrategias: agregar una fuente nueva (p. ej. el MCP de Magneto en la Fase 3) es agregar una línea.
def _fuente_mcp(opciones: dict) -> FuenteVacantes:
    """B1: apagado hasta que el equipo revise los términos de uso de Magneto."""
    if not settings.SCOUTLY_MAGNETO_MCP:
        raise CommandError("La fuente magneto-mcp está apagada: activa SCOUTLY_MAGNETO_MCP solo después de revisar "
                           "los términos de uso de Magneto.")
    from cuentas.models import Usuario
    from cuentas.oauth_magneto import leer_token
    from vacantes.fuentes.magneto_mcp import ClienteMCPHttp, FuenteMagnetoMCP

    usuario = Usuario.objects.filter(email=opciones.get("usuario") or "").first()
    token = leer_token(usuario) if usuario else None
    if not token:
        raise CommandError("Indica con --usuario un candidato que haya conectado su cuenta de Magneto.")
    return FuenteMagnetoMCP(ClienteMCPHttp(token), opciones.get("ids") or [])


FUENTES: dict[str, Callable[[dict], FuenteVacantes]] = {
    "fixture": lambda opciones: FuenteFixture(RUTA_FIXTURE),
    "magneto": lambda opciones: FuenteMagnetoDetalle(opciones["terminos"], opciones["por_termino"],
                                                     omitir=_ya_cargadas() if opciones.get("solo_nuevas") else frozenset()),
    "magneto-mcp": _fuente_mcp,
}


class Command(BaseCommand):
    help = "Ingiere vacantes (texto completo + requisitos) desde una fuente. Solo reescribe las que cambiaron."

    def add_arguments(self, parser):
        parser.add_argument("--fuente", choices=sorted(FUENTES), default="fixture")
        parser.add_argument("--terminos", nargs="+", default=TERMINOS_POR_DEFECTO)
        parser.add_argument("--por-termino", type=int, default=5)
        parser.add_argument("--solo-nuevas", action="store_true",
                            help="magneto: no abre las vacantes ya guardadas (para cargar mucho o retomar una carga)")
        parser.add_argument("--ids", nargs="+", help="magneto-mcp: ids numéricos de las vacantes")
        parser.add_argument("--usuario", help="magneto-mcp: correo del candidato cuyo token se usa")

    def handle(self, *args, fuente, **opciones):
        self.stdout.write(str(ingerir(FUENTES[fuente](opciones))))
