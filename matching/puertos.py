"""Puertos (Adapter + Ports) de los modelos de IA. El decisor solo conoce estas interfaces; los adaptadores reales
(fastembed) y los falsos de los tests las implementan."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dimension: int
    modelo: str  # nombre del modelo; entra en las firmas para re-embeber si cambia

    def embeber(self, textos: list[str]) -> np.ndarray:
        """Matriz float32 de forma (len(textos), dimension) con filas normalizadas (norma L2 = 1)."""
        ...


@dataclass(frozen=True)
class ModelosEmbebido:
    """Los dos modelos viajan juntos (spec §13.6): el de búsqueda da el vector de la preselección y el de cobertura las
    matrices requisito × evidencia. Un parámetro obligatorio evita llamar con uno solo y mezclar espacios."""

    busqueda: Embedder
    cobertura: Embedder

    @property
    def firma(self) -> str:
        """Qué modelos produjeron vector y matriz: si cambia alguno, hay que volver a embeber."""
        return f"{self.busqueda.modelo}|{self.cobertura.modelo}"


class Redactor(Protocol):
    def redactar(self, insumos: dict) -> str | None:
        """Una explicación en prosa de la decisión, o None si no se pudo (el llamador usa un texto de respaldo)."""
        ...


class Reordenador(Protocol):
    def puntuar(self, consulta: str, documentos: list[str]) -> list[float]:
        """Un puntaje por documento: más alto = más relevante para la consulta."""
        ...
