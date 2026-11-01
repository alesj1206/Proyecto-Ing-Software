"""Fuente a partir del fixture JSON de v2 (vacantes reales de Magneto, con la descripción recortada)."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from . import VacanteCruda


class FuenteFixture:
    nombre = "fixture"

    def __init__(self, ruta: Path):
        self.ruta = ruta

    def obtener(self) -> Iterator[VacanteCruda]:
        for registro in json.loads(self.ruta.read_text(encoding="utf-8")):
            salario = registro.get("salario") or {}
            yield VacanteCruda(
                id=registro["id"],
                titulo=registro["titulo"].strip(),
                empresa=registro["empresa"],
                ubicacion=registro["ubicacion"],
                modalidad=registro.get("modalidad", ""),
                texto_completo=registro.get("descripcion", ""),
                etiquetas=tuple(registro.get("requisitos", [])),
                url=registro.get("url", ""),
                fecha_publicacion=date.fromisoformat(registro["fechaPublicacion"]),
                salario_min=salario.get("min"),
                salario_max=salario.get("max"),
                urgente=registro.get("urgente", False),
            )
