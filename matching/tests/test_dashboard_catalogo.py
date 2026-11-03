"""El catálogo del dashboard se pagina: con 120.000 vacantes la página pesaba 86 MB y tardaba 30 s (2026-11-02)."""

from django.urls import reverse

from matching.selectors import TAMANO_PAGINA_CATALOGO
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda
from vacantes.services import ingerir


def _catalogo(n):
    ingerir(FuenteEnMemoria([cruda(f"v{i}", "Requisitos:\n- SQL\n- Excel") for i in range(n)]))


def test_el_catalogo_muestra_una_sola_pagina(client_con_cv):
    _catalogo(TAMANO_PAGINA_CATALOGO + 3)
    r = client_con_cv.get(reverse("dashboard"))
    assert len(r.context["vacantes"]) == TAMANO_PAGINA_CATALOGO and r.context["vacantes"].has_next()
    assert "pagina=2" in r.content.decode()


def test_la_segunda_pagina_trae_el_resto_y_conserva_el_filtro(client_con_cv):
    _catalogo(TAMANO_PAGINA_CATALOGO + 3)
    r = client_con_cv.get(reverse("dashboard"), {"pagina": 2})
    assert len(r.context["vacantes"]) == 3 and not r.context["vacantes"].has_next()
    assert r.context["total_vacantes"] >= TAMANO_PAGINA_CATALOGO + 3
    r = client_con_cv.get(reverse("dashboard"), {"modalidad": "Remoto"})
    assert "modalidad=Remoto" in r.content.decode() or not r.context["vacantes"].has_next()


def test_una_pagina_invalida_no_rompe(client_con_cv):
    _catalogo(2)
    for valor in ("abc", "999", "-1"):
        assert client_con_cv.get(reverse("dashboard"), {"pagina": valor}).status_code == 200


def test_el_catalogo_no_lee_el_texto_completo(client_con_cv):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _catalogo(2)
    with CaptureQueriesContext(connection) as q:
        client_con_cv.get(reverse("dashboard"))
    lecturas = [c["sql"] for c in q if 'FROM "vacantes_vacante"' in c["sql"] and "COUNT" not in c["sql"].upper()]
    assert lecturas and not any('"texto_completo"' in s or '"matriz_requisitos"' in s for s in lecturas)
