"""Preselección exacta en Postgres (spec §13.1, P2): entra toda vacante cuya similitud con el perfil supere τ, sin índice
aproximado (recall 100%), hasta las 3.000 más parecidas. Con MiniLM casi todo el catálogo supera τ (benchmark de la
Fase 4), así que a escala Magneto el que recorta es el tope: cada candidato recibe decisión sobre sus 3.000 vacantes
más parecidas, lo que asume §6 y mantiene la decisión por debajo de 5 s."""

import logging
from dataclasses import dataclass, field

from django.db.models import F, Q
from pgvector.django import CosineDistance

from cuentas.models import Perfil
from vacantes.models import Vacante

log = logging.getLogger(__name__)
TOPE_TECNICO = 3000
OPUESTA = {"Remoto": "Presencial", "Presencial": "Remoto"}


@dataclass
class Preseleccion:
    relevantes: list[tuple[str, float]] = field(default_factory=list)  # (id de vacante, similitud), descendente
    ocultas_por_modalidad: int = 0
    tope_alcanzado: bool = False


def preseleccionar(perfil: Perfil, tau: float, tope: int = TOPE_TECNICO, modelos: str | None = None) -> Preseleccion:
    """`modelos` (vectores.firma_modelos): si se da, solo entran vacantes embebidas con esos modelos."""
    if perfil.vector is None:
        return Preseleccion()
    # Solo vacantes con vectores al día: una re-ingesta posterior al embebido dejaría una matriz desalineada, y una
    # vacante todavía embebida con otro modelo mezclaría espacios distintos.
    al_dia = Vacante.objects.filter(activa=True, vector__isnull=False, hash_embebido=F("hash_contenido"))
    candidatas = ((al_dia.filter(modelos_embebido=modelos) if modelos is not None else al_dia)
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
        log.info("Perfil %s alcanzó el tope de %s vacantes relevantes", perfil.pk, tope)  # normal con catálogos grandes
    return Preseleccion([(i, 1 - float(d)) for i, d in filas[:tope]], ocultas, tope_alcanzado)
