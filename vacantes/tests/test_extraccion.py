import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from vacantes.extraccion import (
    extraer_requisitos,
    extraer_restricciones,
    normalizar,
    requisitos_insuficientes,
)

RUTA_SET = Path(__file__).parent / "datos" / "extraccion.yaml"  # con este set se ajustó el extractor
RUTA_PRUEBA = Path(__file__).parent / "datos" / "extraccion_prueba.yaml"  # nunca se usa para ajustar
RUIDO_DE_PRUEBA = re.compile(r"\$\s?\d|importante empresa|te apasiona|prestaciones de ley|únete", re.IGNORECASE)


@dataclass
class Esperado:
    texto: str
    tipo: str


@dataclass
class Caso:
    id: str
    texto: str
    etiquetas: list[str]
    esperados: list[Esperado]
    insuficiente: bool
    limite_conocido: str | None = None


def cargar_casos(ruta: Path = RUTA_SET) -> list[Caso]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return [Caso(c["id"], c["texto"], c.get("etiquetas", []),
                 [Esperado(**e) for e in c.get("esperados", [])], c.get("insuficiente", False),
                 c.get("limite_conocido"))
            for c in datos["casos"]]


CASOS = cargar_casos()
CASOS_PRUEBA = cargar_casos(RUTA_PRUEBA)


def _coincide(esperado: str, hallados: set[str]) -> bool:
    e = normalizar(esperado)
    return any(e in h or h in e for h in hallados)


# --- contra el set etiquetado (vacantes reales de Magneto) -----------------------------------------

def test_el_set_tiene_al_menos_25_vacantes_y_casos_dificiles():
    assert len(CASOS) >= 25
    assert sum(c.insuficiente for c in CASOS) >= 3


def _cobertura(casos: list[Caso]) -> tuple[float, list[str]]:
    aciertos = total = 0
    fallos = []
    for caso in casos:
        hallados = {normalizar(r.texto) for r in extraer_requisitos(caso.texto, caso.etiquetas)}
        for esperado in caso.esperados:
            total += 1
            if _coincide(esperado.texto, hallados):
                aciertos += 1
            else:
                fallos.append(f"{caso.id}: {esperado.texto}")
    return aciertos / total, fallos


def test_cobertura_de_lo_esperado_en_el_set():
    cobertura, fallos = _cobertura(CASOS)
    assert cobertura >= 0.80, "\n".join(fallos)


def test_cobertura_en_el_set_de_prueba():
    """El número que se reporta: vacantes que el extractor nunca vio mientras se ajustaba (0,82 al crearlo)."""
    assert len(CASOS_PRUEBA) >= 8
    cobertura, fallos = _cobertura(CASOS_PRUEBA)
    assert cobertura >= 0.80, "\n".join(fallos)


def test_insuficientes_en_el_set_de_prueba():
    aciertos = sum(requisitos_insuficientes(extraer_requisitos(c.texto, c.etiquetas)) == c.insuficiente
                   for c in CASOS_PRUEBA)
    assert aciertos / len(CASOS_PRUEBA) >= 0.75


def test_el_tipo_coincide_en_el_set():
    aciertos = total = 0
    for caso in CASOS:
        reqs = extraer_requisitos(caso.texto, caso.etiquetas)
        for esperado in caso.esperados:
            encontrado = next((r for r in reqs if _coincide(esperado.texto, {normalizar(r.texto)})), None)
            if encontrado:
                total += 1
                aciertos += encontrado.tipo == esperado.tipo
    assert aciertos / total >= 0.80


def test_el_ruido_no_entra_como_requisito():
    for caso in CASOS:
        for r in extraer_requisitos(caso.texto, caso.etiquetas):
            assert not RUIDO_DE_PRUEBA.search(r.texto), (caso.id, r.texto)


def test_las_insuficientes_del_set_se_detectan():
    """Los casos marcados `limite_conocido` documentan dónde la regla falla a propósito; no pueden ser más de 1."""
    errados = {c.id for c in CASOS
               if requisitos_insuficientes(extraer_requisitos(c.texto, c.etiquetas)) != c.insuficiente}
    conocidos = {c.id for c in CASOS if c.limite_conocido}
    assert errados <= conocidos and len(conocidos) <= 1, errados - conocidos


# --- reglas puntuales ----------------------------------------------------------------------------

def test_deseable_por_palabra_guia():
    [r] = extraer_requisitos("Requisitos:\n- Deseable inglés intermedio", [])
    assert r.tipo == "deseable"


def test_etiquetas_son_deseables():
    reqs = extraer_requisitos("Requisitos:\n- Experiencia en ventas de 2 años", ["Canva"])
    assert ("Canva", "deseable", "etiqueta") in {(r.texto, r.tipo, r.origen) for r in reqs}


def test_una_etiqueta_repetida_en_el_texto_no_se_duplica():
    reqs = extraer_requisitos("Requisitos:\n- Manejo de Excel", ["excel"])
    assert [r.origen for r in reqs] == ["texto"]


def test_vacante_solo_marketing_es_insuficiente():
    reqs = extraer_requisitos("Importante empresa del sector te invita a unirte. ¡Te apasiona crecer!", [])
    assert requisitos_insuficientes(reqs)


def test_sin_seccion_usa_las_oraciones_con_palabras_de_requisito():
    texto = ("Somos una empresa líder. Buscamos auxiliar con experiencia en manejo de inventarios. "
             "Ofrecemos buen ambiente laboral. Es necesario conocimiento en Excel.")
    textos = [r.texto for r in extraer_requisitos(texto, [])]
    assert any("inventarios" in t for t in textos) and any("Excel" in t for t in textos)
    assert not any("ambiente laboral" in t for t in textos)


def test_las_funciones_no_son_requisitos_si_hay_seccion_de_requisitos():
    texto = "Funciones:\n- Atender clientes en tienda\nRequisitos:\n- Bachiller\n- Experiencia en ventas"
    assert [r.texto for r in extraer_requisitos(texto, [])] == ["Bachiller", "Experiencia en ventas"]


def test_anios_minimos():
    assert extraer_restricciones("Experiencia mínima de 3 años en cargos similares").anios_minimos == 3
    assert extraer_restricciones("Requisitos para aplicar a la vacante:\n\n1 año de experiencia, Técnico").anios_minimos == 1


def test_sin_experiencia():
    assert extraer_restricciones("Requisitos para aplicar a la vacante:\n\nSin experiencia, Bachiller").anios_minimos == 0


def test_salario_rango_y_unico():
    r = extraer_restricciones("$ 3.800.000 a $ 4.200.000\nBogotá")
    assert (r.salario_min, r.salario_max) == (3800000, 4200000)
    r = extraer_restricciones("Requisitos para aplicar a la vacante:\n\n1 año de experiencia\n$ 2.800.000\nMedellín")
    assert (r.salario_min, r.salario_max) == (2800000, 2800000)


@pytest.mark.parametrize("texto,modalidad", [("Modalidad: Presencial", "Presencial"),
                                             ("trabajo 100% remoto", "Remoto"),
                                             ("Esquema híbrido 3x2", "Híbrido"),
                                             ("Sin datos de modalidad", None)])
def test_modalidad(texto, modalidad):
    assert extraer_restricciones(texto).modalidad == modalidad


def test_nivel_de_formacion_del_resumen_de_magneto():
    r = extraer_restricciones("Requisitos para aplicar a la vacante:\n\n1 año de experiencia, Técnico hasta Profesional")
    assert r.nivel_formacion == "Técnico hasta Profesional"


RESUMEN = "Requisitos para aplicar a la vacante:\n\n{}\nDescripción de la vacante."


def test_meses_de_experiencia_cuentan_como_cero_anios():
    assert extraer_restricciones(RESUMEN.format("6 meses de experiencia, Bachillerato completo\n$ 1.750.000\nBogotá")).anios_minimos == 0


def test_salario_a_convenir_no_toma_otras_cifras_del_texto():
    texto = RESUMEN.format("1 año de experiencia, Profesional\nSalario a convenir\nBogotá") + "\nAuxilio de transporte ($249.095)"
    r = extraer_restricciones(texto)
    assert (r.salario_min, r.salario_max, r.ubicacion) == (None, None, "Bogotá")


def test_resumen_de_practica_sin_anios():
    r = extraer_restricciones(RESUMEN.format("Profesional\n$ 1.750.905\nMedellín"))
    assert (r.anios_minimos, r.nivel_formacion, r.ubicacion) == (None, "Profesional", "Medellín")


def test_resumen_con_linea_de_inclusion():
    r = extraer_restricciones(RESUMEN.format("Apto para personas con discapacidad\n6 meses de experiencia, Técnico hasta Tecnólogo\nSalario a convenir\nPereira"))
    assert (r.nivel_formacion, r.ubicacion, r.anios_minimos) == ("Técnico hasta Tecnólogo", "Pereira", 0)


# --- regresiones de la revisión final: restricciones sin resumen de Magneto -------------------------

def test_los_anios_de_la_empresa_no_son_un_requisito():
    texto = "Somos una compañía con más de 20 años de experiencia.\nRequisitos:\n- 2 años de experiencia en ventas"
    assert extraer_restricciones(texto).anios_minimos == 2


def test_una_palabra_suelta_no_define_la_modalidad():
    assert extraer_restricciones("Requisitos:\n- Despliegues en nube híbrida").modalidad is None


def test_el_auxilio_no_es_el_salario():
    r = extraer_restricciones("Requisitos:\n- Excel\nAuxilio de transporte ($249.095)")
    assert (r.salario_min, r.salario_max) == (None, None)
