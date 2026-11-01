"""Puertos (Adapter + Ports) de los modelos de IA. El decisor solo conoce estas interfaces; los adaptadores reales
(fastembed) y los falsos de los tests las implementan."""

from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dimension: int

    def embeber(self, textos: list[str]) -> np.ndarray:
        """Matriz float32 de forma (len(textos), dimension) con filas normalizadas (norma L2 = 1)."""
        ...


class Reordenador(Protocol):
    def puntuar(self, consulta: str, documentos: list[str]) -> list[float]:
        """Un puntaje por documento: más alto = más relevante para la consulta."""
        ...
