"""Regresiones de la revisión final de la Fase 4 sobre la extracción de requisitos."""

import time

from vacantes.extraccion import extraer_requisitos, nucleo


def _reqs(texto):
    return [(r.texto, r.tipo) for r in extraer_requisitos(texto, [])]


def test_lista_entre_parentesis_hereda_deseable():
    reqs = _reqs("Requisitos:\n- Deseable conocimiento en herramientas (Excel, Word y PowerPoint)")
    assert reqs and all(tipo == "deseable" for _, tipo in reqs)


def test_lista_de_lugares_entre_parentesis_no_se_separa():
    textos = [t for t, _ in _reqs("Requisitos:\n- Disponibilidad para trabajar en Medellín (Bello, Itagüí y Envigado)\n"
                                  "- Manejo de Excel")]
    assert textos[0].startswith("Disponibilidad para trabajar") and "Bello" not in textos


def test_items_cortos_entre_parentesis_no_se_separan():
    assert [t for t, _ in _reqs("Requisitos:\n- Licencia de conducción (A2 y B1)\n- Manejo de Excel")][0] == \
        "Licencia de conducción (A2 y B1)"


def test_parentesis_sin_cerrar_no_deja_fragmentos():
    textos = [t for t, _ in _reqs("Requisitos:\n- Manejo de SAP (módulos FI, CO y MM)\n- Manejo de Excel")]
    assert all(t.count("(") == t.count(")") for t in textos)


def test_frases_tipo_presentacion_dentro_de_requisitos_se_conservan():
    textos = [t for t, _ in _reqs("Requisitos:\n- Si tienes experiencia en ventas de 2 años\n"
                                  "- Tendrás manejo de Excel avanzado")]
    assert len(textos) == 2


def test_habilidades_tecnicas_del_empleador_son_requisitos():
    textos = [t for t, _ in _reqs("Requisitos:\n- Contador público\nHabilidades técnicas:\n- NIIF\n- SAP\n- Excel avanzado")]
    assert {"NIIF", "SAP", "Excel avanzado"} <= set(textos)


def test_el_pie_de_magneto_sigue_fuera():
    textos = [t for t, _ in _reqs("Requisitos:\n- Manejo de Excel\n- Experiencia en conciliaciones\n"
                                  "Otras habilidades:\nHabilidades técnicas:\nOdoo\nHabilidades interpersonales:\nProaktividad")]
    assert "Odoo" not in textos and "Proaktividad" not in textos


def test_nucleo_generico_conserva_la_frase():
    for frase in ("Experiencia de 2 años en el cargo", "Experiencia mínima de 1 año en cargos similares"):
        assert nucleo(frase) == frase


def test_nucleo_no_se_cuelga_con_espacios():
    inicio = time.perf_counter()
    nucleo("experiencia" + " " * 20000 + "x")
    assert time.perf_counter() - inicio < 0.5
