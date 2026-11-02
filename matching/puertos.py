"""Puertos (Adapter + Ports) de los modelos de IA. El decisor solo conoce estas interfaces; los adaptadores reales
(fastembed) y los falsos de los tests las implementan."""

from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dimension: int
    modelo: str  # nombre del modelo; entra en las firmas para re-embeber si cambia

    def embeber(self, textos: list[str]) -> np.ndarray:
        """Matriz float32 de forma (len(textos), dimension) con filas normalizadas (norma L2 = 1)."""
        ...


class Redactor(Protocol):
    def redactar(self, insumos: dict) -> str | None:
        """Una explicación en prosa de la decisión, o None si no se pudo (el llamador usa un texto de respaldo)."""
        ...


class Reordenador(Protocol):
    def puntuar(self, consulta: str, documentos: list[str]) -> list[float]:
        """Un puntaje por documento: más alto = más relevante para la consulta."""
        ...
