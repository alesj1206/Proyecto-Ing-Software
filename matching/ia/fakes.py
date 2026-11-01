"""Modelos falsos y determinísticos para los tests: no descargan nada y se comportan de forma predecible."""

import hashlib
import re
import unicodedata

import numpy as np

DIMENSION_FALSA = 384  # igual a la columna halfvec, para poder guardar sus vectores


def _palabras(texto: str) -> list[str]:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return [p for p in re.findall(r"\w+", sin_acentos) if len(p) > 2]


class EmbedderFalso:
    """Bolsa de palabras con hashing: mismas palabras = mismo vector; sin palabras en común ≈ ortogonales."""

    def __init__(self, dimension: int = DIMENSION_FALSA):
        self.dimension = dimension

    def _vector(self, texto: str) -> np.ndarray:
        v = np.zeros(self.dimension, dtype=np.float32)
        for palabra in _palabras(texto):
            v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % self.dimension] += 1.0
        norma = np.linalg.norm(v)
        return v / norma if norma else v

    def embeber(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, self.dimension), dtype=np.float32)
        return np.vstack([self._vector(t) for t in textos])


class ReordenadorFalso:
    def puntuar(self, consulta: str, documentos: list[str]) -> list[float]:
        claves = set(_palabras(consulta))
        return [len(claves & set(_palabras(d))) / (len(claves) or 1) for d in documentos]
