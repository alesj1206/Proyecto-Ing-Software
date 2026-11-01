"""Set de evaluación del decisor (spec §10): CVs ficticios que pasan por el parser real, vacantes reales y pares
etiquetados. La mitad de ajuste calibra los umbrales; la de prueba se reserva para la Fase 4."""

import itertools
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import yaml

from cuentas.models import Perfil
from cuentas.services import crear_usuario_con_autorizacion, guardar_perfil_desde_cv
from cuentas.tests.cvs import pdf_cv
from vacantes.fuentes import FuenteVacantes
from vacantes.models import Vacante
from vacantes.services import ingerir

from ..politica import Politica
from ..puertos import Embedder
from ..services import decidir_par
from ..vectores import embeber_perfil, embeber_vacantes

MARGEN_LINEA_BASE = 0.10
NO_RELEVANTE = "DESCARTAR"  # una vacante bajo τ_relevancia no se le muestra al candidato: equivale a descartarla


@dataclass(frozen=True)
class Par:
    cv: str
    vacante: str
    accion_esperada: str
    justificacion: str
    mitad: str  # "ajuste" | "prueba"


@dataclass
class Escenario:
    perfiles: dict[str, Perfil]


@dataclass
class Informe:
    total: int = 0
    aciertos: int = 0
    aciertos_linea_base: int = 0
    distribucion: Counter = field(default_factory=Counter)
    confusion: Counter = field(default_factory=Counter)  # (esperada, predicha) -> n
    errores: list[str] = field(default_factory=list)

    @property
    def exactitud(self) -> float:
        return self.aciertos / self.total if self.total else 0.0

    @property
    def exactitud_linea_base(self) -> float:
        return self.aciertos_linea_base / self.total if self.total else 0.0


def cargar_pares(ruta: Path, mitad: str) -> list[Par]:
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    return [Par(**p) for p in datos["pares"] if p["mitad"] == mitad]


def preparar(cvs: dict[str, dict], fuente: FuenteVacantes, embedder: Embedder) -> Escenario:
    """Carga las vacantes y crea un perfil por CV pasando el PDF por el parser real, con su vector."""
    ingerir(fuente)
    embeber_vacantes(embedder)
    perfiles = {}
    for clave, cv in cvs.items():
        usuario = crear_usuario_con_autorizacion(f"eval-{clave}@correo-ficticio.co", None)
        pdf = pdf_cv(f"{clave}.pdf", nombre=cv["nombre"], contacto=cv.get("contacto"), experiencia=cv["experiencia"],
                     educacion=tuple(cv.get("educacion", ())), habilidades=cv.get("habilidades"))
        perfil = guardar_perfil_desde_cv(usuario, pdf)
        for campo, valor in cv.get("expectativas", {}).items():
            setattr(perfil, campo, valor)
        perfil.save()
        embeber_perfil(perfil, embedder)
        perfiles[clave] = perfil
    return Escenario(perfiles)


def linea_base(similitud: float, politica: Politica) -> str:
    """Lo que haría un ranking por similitud pura, sin cobertura ni restricciones ni política."""
    if similitud >= politica.tau_relevancia + MARGEN_LINEA_BASE:
        return "POSTULAR"
    return "CERRAR_BRECHA" if similitud >= politica.tau_relevancia else "DESCARTAR"


def predecir(escenario: Escenario, par: Par, politica: Politica) -> tuple[str, float]:
    perfil = escenario.perfiles[par.cv]
    vacante = Vacante.objects.prefetch_related("requisito_set").get(id=par.vacante)
    if perfil.vector is None or vacante.vector is None:
        return NO_RELEVANTE, 0.0
    similitud = float(np.dot(np.asarray(perfil.vector, np.float32), np.asarray(vacante.vector, np.float32)))
    if similitud < politica.tau_relevancia:
        return NO_RELEVANTE, similitud
    return str(decidir_par(perfil, vacante, similitud, politica).accion), similitud


def evaluar(escenario: Escenario, pares: list[Par], politica: Politica) -> Informe:
    informe = Informe()
    for par in pares:
        predicha, similitud = predecir(escenario, par, politica)
        informe.total += 1
        informe.aciertos += predicha == par.accion_esperada
        informe.aciertos_linea_base += linea_base(similitud, politica) == par.accion_esperada
        informe.distribucion[predicha] += 1
        informe.confusion[(par.accion_esperada, predicha)] += 1
        if predicha != par.accion_esperada:
            informe.errores.append(f"{par.cv} × {par.vacante}: esperada {par.accion_esperada}, "
                                   f"predicha {predicha} (similitud {similitud:.2f})")
    return informe


GRILLA = {"tau_alto": (0.45, 0.50, 0.55), "tau_bajo": (0.35, 0.40), "tau_relevancia": (0.35, 0.40, 0.45)}


def barrido(escenario: Escenario, pares: list[Par], base: Politica) -> list[tuple[Politica, Informe]]:
    """Todas las combinaciones de la grilla, de mejor a peor exactitud (solo sobre la mitad de ajuste)."""
    resultados = []
    for alto, bajo, relevancia in itertools.product(*GRILLA.values()):
        if bajo >= alto:
            continue
        politica = replace(base, tau_alto=alto, tau_bajo=bajo, tau_relevancia=relevancia)
        resultados.append((politica, evaluar(escenario, pares, politica)))
    return sorted(resultados, key=lambda r: (-r[1].exactitud, abs(r[0].tau_alto - base.tau_alto)))
