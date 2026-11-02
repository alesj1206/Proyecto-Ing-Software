"""Fuente de vacantes sintéticas (un Strategy más de FuenteVacantes) armadas con piezas de vacantes reales: títulos,
ciudades, salarios y requisitos ya extraídos, recombinados con variaciones léxicas para que el número de textos
distintos se parezca al de un catálogo real. Reproducible con la semilla."""

import random
from collections.abc import Iterator
from datetime import date, timedelta

from vacantes.extraccion import extraer_requisitos
from vacantes.fuentes import VacanteCruda

CIUDADES = ("Bogotá, D.C.", "Medellín", "Cali", "Barranquilla", "Bucaramanga", "Cartagena", "Pereira", "Manizales",
            "Ibagué", "Neiva", "Santa Marta", "Villavicencio", "Cúcuta", "Pasto", "Montería", "Armenia")
NIVELES = ("", "Junior", "Senior", "I", "II", "III", "Líder", "Auxiliar")
MODALIDADES = ("Presencial", "Presencial", "Presencial", "Híbrido", "Remoto")
MIN_REQUISITOS_PLANTILLA = 4
PREFIJOS = ("", "", "Conocimiento en ", "Experiencia en ", "Manejo de ", "Dominio de ")
SUFIJOS = ("", "", "", " (deseable)", " avanzado", " intermedio")


class FuenteSintetica:
    nombre = "sintetica"

    def __init__(self, plantillas: list[dict], n: int, semilla: int = 0, desde: int = 0):
        self.n, self.semilla, self.desde = n, semilla, desde
        self.plantillas = []  # (título, requisitos) de cada vacante real con al menos 4 requisitos
        for p in plantillas:
            requisitos = sorted({r.texto for r in extraer_requisitos(p.get("descripcion", ""), []) if len(r.texto) < 160})
            if len(requisitos) >= MIN_REQUISITOS_PLANTILLA:
                self.plantillas.append((p["titulo"].split(" 16")[0].strip(), requisitos))
        self.requisitos_de = [r for _, r in self.plantillas]
        self.todos = sorted({r for reqs in self.requisitos_de for r in reqs})
        self.plantilla_de: dict[str, int] = {}

    def _vacante(self, i: int, azar: random.Random) -> VacanteCruda:
        indice = azar.randrange(len(self.plantillas))
        base, propios = self.plantillas[indice]
        self.plantilla_de[f"syn-{i}"] = indice
        titulo = " ".join(t for t in (base, azar.choice(NIVELES)) if t)
        ciudad = azar.choice(CIUDADES)
        elegidos = azar.sample(propios, azar.randint(MIN_REQUISITOS_PLANTILLA - 1, min(10, len(propios))))
        if azar.random() < 0.3:  # a veces un requisito de otra área, como en las vacantes reales mixtas
            elegidos.append(azar.choice(self.todos))
        requisitos = [f"{azar.choice(PREFIJOS)}{r[0].lower() + r[1:] if azar.random() < 0.3 else r}{azar.choice(SUFIJOS)}"
                      for r in elegidos]
        salario = azar.choice((None, *range(1_750_000, 9_000_001, 250_000)))
        texto = "\n".join([f"{titulo} - {ciudad}", "Requisitos:", *(f"- {r}" for r in requisitos)])
        return VacanteCruda(
            id=f"syn-{i}", titulo=f"{titulo} - {ciudad}", empresa=f"Empresa sintética {azar.randint(1, 4000)}",
            ubicacion=ciudad, modalidad=azar.choice(MODALIDADES), texto_completo=texto, etiquetas=(),
            url=f"https://ejemplo.invalid/vacante/{i}", fecha_publicacion=date(2026, 11, 1) - timedelta(days=i % 30),
            salario_min=salario, salario_max=salario)

    def obtener(self) -> Iterator[VacanteCruda]:
        for i in range(self.desde, self.desde + self.n):
            yield self._vacante(i, random.Random(self.semilla * 1_000_003 + i))  # cada vacante, independiente
