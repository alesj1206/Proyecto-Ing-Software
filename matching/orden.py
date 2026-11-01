"""Orden dentro de cada acción (Strategy, spec §13.1 P1-b): similitud × cobertura por defecto; con el reranker
encendido (GPU), se reordena solo la primera página de POSTULAR y AJUSTAR_CV (D5)."""

from typing import Protocol

from .politica import Accion
from .puertos import Reordenador

PAGINA = 20
EVIDENCIAS_EN_CONSULTA = 10
REQUISITOS_EN_DOCUMENTO = 8


class Ordenador(Protocol):
    def ordenar(self, perfil, decisiones: list) -> None:
        """Escribe `orden` (y `relevancia` si aplica) en cada decisión, sin guardar."""
        ...


class OrdenSimilitudCobertura:
    def ordenar(self, perfil, decisiones):
        for d in decisiones:
            d.orden = d.similitud * d.cobertura_pct / 100


class OrdenConReranker:
    def __init__(self, reordenador: Reordenador, base: Ordenador | None = None):
        self.reordenador, self.base = reordenador, base or OrdenSimilitudCobertura()

    def ordenar(self, perfil, decisiones):
        self.base.ordenar(perfil, decisiones)
        evidencias = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
        consulta = " ".join(evidencias[:EVIDENCIAS_EN_CONSULTA])
        for accion in (Accion.POSTULAR, Accion.AJUSTAR_CV):
            pagina = sorted((d for d in decisiones if d.accion == accion), key=lambda d: -d.orden)[:PAGINA]
            if not pagina:
                continue
            documentos = [" ".join([d.vacante.titulo, *d.vacante.requisitos[:REQUISITOS_EN_DOCUMENTO]]) for d in pagina]
            puntajes = self.reordenador.puntuar(consulta, documentos)
            ordenes = sorted((d.orden for d in pagina), reverse=True)  # la página conserva sus posiciones globales
            for d, puntaje in zip(pagina, puntajes):
                d.relevancia = puntaje
            for d, orden in zip(sorted(pagina, key=lambda d: -d.relevancia), ordenes):
                d.orden = orden
