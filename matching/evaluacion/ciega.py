"""Evaluación ciega con reclutadores (spec §13.3). Por cada CV ficticio, dos preguntas sin decir qué es cada opción:
¿qué lista de vacantes le recomendarías (Plan de hoy del decisor contra top por similitud pura)? y ¿qué CV pasaría tu
primer filtro (el original contra el que agrega las sugerencias del Taller)? La clave (qué es A/B y 1/2) se sortea con
una semilla y se guarda fuera del repo para que nadie del equipo la vea antes de tabular."""

import random
from collections import defaultdict
from dataclasses import dataclass, field

from django.utils import timezone

from matching.models import Decision
from matching.politica import POLITICA, Accion
from matching.preseleccion import preseleccionar
from matching.selectors import plan_de_hoy
from matching.services import decidir_para_perfil
from matching.taller import responder, taller, texto_adaptado
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


def asignar(claves: list[str], semilla: int) -> dict[str, dict]:
    azar = random.Random(semilla)
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


def preparar(escenario, cvs: dict[str, dict], claves: list[str], embedder, semilla: int) -> tuple[list[Paquete], dict]:
    sorteo, paquetes, clave = asignar(claves, semilla), [], {}
    hoy = timezone.localdate()
    for numero, nombre in enumerate(claves, 1):
        perfil = escenario.perfiles[nombre]
        decidir_para_perfil(perfil, embedder)
        por_origen = {
            "decisor": [_rotulo(item.vacante) for item in plan_de_hoy(perfil, TAMANO_LISTA, hoy)],
            "similitud": [_rotulo(v) for v in Vacante.objects.filter(id__in=[i for i, _ in preseleccionar(
                perfil, POLITICA.tau_relevancia).relevantes[:TAMANO_LISTA]])]}
        asignacion = sorteo[nombre]
        paquete = Paquete(numero, texto_cv(cvs[nombre]),
                          {letra: por_origen[origen] for letra, origen in asignacion["listas"].items()})
        objetivo = (Decision.objects.filter(perfil=perfil, accion=Accion.AJUSTAR_CV).select_related("vacante")
                    .order_by("-orden").first())
        if objetivo:
            for sugerencia in taller(perfil, objetivo.vacante):
                responder(sugerencia, True)
            original = paquete.cv
            adaptado = f"{original}\nPerfil para esta vacante:\n{texto_adaptado(perfil, objetivo.vacante)}"
            textos = {"original": original, "adaptado": adaptado}
            paquete.vacante_objetivo = _rotulo(objetivo.vacante)
            paquete.cvs = {n: textos[origen] for n, origen in asignacion["cvs"].items()}
        paquetes.append(paquete)
        clave[str(numero)] = {"cv": nombre, **asignacion}
    return paquetes, clave


def tabular(filas: list[dict], clave: dict) -> dict:
    """% de veces que se eligió la opción del decisor (pregunta "lista") y el CV con sugerencias (pregunta "cv")."""
    favorable = {"lista": "decisor", "cv": "adaptado"}
    conteo = {p: defaultdict(lambda: [0, 0]) for p in favorable}
    for fila in filas:
        pregunta = fila["pregunta"].strip()
        campo = "listas" if pregunta == "lista" else "cvs"
        origen = clave[fila["paquete"].strip()][campo][fila["eleccion"].strip()]
        for quien in ("total", fila["reclutador"].strip()):
            conteo[pregunta][quien][0] += origen == favorable[pregunta]
            conteo[pregunta][quien][1] += 1
    resultado = {}
    for pregunta, por_quien in conteo.items():
        total = por_quien.get("total", [0, 0])
        resultado[pregunta] = {favorable[pregunta]: total[0] / total[1] if total[1] else 0.0, "n": total[1],
                               "por_reclutador": {q: a / n for q, (a, n) in por_quien.items() if q != "total"}}
    return resultado
