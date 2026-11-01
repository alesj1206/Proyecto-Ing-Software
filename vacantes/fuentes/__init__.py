"""Puerto de las fuentes de vacantes (Strategy): la ingesta no sabe de dónde vienen."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class VacanteCruda:
    id: str
    titulo: str
    empresa: str
    ubicacion: str
    modalidad: str  # "" si la fuente no la dice; la ingesta la busca en el texto
    texto_completo: str
    etiquetas: tuple[str, ...]
    url: str
    fecha_publicacion: date
    salario_min: int | None = None  # solo si la fuente lo trae estructurado
    salario_max: int | None = None
    urgente: bool = False
    prefiltro: tuple[str, ...] = ()  # preguntas de la empresa (solo las trae el MCP de Magneto, B1)


class FuenteVacantes(Protocol):
    nombre: str

    def obtener(self) -> Iterable[VacanteCruda]: ...
