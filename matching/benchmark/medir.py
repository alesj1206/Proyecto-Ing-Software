"""Mediciones del benchmark y su informe. Cada cifra dice si se midió o se proyectó (spec §6)."""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

# etapa → (umbral de §6, segundos por unidad del umbral)
UMBRALES = {"carga_inicial_cpu_h": (8, 3600), "delta_diario_min": (15, 60), "decision_candidato_s": (5, 1),
            "decision_candidato_p50_s": (5, 1), "carga_masiva_min": (None, 60)}


@dataclass(frozen=True)
class Medicion:
    etapa: str
    n: int
    segundos: float
    tipo: Literal["medido", "proyectado"]
    nota: str = ""


@contextmanager
def cronometro():
    tiempos = {}
    inicio = time.perf_counter()
    yield tiempos
    tiempos["s"] = time.perf_counter() - inicio


def _valor(m: Medicion) -> tuple[float, str]:
    umbral, por_unidad = UMBRALES.get(m.etapa, (None, 1))  # carga_masiva no tiene umbral en §6: se informa
    valor = m.segundos / por_unidad
    if umbral is None:
        return valor, "—"
    return valor, "sí" if valor <= umbral else "no"


def informe_markdown(mediciones: list[Medicion], contexto: dict[str, str]) -> str:
    lineas = ["# Benchmark de escala (spec §6)", "", *(f"- **{k}:** {v}" for k, v in contexto.items()), "",
              "| etapa | n | valor | umbral §6 | tipo | nota | cumple |", "|---|---:|---:|---:|---|---|---|"]
    for m in mediciones:
        valor, cumple = _valor(m)
        umbral = UMBRALES.get(m.etapa, (None,))[0]
        umbral = "—" if umbral is None else umbral
        lineas.append(f"| {m.etapa} | {m.n} | {valor:.2f} | {umbral} | {m.tipo} | {m.nota} | {cumple} |")
    return "\n".join(lineas) + "\n"
