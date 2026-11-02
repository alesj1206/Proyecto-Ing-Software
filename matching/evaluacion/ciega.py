"""Evaluación ciega con reclutadores (spec §13.3). Por cada CV ficticio, dos preguntas sin decir qué es cada opción:
¿qué lista de vacantes le recomendarías (Plan de hoy del decisor contra top por similitud pura)? y ¿qué CV pasaría tu
primer filtro (el original contra el que agrega las sugerencias del Taller)? La clave (qué es A/B y 1/2) se sortea con
una semilla y se guarda fuera del repo para que nadie del equipo la vea antes de tabular."""

import random
from collections import defaultdict
from dataclasses import dataclass, field

from django.utils import timezone

from matching.politica import POLITICA
from matching.preseleccion import preseleccionar
from matching.selectors import plan_de_hoy
from matching.services import decidir_para_perfil
from vacantes.models import Vacante

TAMANO_LISTA = 5
COLUMNAS = ("reclutador", "paquete", "pregunta", "eleccion")


@dataclass
class Paquete:
    numero: int
    cv: str
    listas: dict[str, list[str]]
    vacante_objetivo: str = ""
    cvs: dict[str, str] = field(default_factory=dict)

    def markdown(self) -> str:
        partes = [f"# Paquete {self.numero}", "", "## Candidato", "", self.cv, "",
                  "## Pregunta 1: ¿cuál lista le recomendarías a este candidato para enviar su hoja de vida esta semana?", ""]
        for letra in ("A", "B"):
            partes += [f"**Lista {letra}**", "", *(f"{i}. {v}" for i, v in enumerate(self.listas[letra], 1)), ""]
        if self.cvs:
            partes += ["## Pregunta 2: ¿cuál CV pasaría tu primer filtro para esta vacante?", "",
                       f"Vacante: {self.vacante_objetivo}", ""]
            for numero in ("1", "2"):
                partes += [f"**CV {numero}**", "", self.cvs[numero], ""]
        return "\n".join(partes)


def asignar(claves: list[str], semilla: int | None) -> dict[str, dict]:
    """Sin semilla (lo normal) el sorteo usa el azar del sistema: la clave no se puede recalcular desde el repositorio.
    La semilla solo existe para las pruebas."""
    azar = random.Random(semilla) if semilla is not None else random.SystemRandom()
    resultado = {}
    for clave in claves:
        a_decisor, uno_original = azar.random() < 0.5, azar.random() < 0.5
        resultado[clave] = {"listas": {"A": "decisor" if a_decisor else "similitud",
                                       "B": "similitud" if a_decisor else "decisor"},
                            "cvs": {"1": "original" if uno_original else "adaptado",
                                    "2": "adaptado" if uno_original else "original"}}
    return resultado


def texto_cv(cv: dict) -> str:
    """El CV ficticio sin nombre ni contacto: el reclutador juzga el contenido."""
    lineas = ["Experiencia:", *(f"- {e}" for e in cv.get("experiencia", []))]
    if cv.get("educacion"):
        lineas += ["Educación:", *(f"- {e}" for e in cv["educacion"])]
    if cv.get("habilidades"):
        lineas += [f"Habilidades: {cv['habilidades']}"]
    return "\n".join(lineas)


def _rotulo(vacante: Vacante) -> str:
    return f"{vacante.titulo} — {vacante.empresa} ({vacante.ubicacion})"


def preparar(escenario, cvs: dict[str, dict], claves: list[str], embedder,
             semilla: int | None, cobertura=None) -> tuple[list[Paquete], dict]:
    sorteo, paquetes, clave = asignar(claves, semilla), [], {}
    hoy = timezone.localdate()
    for numero, nombre in enumerate(claves, 1):
        perfil = escenario.perfiles[nombre]
        decidir_para_perfil(perfil, embedder, cobertura=cobertura)
        decisor = [_rotulo(item.vacante) for item in plan_de_hoy(perfil, TAMANO_LISTA, hoy)]
        ids = [i for i, _ in preseleccionar(perfil, POLITICA.tau_relevancia).relevantes[:TAMANO_LISTA]]
        por_id = Vacante.objects.in_bulk(ids)
        similitud = [_rotulo(por_id[i]) for i in ids]  # en orden de similitud, no en el orden por defecto del modelo
        largo = min(len(decisor), len(similitud))  # mismo largo: el tamaño de la lista no delata su origen
        por_origen = {"decisor": decisor[:largo], "similitud": similitud[:largo]}
        asignacion = sorteo[nombre]
        paquete = Paquete(numero, texto_cv(cvs[nombre]),
                          {letra: por_origen[origen] for letra, origen in asignacion["listas"].items()})
        # Con el Taller guiado (preguntas, sin texto propuesto) no hay un "CV con sugerencias" que el sistema pueda
        # escribir solo: la pregunta 2 queda para cuando haya respuestas reales de candidatos.
        paquetes.append(paquete)
        clave[str(numero)] = {"cv": nombre, "tiene_cv": bool(paquete.cvs), **asignacion}
    return paquetes, clave


def tabular(filas: list[dict], clave: dict) -> dict:
    """% de veces que se eligió la opción del decisor (pregunta "lista") y el CV con sugerencias (pregunta "cv").
    Las filas inválidas o repetidas no cuentan: se devuelven sus números de línea en el CSV (la 1 es la cabecera)."""
    favorable = {"lista": "decisor", "cv": "adaptado"}
    validas = {"lista": {"A", "B"}, "cv": {"1", "2"}}
    conteo = {p: defaultdict(lambda: [0, 0]) for p in favorable}
    vistos, errores = set(), []
    for numero, fila in enumerate(filas, 2):
        reclutador, paquete, pregunta, eleccion = ((fila.get(c) or "").strip() for c in COLUMNAS)
        eleccion = eleccion.upper()
        invalida = (not reclutador or reclutador == "total" or paquete not in clave
                    or eleccion not in validas.get(pregunta, ())
                    or (pregunta == "cv" and not clave[paquete].get("tiene_cv"))
                    or (reclutador, paquete, pregunta) in vistos)
        if invalida:
            errores.append(numero)
            continue
        vistos.add((reclutador, paquete, pregunta))
        origen = clave[paquete]["listas" if pregunta == "lista" else "cvs"][eleccion]
        for quien in ("total", reclutador):
            conteo[pregunta][quien][0] += origen == favorable[pregunta]
            conteo[pregunta][quien][1] += 1
    resultado = {}
    for pregunta, por_quien in conteo.items():
        total = por_quien.get("total", [0, 0])
        resultado[pregunta] = {favorable[pregunta]: total[0] / total[1] if total[1] else 0.0, "n": total[1],
                               "por_reclutador": {q: a / n for q, (a, n) in por_quien.items() if q != "total"}}
    resultado["errores"] = errores
    return resultado
