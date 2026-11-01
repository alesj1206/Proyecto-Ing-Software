"""Adaptadores de fastembed (ONNX, sin torch). Solo los importa el proceso batch."""

from pathlib import Path

import numpy as np

MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_RERANKER = "BAAI/bge-reranker-v2-m3"
CACHE_MODELOS = Path.home() / ".cache" / "scoutly-modelos"
LOTE = 64


def _proveedores(proveedor: str) -> list[str]:
    return ["CUDAExecutionProvider", "CPUExecutionProvider"] if proveedor == "cuda" else ["CPUExecutionProvider"]


class EmbedderFastembed:
    def __init__(self, modelo: str = MODELO_EMBEDDINGS, proveedor: str = "cpu"):
        from fastembed import TextEmbedding

        self._modelo = TextEmbedding(modelo, cache_dir=str(CACHE_MODELOS), providers=_proveedores(proveedor))
        self.dimension = int(self.embeber(["dimension"]).shape[1])

    def embeber(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, getattr(self, "dimension", 0)), dtype=np.float32)
        m = np.asarray(list(self._modelo.embed(textos, batch_size=LOTE)), dtype=np.float32)
        return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-12, None)


class ReordenadorFastembed:
    def __init__(self, modelo: str = MODELO_RERANKER, proveedor: str = "cuda"):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._modelo = TextCrossEncoder(modelo, cache_dir=str(CACHE_MODELOS), providers=_proveedores(proveedor))

    def puntuar(self, consulta: str, documentos: list[str]) -> list[float]:
        return [float(p) for p in self._modelo.rerank(consulta, documentos)] if documentos else []
