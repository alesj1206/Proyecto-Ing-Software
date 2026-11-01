"""Política de decisión (spec §5.3, §13.2) como Chain of Responsibility: reglas pequeñas en orden, gana la primera que
responde. Los umbrales viven en un solo objeto versionado (`Politica`) que se ajusta con el set de evaluación."""

from dataclasses import dataclass, field
from typing import Protocol

from django.db import models

from vacantes.extraccion import requisitos_insuficientes

from .cobertura import Cobertura
from .restricciones import ResultadoRestriccion


@dataclass(frozen=True)
class Politica:
    version: str = "2026-11-02.2"  # τ_alto 0,50 → 0,45 tras el barrido sobre la mitad de ajuste (docs/fase2/EVALUACION.md)
    tau_alto: float = 0.45
    tau_bajo: float = 0.40
    tau_relevancia: float = 0.40
    max_faltantes_descartar: int = 3
    cobertura_nota: float = 0.70
    factor_experiencia: float = 0.5
    max_palabras_herramienta: int = 4


POLITICA = Politica()


class Accion(models.TextChoices):
    POSTULAR = "POSTULAR", "Postular"
    AJUSTAR_CV = "AJUSTAR_CV", "Ajustar CV"
    CERRAR_BRECHA = "CERRAR_BRECHA", "Cerrar brecha"
    DESCARTAR = "DESCARTAR", "Descartar"
    SIN_DATOS = "SIN_DATOS", "Revísala tú"


@dataclass
class ContextoDecision:
    cobertura: Cobertura
    restricciones: list[ResultadoRestriccion]
    requisitos: list  # los extraídos (con .origen), para saber si la vacante es legible
    politica: Politica = POLITICA


@dataclass
class Veredicto:
    accion: str
    con_nota: str | None = None
    motivos: list[str] = field(default_factory=list)


class Regla(Protocol):
    def aplicar(self, contexto: ContextoDecision) -> Veredicto | None: ...


class DescartarPorRestriccion:
    def aplicar(self, contexto):
        violadas = [r.motivo for r in contexto.restricciones if r.estado == "no_cumple"]
        return Veredicto(Accion.DESCARTAR, motivos=violadas) if violadas else None


class SinDatos:
    def aplicar(self, contexto):
        if requisitos_insuficientes(contexto.requisitos):
            return Veredicto(Accion.SIN_DATOS, motivos=["La vacante no trae requisitos legibles: revísala tú"])
        return None


class DescartarPorFaltantes:
    def aplicar(self, contexto):
        n = len(contexto.cobertura.faltantes_obligatorios)
        if n >= contexto.politica.max_faltantes_descartar:
            return Veredicto(Accion.DESCARTAR, motivos=[f"Te faltan {n} requisitos obligatorios"])
        return None


class Postular:
    """Cubre todo lo obligatorio, o casi todo con un solo faltante corto (una herramienta): POSTULAR con nota."""

    def aplicar(self, contexto):
        c, p = contexto.cobertura, contexto.politica
        faltantes = c.faltantes_obligatorios
        motivo = [f"Cubres {c.obligatorios_cubiertos}/{c.obligatorios_total} obligatorios"]
        if not faltantes and not c.parciales_con_evidencia:
            return Veredicto(Accion.POSTULAR, motivos=motivo)
        if (len(faltantes) == 1 and c.porcentaje >= p.cobertura_nota * 100
                and len(faltantes[0].texto.split()) <= p.max_palabras_herramienta):
            return Veredicto(Accion.POSTULAR, f"Menciona que puedes aprender {faltantes[0].texto} rápido", motivo)
        return None


class AjustarCV:
    def aplicar(self, contexto):
        c = contexto.cobertura
        if c.faltantes_obligatorios or not c.parciales_con_evidencia:
            return None
        return Veredicto(Accion.AJUSTAR_CV, motivos=[f"Haz explícito «{r.texto}» (tu evidencia: «{r.evidencia}»)"
                                                      for r in c.parciales_con_evidencia])


class CerrarBrecha:
    def aplicar(self, contexto):
        faltantes = contexto.cobertura.faltantes_obligatorios
        return Veredicto(Accion.CERRAR_BRECHA, motivos=[f"Te falta: {r.texto}" for r in faltantes]) if faltantes else None


CADENA: list[Regla] = [DescartarPorRestriccion(), SinDatos(), DescartarPorFaltantes(), Postular(), AjustarCV(),
                       CerrarBrecha()]


def decidir(contexto: ContextoDecision) -> Veredicto:
    for regla in CADENA:
        if veredicto := regla.aplicar(contexto):
            return veredicto
    raise AssertionError("La cadena de reglas no cubrió el caso")  # CerrarBrecha cierra todo lo demás
