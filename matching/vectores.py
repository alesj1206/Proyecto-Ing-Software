"""Vectores de vacantes y perfiles. Solo se recalcula lo que cambió (hash), y la matriz se guarda como bytea float16
en la misma transacción que el vector (spec §13.1, P3 y P4)."""

import hashlib

import numpy as np
from django.db import transaction
from django.db.models import F, Q

from cuentas.models import Perfil
from vacantes.extraccion import nucleo
from vacantes.models import Vacante

from .puertos import Embedder


def a_bytes(matriz: np.ndarray) -> bytes:
    return np.asarray(matriz, dtype=np.float16).tobytes()


DIMENSIONES = (384, 768)  # MiniLM-L12 (búsqueda) y mpnet-base-v2 (cobertura)


def de_bytes(datos: bytes | memoryview | None, filas: int) -> np.ndarray | None:
    """La matriz guardada, de `filas` filas. La dimensión sale del tamaño, porque la búsqueda y la cobertura usan
    modelos distintos; solo se aceptan las de `DIMENSIONES`. None si el tamaño no corresponde (matriz vieja)."""
    valores = np.frombuffer(bytes(datos or b""), dtype=np.float16)
    if filas == 0:
        return np.zeros((0, 0), dtype=np.float32) if not len(valores) else None
    if len(valores) % filas or len(valores) // filas not in DIMENSIONES:
        return None
    return valores.reshape(filas, -1).astype(np.float32)


def _promedio_normalizado(filas: np.ndarray) -> np.ndarray | None:
    if not len(filas):
        return None
    v = filas.mean(axis=0)
    norma = np.linalg.norm(v)
    return v / norma if norma else None


def firma_modelos(embedder: Embedder, cobertura: Embedder | None) -> str:
    """Qué modelos produjeron vector y matriz: si cambia alguno, hay que volver a embeber."""
    busqueda = getattr(embedder, "modelo", "")
    return f"{busqueda}|{getattr(cobertura, 'modelo', '') if cobertura is not None else busqueda}"


def embeber_vacantes(embedder: Embedder, lote: int = 256, cobertura: Embedder | None = None) -> int:
    """Embebe las vacantes nuevas o cuyo contenido cambió desde la última vez. Devuelve cuántas. El vector (preselección)
    sale de `embedder`; la matriz de requisitos, de `cobertura` si se da (si no, del mismo `embedder`)."""
    modelos = firma_modelos(embedder, cobertura)
    pendientes = (Vacante.objects.exclude(Q(hash_embebido=F("hash_contenido")) & Q(modelos_embebido=modelos))
                  .prefetch_related("requisito_set").order_by("id"))
    total = 0
    ids = list(pendientes.values_list("id", flat=True))
    for inicio in range(0, len(ids), lote):
        vacantes = list(pendientes.filter(id__in=ids[inicio:inicio + lote]))
        textos, tramos, crudos = [], [], []
        for v in vacantes:
            requisitos = sorted(v.requisito_set.all(), key=lambda r: r.posicion)
            tramos.append((len(textos), len(crudos), [r.origen == "texto" for r in requisitos]))
            textos += [v.titulo] + [nucleo(r.texto) for r in requisitos]  # la experiencia, por su área
            crudos += [r.texto for r in requisitos]
        matriz = embedder.embeber(textos)
        # mpnet se midió sobre el texto completo del requisito (prueba_3); `nucleo` es el ajuste que necesitó MiniLM.
        matriz_cob = cobertura.embeber(crudos) if cobertura is not None else None
        for v, (desde, desde_cob, de_texto) in zip(vacantes, tramos):
            titulo, reqs = matriz[desde], matriz[desde + 1: desde + 1 + len(de_texto)]
            base = np.vstack([titulo[None, :], reqs[np.array(de_texto, dtype=bool)]]) if len(de_texto) else titulo[None, :]
            if matriz_cob is not None:
                reqs = matriz_cob[desde_cob: desde_cob + len(de_texto)]
            v.vector, v.matriz_requisitos, v.hash_embebido = _promedio_normalizado(base), a_bytes(reqs), v.hash_contenido
            v.modelos_embebido = modelos
        with transaction.atomic():
            Vacante.objects.bulk_update(vacantes, ["vector", "matriz_requisitos", "hash_embebido", "modelos_embebido"])
        total += len(vacantes)
    return total


def embeber_perfil(perfil: Perfil, embedder: Embedder, textos: list[str] | None = None,
                   cobertura: Embedder | None = None) -> bool:
    """Embebe la evidencia del perfil si cambió (o si cambió algún modelo). Devuelve si hizo algo. `textos` evita
    leerla dos veces. El vector sale de `embedder` y la matriz de `cobertura` si se da."""
    if textos is None:
        textos = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
    firma = hashlib.sha256("\n".join([firma_modelos(embedder, cobertura)] + textos).encode("utf-8")).hexdigest()
    if perfil.hash_embebido == firma:
        return False
    matriz = embedder.embeber(textos)
    matriz_cob = cobertura.embeber(textos) if cobertura is not None else matriz
    perfil.vector, perfil.matriz_evidencia, perfil.hash_embebido = (_promedio_normalizado(matriz), a_bytes(matriz_cob),
                                                                    firma)
    perfil.save(update_fields=["vector", "matriz_evidencia", "hash_embebido"])
    return True
