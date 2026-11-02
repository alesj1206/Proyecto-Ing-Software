"""Vectores de vacantes y perfiles. Solo se recalcula lo que cambió (hash), y la matriz se guarda como bytea float16
en la misma transacción que el vector (spec §13.1, P3 y P4)."""

import hashlib

import numpy as np
from django.db import transaction
from django.db.models import F, Q

from cuentas.models import Perfil
from vacantes.extraccion import nucleo
from vacantes.models import Vacante

from . import candados
from .candados import candado_de_aviso
from .puertos import Embedder, ModelosEmbebido


def a_bytes(matriz: np.ndarray) -> bytes:
    return np.asarray(matriz, dtype=np.float16).tobytes()


def de_bytes(datos: bytes | memoryview | None, filas: int, dimension: int | None = None) -> np.ndarray | None:
    """La matriz guardada, de `filas` filas. None si el tamaño no corresponde (matriz vieja). Si se conoce la `dimension`
    esperada se exige: 2×384 y 1×768 ocupan los mismos bytes. Si no, se deduce del tamaño."""
    valores = np.frombuffer(bytes(datos or b""), dtype=np.float16)
    if filas == 0:
        return np.zeros((0, dimension or 0), dtype=np.float32) if not len(valores) else None
    if not len(valores) or len(valores) % filas or (dimension is not None and len(valores) != filas * dimension):
        return None
    return valores.reshape(filas, -1).astype(np.float32)


def _promedio_normalizado(filas: np.ndarray) -> np.ndarray | None:
    if not len(filas):
        return None
    v = filas.mean(axis=0)
    norma = np.linalg.norm(v)
    return v / norma if norma else None


def _embeber_distintos(embedder: Embedder, textos: list[str]) -> np.ndarray:
    """Como `embedder.embeber`, pero cada texto distinto pasa por el modelo una sola vez: los requisitos y las etiquetas
    se repiten mucho entre vacantes, y el modelo es lo más caro de la ingesta."""
    distintos = list(dict.fromkeys(textos))
    matriz = embedder.embeber(distintos)
    posicion = {t: i for i, t in enumerate(distintos)}
    return matriz[[posicion[t] for t in textos]] if textos else matriz


def embeber_vacantes(modelos: ModelosEmbebido, lote: int = 256, esperar: bool = True) -> int | None:
    """Embebe las vacantes nuevas, las que cambiaron de contenido y las embebidas con otros modelos. Devuelve cuántas.
    El vector (preselección) sale del modelo de búsqueda; la matriz de requisitos, del de cobertura.

    Un solo proceso embebe a la vez (candado de aviso). Con `esperar=False` (los que escuchan la cola), si otro ya está
    embebiendo, devuelve None sin hacer nada; las vacantes a medio embeber no entran a la preselección y conservan su
    decisión anterior (services._con_vectores_viejos)."""
    with candado_de_aviso(candados.EMBEBIDO, esperar) as tomado:
        return _embeber_vacantes(modelos, lote) if tomado else None


def _embeber_vacantes(modelos: ModelosEmbebido, lote: int) -> int:
    firma = modelos.firma
    pendientes = (Vacante.objects.exclude(Q(hash_embebido=F("hash_contenido")) & Q(modelos_embebido=firma))
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
        matriz = _embeber_distintos(modelos.busqueda, textos)
        # La cobertura se mide sobre el texto completo del requisito, como se midió mpnet en prueba_3; `nucleo` es el
        # ajuste que necesitó MiniLM y solo entra al vector de la preselección.
        matriz_cob = _embeber_distintos(modelos.cobertura, crudos)
        for v, (desde, desde_cob, de_texto) in zip(vacantes, tramos):
            titulo, reqs = matriz[desde], matriz[desde + 1: desde + 1 + len(de_texto)]
            base = np.vstack([titulo[None, :], reqs[np.array(de_texto, dtype=bool)]]) if len(de_texto) else titulo[None, :]
            v.vector, v.hash_embebido, v.modelos_embebido = _promedio_normalizado(base), v.hash_contenido, firma
            v.matriz_requisitos = a_bytes(matriz_cob[desde_cob: desde_cob + len(de_texto)])
        with transaction.atomic():
            Vacante.objects.bulk_update(vacantes, ["vector", "matriz_requisitos", "hash_embebido", "modelos_embebido"])
        total += len(vacantes)
    return total


def embeber_perfil(perfil: Perfil, modelos: ModelosEmbebido, textos: list[str] | None = None) -> bool:
    """Embebe la evidencia del perfil si cambió (o si cambió algún modelo). Devuelve si hizo algo. `textos` evita
    leerla dos veces. El vector sale del modelo de búsqueda y la matriz del de cobertura."""
    if textos is None:
        textos = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
    firma = hashlib.sha256("\n".join([modelos.firma] + textos).encode("utf-8")).hexdigest()
    if perfil.hash_embebido == firma:
        return False
    vector = _promedio_normalizado(modelos.busqueda.embeber(textos))
    perfil.vector, perfil.matriz_evidencia, perfil.hash_embebido = vector, a_bytes(modelos.cobertura.embeber(textos)), firma
    perfil.save(update_fields=["vector", "matriz_evidencia", "hash_embebido"])
    return True
