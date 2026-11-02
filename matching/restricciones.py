"""Restricciones duras como Strategy (spec §5.2.5): cada una evalúa un criterio y explica su resultado. `sin_datos`
nunca descarta: solo baja la solidez (un candidato que no declaró algo no puede violarlo)."""

import re
from dataclasses import dataclass
from typing import Protocol

from vacantes.extraccion import normalizar

from .formato import pesos

VALOR_PCT = {"cumple": 100, "parcial": 50, "no_cumple": 0, "sin_datos": 0}
AFINIDAD_MODALIDAD = {  # la tabla de v2 (vacantes/matching.py del tag pre-sprint3-rebuild)
    ("Remoto", "Remoto"): 100, ("Presencial", "Presencial"): 100, ("Híbrido", "Híbrido"): 100,
    ("Híbrido", "Remoto"): 50, ("Remoto", "Híbrido"): 50, ("Híbrido", "Presencial"): 50,
    ("Presencial", "Híbrido"): 50, ("Remoto", "Presencial"): 0, ("Presencial", "Remoto"): 0,
}


@dataclass(frozen=True)
class ResultadoRestriccion:
    criterio: str
    estado: str  # "cumple" | "parcial" | "no_cumple" | "sin_datos"
    motivo: str

    @property
    def valor_pct(self) -> int:
        return VALOR_PCT[self.estado]


class Restriccion(Protocol):
    criterio: str

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion | None: ...  # None: no aplica


class RestriccionModalidad:
    criterio = "modalidad"

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion:
        if not perfil.exp_modalidad:
            return ResultadoRestriccion(self.criterio, "sin_datos", "No declaraste la modalidad que buscas")
        if vacante.modalidad_inferida:
            return ResultadoRestriccion(self.criterio, "sin_datos", "La vacante no dice su modalidad")
        afinidad = AFINIDAD_MODALIDAD.get((vacante.modalidad, perfil.exp_modalidad), 0)
        if afinidad == 100:
            return ResultadoRestriccion(self.criterio, "cumple", f"Es {vacante.modalidad.lower()}, como buscas")
        estado = "parcial" if afinidad == 50 else "no_cumple"
        return ResultadoRestriccion(self.criterio, estado,
                                    f"Es {vacante.modalidad.lower()} y buscas {perfil.exp_modalidad.lower()}")


class RestriccionSalario:
    criterio = "salario"

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion:
        if not perfil.exp_salario_min:
            return ResultadoRestriccion(self.criterio, "sin_datos", "No declaraste tu salario mínimo")
        if vacante.salario_max is None:
            return ResultadoRestriccion(self.criterio, "sin_datos", "La vacante no dice el salario")
        if vacante.salario_max < perfil.exp_salario_min:
            return ResultadoRestriccion(self.criterio, "no_cumple", f"Ofrece {pesos(vacante.salario_max)} y tu "
                                                                    f"mínimo es {pesos(perfil.exp_salario_min)}")
        return ResultadoRestriccion(self.criterio, "cumple", f"Ofrece hasta {pesos(vacante.salario_max)}")


# Municipios conurbados con la ciudad núcleo (áreas metropolitanas formales). Quien busca la ciudad núcleo acepta
# su área; no al revés (quien busca Envigado no necesariamente quiere ir a Bello).
AREAS_METROPOLITANAS = {
    "medellin": ("bello", "itagui", "envigado", "sabaneta", "la estrella", "caldas", "copacabana", "girardota", "barbosa"),
    "bogota": ("soacha",),
    "barranquilla": ("soledad", "malambo", "puerto colombia", "galapa"),
    "bucaramanga": ("floridablanca", "giron", "piedecuesta"),
    "cali": ("jamundi", "yumbo"),
}


def _con_area(ciudad: str) -> tuple[str, ...]:
    return (ciudad, *AREAS_METROPOLITANAS.get(ciudad, ()))


class RestriccionUbicacion:
    criterio = "ubicacion"

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion:
        if vacante.modalidad == "Remoto" and not getattr(vacante, "modalidad_inferida", False):
            return ResultadoRestriccion(self.criterio, "cumple", "Es remota")
        if not perfil.exp_ubicacion:
            return ResultadoRestriccion(self.criterio, "sin_datos", "No declaraste dónde quieres trabajar")
        if normalizar(vacante.ubicacion) in ("", "colombia"):  # "Colombia" era el relleno de la Fase 1
            return ResultadoRestriccion(self.criterio, "sin_datos", "La vacante no dice dónde queda")
        lugar = normalizar(vacante.ubicacion)
        ciudades = [normalizar(c) for c in perfil.exp_ubicacion.split(",") if normalizar(c)]
        if any(c in lugar for c in ciudades):
            return ResultadoRestriccion(self.criterio, "cumple", f"Queda en {vacante.ubicacion}")
        nombres = [c.strip() for c in perfil.exp_ubicacion.split(",") if normalizar(c)]
        if area := next((n for n in nombres if any(m in lugar for m in _con_area(normalizar(n)))), None):
            return ResultadoRestriccion(self.criterio, "cumple", f"Queda en {vacante.ubicacion}, en el área "
                                                                 f"metropolitana de {area}")
        return ResultadoRestriccion(self.criterio, "no_cumple",
                                    f"Queda en {vacante.ubicacion}, fuera de {perfil.exp_ubicacion}")


class RestriccionExperiencia:
    """Calibración inicial (D3): pedir 1 año o menos nunca descarta; con 2 o más, descarta si tiene menos de la mitad."""

    criterio = "experiencia"

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion:
        pide, tiene = vacante.experiencia_minima, perfil.anios_experiencia
        if not pide:
            return ResultadoRestriccion(self.criterio, "cumple", "No pide experiencia mínima")
        if tiene is None:
            return ResultadoRestriccion(self.criterio, "sin_datos", "No declaraste tus años de experiencia")
        motivo = f"Pide {pide} {'año' if pide == 1 else 'años'} de experiencia y declaraste {tiene}"
        if tiene >= pide:
            return ResultadoRestriccion(self.criterio, "cumple", motivo)
        if pide >= 2 and tiene < politica.factor_experiencia * pide:
            return ResultadoRestriccion(self.criterio, "no_cumple", motivo)
        return ResultadoRestriccion(self.criterio, "parcial", motivo)


class RestriccionEstudiante:
    """Las prácticas y los contratos de aprendizaje exigen ser estudiante: no basta con haber estudiado el área.
    Solo aplica a esas vacantes (devuelve None en las demás, así no agrega una fila a cada decisión). "Técnico,
    tecnólogo o estudiante de…" no la activa: ahí ser estudiante es una alternativa, no una exigencia."""

    criterio = "estudiante"
    TITULO = re.compile(r"\b(practicante|practica|practicas|aprendiz|pasante|pasantia)\b")
    DESCRIPCION = re.compile(r"\bcontrato de aprendizaje\b")
    EN_CURSO = re.compile(r"\b(en curso|cursando|actualmente|actual|a la fecha|presente|semestre)\b")
    MOTIVO_NO = "La vacante es para estudiantes y tu CV no muestra estudios en curso"

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion | None:
        if not (self.TITULO.search(normalizar(vacante.titulo))
                or self.DESCRIPCION.search(normalizar(vacante.descripcion or ""))):
            return None
        educacion = perfil.evidencias.filter(seccion="educacion").values_list("texto", flat=True)
        if any(self.EN_CURSO.search(normalizar(t)) for t in educacion):
            return ResultadoRestriccion(self.criterio, "cumple", "Tu CV muestra estudios en curso")
        return ResultadoRestriccion(self.criterio, "no_cumple", self.MOTIVO_NO)


RESTRICCIONES: list[Restriccion] = [RestriccionModalidad(), RestriccionSalario(), RestriccionUbicacion(),
                                    RestriccionExperiencia(), RestriccionEstudiante()]
