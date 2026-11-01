"""Textos sintéticos en español con forma de vacante y de CV, para medir
rendimiento a escala sin depender del scraping real."""

import json
import random
from functools import cache
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "vacantes" / "fixtures" / "vacantes_magneto.json"

INDUSTRIAS = {
    "tecnología": ["Python", "Java con Spring Boot", "React", "Node.js", "SQL Server", "Docker", "AWS", "Git", "APIs REST", "pruebas automatizadas"],
    "contabilidad": ["NIIF", "conciliaciones bancarias", "SAP FI", "Excel avanzado", "declaraciones tributarias", "nómina", "cuentas por pagar"],
    "comercial": ["gestión de cartera", "prospección de clientes", "CRM Salesforce", "negociación", "cumplimiento de metas de ventas", "atención al cliente"],
    "salud": ["enfermería", "manejo de historias clínicas", "toma de muestras", "protocolos de bioseguridad", "atención de urgencias", "farmacovigilancia"],
    "logística": ["control de inventarios", "WMS", "despacho de mercancía", "montacargas", "rutas de distribución", "comercio exterior"],
    "diseño": ["Figma", "Adobe Illustrator", "Photoshop", "diseño de interfaces", "identidad de marca", "edición de video"],
}

PLANTILLAS_REQUISITO = [
    "Experiencia mínima de {anios} años en {h1}",
    "Conocimiento en {h1} y {h2}",
    "Manejo de {h1}, deseable {h2}",
    "Formación {nivel} en áreas afines a {area} con énfasis en {h1}",
    "Disponibilidad para aprender {h2} y aplicar {h1} en el día a día",
    "Al menos {anios} años usando {h2} en procesos de {area}",
    "Experiencia comprobada en {h1} dentro del sector {area}",
    "Dominio de {h1} para el apoyo de procesos de {area}",
    "Capacidad para liderar procesos de {h1} y reportar indicadores",
    "Se valora experiencia previa en {h2} y {h1}",
]

PLANTILLAS_EVIDENCIA = [
    "Trabajé {anios} años en {h1} para una empresa del sector {area}",
    "Lideré proyectos de {h1} integrando {h2}",
    "Responsable de {h1} y de reportes semanales a la gerencia",
    "Apoyé al equipo de {area} en tareas de {h1} y {h2}",
    "Certificación en {h1} obtenida en {anio}",
    "Implementé mejoras en {h1} que redujeron tiempos del área de {area}",
]

CONECTORES = ["Funciones:", "Requisitos:", "Ofrecemos:", "Responsabilidades del cargo:"]
BENEFICIOS = [
    "contrato a término indefinido", "salario competitivo más prestaciones de ley", "horario de lunes a viernes",
    "plan de carrera", "modalidad híbrida", "auxilio de alimentación", "capacitación constante",
]


@cache
def _fixture() -> tuple[tuple[str, str], ...]:
    vacantes = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return tuple((v["titulo"], v["descripcion"]) for v in vacantes)


CONTEXTOS = [
    "", "en empresas medianas", "para clientes nacionales e internacionales", "bajo metodologías ágiles",
    "en entornos de alto volumen", "con orientación a resultados", "en el sector público", "en Medellín o Bogotá",
    "a nivel intermedio", "a nivel avanzado", "con autonomía", "en turnos rotativos",
]


def _rellenar(plantilla: str, rnd: random.Random) -> str:
    area = rnd.choice(list(INDUSTRIAS))
    h1, h2 = rnd.sample(INDUSTRIAS[area], 2)
    nivel = rnd.choice(["técnica", "tecnológica", "profesional", "de posgrado"])
    frase = plantilla.format(area=area, h1=h1, h2=h2, nivel=nivel, anios=rnd.randint(1, 8), anio=rnd.randint(2015, 2026))
    return f"{frase} {rnd.choice(CONTEXTOS)}".strip()


def _frases(plantillas: list[str], n: int, semilla: int) -> list[str]:
    rnd = random.Random(semilla)
    return [_rellenar(rnd.choice(plantillas), rnd) for _ in range(n)]


def unidades_requisito(n: int, semilla: int = 0) -> list[str]:
    return _frases(PLANTILLAS_REQUISITO, n, semilla)


def unidades_evidencia(n: int, semilla: int = 0) -> list[str]:
    return _frases(PLANTILLAS_EVIDENCIA, n, semilla + 1_000_003)


def documentos_vacante(n: int, semilla: int = 0) -> list[str]:
    rnd = random.Random(semilla)
    reales = _fixture()
    docs = []
    for _ in range(n):
        titulo, descripcion = rnd.choice(reales)
        partes = [titulo, descripcion]
        objetivo = rnd.randint(300, 2400)
        while sum(len(p) + 1 for p in partes) < objetivo:
            partes.append(rnd.choice(CONECTORES))
            partes.extend(_rellenar(rnd.choice(PLANTILLAS_REQUISITO), rnd) + "." for _ in range(rnd.randint(2, 5)))
            partes.append("Ofrecemos " + ", ".join(rnd.sample(BENEFICIOS, 3)) + ".")
        docs.append(" ".join(partes)[:2500])
    return docs


def resumenes_vacante(n: int, semilla: int = 0) -> list[str]:
    """Lo que de verdad recibe el reranker: título + requisitos, no la descripción completa."""
    rnd = random.Random(semilla + 7_000_001)
    reales = _fixture()
    resumenes = []
    for _ in range(n):
        titulo = rnd.choice(reales)[0]
        requisitos = [_rellenar(rnd.choice(PLANTILLAS_REQUISITO), rnd) for _ in range(rnd.randint(3, 7))]
        resumen = f"{titulo}. " + "; ".join(requisitos)
        while len(resumen) > 700:
            requisitos.pop()
            resumen = f"{titulo}. " + "; ".join(requisitos)
        resumenes.append(resumen)
    return resumenes
