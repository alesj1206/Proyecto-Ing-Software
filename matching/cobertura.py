"""Cobertura semántica: cada requisito contra la evidencia más parecida del CV (spec §5.2.4). La formación no se mide
por similitud (§13.2): que algo "se parezca" no prueba un título, y AJUSTAR_CV nunca debe sugerir inflar el CV."""

from dataclasses import dataclass, field

import numpy as np

from vacantes.extraccion import normalizar

INICIOS_FORMACION = ("tecnico", "tecnologo", "profesional", "bachiller", "estudiante", "titulo", "formacion",
                     "carrera", "ingeniero")


@dataclass(frozen=True)
class RequisitoEvaluado:
    texto: str
    tipo: str
    origen: str
    estado: str  # "cubierto" | "parcial" | "faltante" | "formacion"
    similitud: float
    evidencia: str | None

    @property
    def cuenta(self) -> bool:
        """Entra al porcentaje: obligatorio y no de formación."""
        return self.tipo == "obligatorio" and self.estado != "formacion"


@dataclass
class Cobertura:
    requisitos: list[RequisitoEvaluado] = field(default_factory=list)

    def _contables(self, estado: str | None = None) -> list[RequisitoEvaluado]:
        return [r for r in self.requisitos if r.cuenta and (estado is None or r.estado == estado)]

    @property
    def obligatorios_total(self) -> int:
        return len(self._contables())

    @property
    def obligatorios_cubiertos(self) -> int:
        return len(self._contables("cubierto"))

    @property
    def faltantes_obligatorios(self) -> list[RequisitoEvaluado]:
        return self._contables("faltante")

    @property
    def parciales_con_evidencia(self) -> list[RequisitoEvaluado]:
        return [r for r in self._contables("parcial") if r.evidencia]

    @property
    def porcentaje(self) -> int:
        """(cubiertos + ½ parciales) / obligatorios, redondeado hacia arriba en .5 (lo que muestra el anillo)."""
        if not self.obligatorios_total:
            return 0
        puntos = self.obligatorios_cubiertos + 0.5 * len(self._contables("parcial"))
        return int(puntos / self.obligatorios_total * 100 + 0.5)


def es_formacion(texto: str) -> bool:
    return normalizar(texto).startswith(INICIOS_FORMACION)


def cubrir(requisitos, matriz_req: np.ndarray, evidencias: list[str], matriz_evid: np.ndarray,
           tau_alto: float, tau_bajo: float) -> Cobertura:
    if len(evidencias):
        similitudes = matriz_req @ matriz_evid.T
        mejores, indices = similitudes.max(axis=1), similitudes.argmax(axis=1)
    else:
        mejores, indices = np.zeros(len(requisitos)), np.zeros(len(requisitos), dtype=int)
    evaluados = []
    for r, sim, j in zip(requisitos, mejores, indices):
        sim = float(sim)
        if es_formacion(r.texto):
            estado = "formacion"
        elif sim >= tau_alto:
            estado = "cubierto"
        elif sim >= tau_bajo:
            estado = "parcial"
        else:
            estado = "faltante"
        evidencia = evidencias[j] if estado in ("cubierto", "parcial") else None
        evaluados.append(RequisitoEvaluado(r.texto, r.tipo, r.origen, estado, round(sim, 4), evidencia))
    return Cobertura(evaluados)
