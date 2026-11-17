"""Cobertura semántica: cada requisito contra la evidencia más parecida del CV (spec §5.2.4). La formación no se mide
por similitud (§13.2): que algo "se parezca" no prueba un título, y AJUSTAR_CV nunca debe sugerir inflar el CV."""

from dataclasses import dataclass, field

import re

import numpy as np

from vacantes.extraccion import normalizar

INICIOS_FORMACION = ("tecnico", "tecnologo", "profesional", "bachiller", "estudiante", "titulo", "formacion",
                     "carrera", "ingeniero")


# Palabras que no aportan contenido a un requisito de años ("Experiencia: mínimo 1–2 años comprobables").
_RELLENO_ANIOS = {"experiencia", "minimo", "minima", "de", "en", "al", "menos", "anos", "ano", "meses", "mes",
                  "comprobable", "comprobables", "certificable", "certificada", "laboral", "laborales", "y", "a", "o",
                  "como", "similar", "similares", "cargos", "relacionada", "relacionados"}


# Competencias blandas y condiciones (disponibilidad, documentos): casi nunca están en un CV y no se "cierran"
# estudiando, así que no cuentan como brecha. Se comparan por palabras clave sobre el texto normalizado.
PALABRAS_BLANDAS = ("trabajo en equipo", "disponibilidad", "aprendizaje", "actitud", "proactiv", "responsabilidad",
                    "compromiso", "etica", "valores", "adaptabilidad", "puntualidad", "atencion al detalle",
                    "orientacion al logro", "comunicacion asertiva", "comunicacion efectiva", "creatividad",
                    "liderazgo", "agilidad", "humanizacion", "resolucion de problemas", "trabajo bajo presion",
                    "vacunacion", "habilidades de comunicacion", "capacidad de aprendizaje", "empatia")


# Requisitos técnicos que contienen una palabra "blanda" (revisión final de la Fase 2).
EXCEPCIONES_TECNICAS = ("aprendizaje automatico", "aprendizaje de maquina", "aprendizaje profundo", "titulos valores",
                        "liderazgo tecnico")
_BLANDAS = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in PALABRAS_BLANDAS) + r")")


def es_blando(texto: str) -> bool:
    normal = normalizar(texto)
    return not any(e in normal for e in EXCEPCIONES_TECNICAS) and bool(_BLANDAS.search(normal))


def es_solo_anios(texto: str) -> bool:
    """Un requisito que solo pide tiempo de experiencia: lo evalúa la restricción de experiencia, no la similitud."""
    palabras = normalizar(texto).split()
    tiene_tiempo = any(p in ("ano", "anos", "mes", "meses") for p in palabras) and any(p.isdigit() for p in palabras)
    return tiene_tiempo and all(p.isdigit() or p in _RELLENO_ANIOS for p in palabras)


@dataclass(frozen=True)
class RequisitoEvaluado:
    texto: str
    tipo: str
    origen: str
    estado: str  # "cubierto" | "parcial" | "faltante" | "formacion" | "experiencia" | "blando"
    similitud: float
    evidencia: str | None

    @property
    def cuenta(self) -> bool:
        """Entra al porcentaje: obligatorio y medido por similitud (no formación ni años de experiencia)."""
        return self.tipo == "obligatorio" and self.estado not in ("formacion", "experiencia", "blando")


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
        # una habilidad blanda suelta del CV ("Liderazgo") no prueba un requisito técnico, igual que un requisito blando
        # no cuenta; una frase de experiencia que la menciona ("Lideré un equipo de 5 en SQL") sí sigue valiendo
        similitudes[:, [es_blando(e) and len(e.split()) <= 4 for e in evidencias]] = -1.0
        mejores, indices = similitudes.max(axis=1), similitudes.argmax(axis=1)
    else:
        mejores, indices = np.zeros(len(requisitos)), np.zeros(len(requisitos), dtype=int)
    evaluados = []
    for r, sim, j in zip(requisitos, mejores, indices):
        sim = float(sim)
        if es_formacion(r.texto):
            estado = "formacion"
        elif es_solo_anios(r.texto):
            estado = "experiencia"
        elif es_blando(r.texto):
            estado = "blando"
        elif sim >= tau_alto:
            estado = "cubierto"
        elif sim >= tau_bajo:
            estado = "parcial"
        else:
            estado = "faltante"
        evidencia = evidencias[j] if estado in ("cubierto", "parcial") else None
        evaluados.append(RequisitoEvaluado(r.texto, r.tipo, r.origen, estado, round(sim, 4), evidencia))
    return Cobertura(evaluados)
