"""Restricciones duras como Strategy (spec §5.2.5): cada una evalúa un criterio y explica su resultado. `sin_datos`
nunca descarta: solo baja la solidez (un candidato que no declaró algo no puede violarlo)."""

from dataclasses import dataclass
from typing import Protocol

from vacantes.extraccion import normalizar

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

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion: ...


def _pesos(valor: int) -> str:
    return f"$ {valor:,.0f}".replace(",", ".")


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
            return ResultadoRestriccion(self.criterio, "no_cumple", f"Ofrece {_pesos(vacante.salario_max)} y tu "
                                                                    f"mínimo es {_pesos(perfil.exp_salario_min)}")
        return ResultadoRestriccion(self.criterio, "cumple", f"Ofrece hasta {_pesos(vacante.salario_max)}")


class RestriccionUbicacion:
    criterio = "ubicacion"

    def evaluar(self, perfil, vacante, politica) -> ResultadoRestriccion:
        if vacante.modalidad == "Remoto" and not getattr(vacante, "modalidad_inferida", False):
            return ResultadoRestriccion(self.criterio, "cumple", "Es remota")
        if not perfil.exp_ubicacion:
            return ResultadoRestriccion(self.criterio, "sin_datos", "No declaraste dónde quieres trabajar")
        lugar = normalizar(vacante.ubicacion)
        ciudades = [normalizar(c) for c in perfil.exp_ubicacion.split(",") if normalizar(c)]
        if any(c in lugar for c in ciudades):
            return ResultadoRestriccion(self.criterio, "cumple", f"Queda en {vacante.ubicacion}")
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


RESTRICCIONES: list[Restriccion] = [RestriccionModalidad(), RestriccionSalario(), RestriccionUbicacion(),
                                    RestriccionExperiencia()]
