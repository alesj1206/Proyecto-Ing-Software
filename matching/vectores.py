"""Vectores de vacantes y perfiles. Solo se recalcula lo que cambió (hash), y la matriz se guarda como bytea float16
en la misma transacción que el vector (spec §13.1, P3 y P4)."""

import hashlib

import numpy as np
from django.conf import settings
from django.db import transaction
from django.db.models import F

from cuentas.models import Perfil
from vacantes.models import Vacante

from .puertos import Embedder


def a_bytes(matriz: np.ndarray) -> bytes:
    return np.asarray(matriz, dtype=np.float16).tobytes()


def de_bytes(datos: bytes | memoryview | None, dimension: int = settings.SCOUTLY_DIMENSION) -> np.ndarray:
    if not datos:
        return np.zeros((0, dimension), dtype=np.float32)
    return np.frombuffer(bytes(datos), dtype=np.float16).reshape(-1, dimension).astype(np.float32)


def _promedio_normalizado(filas: np.ndarray) -> np.ndarray | None:
    if not len(filas):
        return None
    v = filas.mean(axis=0)
    norma = np.linalg.norm(v)
    return v / norma if norma else None


def embeber_vacantes(embedder: Embedder, lote: int = 256) -> int:
    """Embebe las vacantes nuevas o cuyo contenido cambió desde la última vez. Devuelve cuántas."""
    pendientes = (Vacante.objects.exclude(hash_embebido=F("hash_contenido"))
                  .prefetch_related("requisito_set").order_by("id"))
    total = 0
    ids = list(pendientes.values_list("id", flat=True))
    for inicio in range(0, len(ids), lote):
        vacantes = list(pendientes.filter(id__in=ids[inicio:inicio + lote]))
        textos, tramos = [], []
        for v in vacantes:
            requisitos = sorted(v.requisito_set.all(), key=lambda r: r.posicion)
            tramos.append((len(textos), [r.origen == "texto" for r in requisitos]))
            textos += [v.titulo] + [r.texto for r in requisitos]
        matriz = embedder.embeber(textos)
        for v, (desde, de_texto) in zip(vacantes, tramos):
            titulo, reqs = matriz[desde], matriz[desde + 1: desde + 1 + len(de_texto)]
            base = np.vstack([titulo[None, :], reqs[np.array(de_texto, dtype=bool)]]) if len(de_texto) else titulo[None, :]
            v.vector, v.matriz_requisitos, v.hash_embebido = _promedio_normalizado(base), a_bytes(reqs), v.hash_contenido
        with transaction.atomic():
            Vacante.objects.bulk_update(vacantes, ["vector", "matriz_requisitos", "hash_embebido"])
        total += len(vacantes)
    return total


def embeber_perfil(perfil: Perfil, embedder: Embedder, textos: list[str] | None = None) -> bool:
    """Embebe la evidencia del perfil si cambió. Devuelve si hizo algo. `textos` evita leerla dos veces."""
    if textos is None:
        textos = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
    firma = hashlib.sha256("\n".join(textos).encode("utf-8")).hexdigest()
    if perfil.hash_embebido == firma:
        return False
    matriz = embedder.embeber(textos)
    perfil.vector, perfil.matriz_evidencia, perfil.hash_embebido = _promedio_normalizado(matriz), a_bytes(matriz), firma
    perfil.save(update_fields=["vector", "matriz_evidencia", "hash_embebido"])
    return True
