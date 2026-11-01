"""Preselección exacta en Postgres (spec §13.1, P2): entra toda vacante cuya similitud con el perfil supere τ, sin índice
aproximado (recall 100%). El tope técnico solo protege contra perfiles degenerados y se registra si se alcanza."""

import logging
from dataclasses import dataclass, field

from django.db.models import Q
from pgvector.django import CosineDistance

from cuentas.models import Perfil
from vacantes.models import Vacante

log = logging.getLogger(__name__)
TOPE_TECNICO = 5000
OPUESTA = {"Remoto": "Presencial", "Presencial": "Remoto"}


@dataclass
class Preseleccion:
    relevantes: list[tuple[str, float]] = field(default_factory=list)  # (id de vacante, similitud), descendente
    ocultas_por_modalidad: int = 0
    tope_alcanzado: bool = False


def preseleccionar(perfil: Perfil, tau: float, tope: int = TOPE_TECNICO) -> Preseleccion:
    if perfil.vector is None:
        return Preseleccion()
    candidatas = (Vacante.objects.filter(activa=True, vector__isnull=False)
                  .annotate(distancia=CosineDistance("vector", perfil.vector))
                  .filter(distancia__lte=1 - tau))
    ocultas = 0
    if opuesta := OPUESTA.get(perfil.exp_modalidad):  # solo si ambos lados declararon la modalidad
        es_opuesta = Q(modalidad=opuesta, modalidad_inferida=False)
        ocultas = candidatas.filter(es_opuesta).count()
        candidatas = candidatas.exclude(es_opuesta)
    filas = list(candidatas.order_by("distancia", "id").values_list("id", "distancia")[: tope + 1])
    tope_alcanzado = len(filas) > tope
    if tope_alcanzado:
        log.warning("Perfil %s alcanzó el tope técnico de %s vacantes relevantes", perfil.pk, tope)
    return Preseleccion([(i, 1 - float(d)) for i, d in filas[:tope]], ocultas, tope_alcanzado)
