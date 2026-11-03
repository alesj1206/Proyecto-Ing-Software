"""Fuente de Magneto para cargar un catálogo grande: pagina, entrega por término y omite lo conocido."""

import pytest

from vacantes.fuentes.magneto_detalle import CHROME, FuenteMagnetoDetalle


class _PaginaFalsa:
    """Un listado de Magneto: tras buscar queda en /buscar/<término> y cada /pagina-N da sus enlaces. Como el sitio real,
    ignora los parámetros de la URL (?paginator[page]=N devuelve la primera página)."""

    def __init__(self, paginas: dict[int, list[str]]):
        self.paginas, self.actual, self.url, self.visitadas = paginas, 1, "https://www.magneto365.com/co/trabajos/buscar/x", []

    def goto(self, url, timeout=None):
        self.visitadas.append(url)
        self.actual = int(url.rsplit("/pagina-", 1)[1]) if "/pagina-" in url else 1

    def wait_for_timeout(self, ms):
        pass

    def eval_on_selector_all(self, selector, codigo):
        return [f"https://www.magneto365.com/co/empleos/v-{i}" for i in self.paginas.get(self.actual, [])]


def _fuente_con_busqueda(monkeypatch, por_termino, omitir=frozenset()):
    fuente = FuenteMagnetoDetalle(["x"], por_termino, omitir=omitir)
    monkeypatch.setattr(fuente, "_buscar", lambda pagina, termino: None)
    return fuente


def test_si_no_alcanza_una_pagina_de_resultados_sigue_con_la_siguiente(monkeypatch):
    pagina = _PaginaFalsa({1: [1, 2], 2: [3, 4], 3: [5, 6]})
    urls = _fuente_con_busqueda(monkeypatch, 3)._enlaces(pagina, "x")
    assert [u.rsplit("-", 1)[-1] for u in urls] == ["1", "2", "3"]
    assert pagina.visitadas == ["https://www.magneto365.com/co/trabajos/buscar/x/pagina-2"]


def test_los_resultados_se_acaban_antes_del_tope(monkeypatch):
    pagina = _PaginaFalsa({1: [1, 2]})
    assert len(_fuente_con_busqueda(monkeypatch, 50)._enlaces(pagina, "x")) == 2


def test_las_vacantes_conocidas_se_omiten_sin_abrirlas_y_no_cuentan_para_el_tope(monkeypatch):
    pagina = _PaginaFalsa({1: [1, 2], 2: [3, 4]})
    urls = _fuente_con_busqueda(monkeypatch, 2, omitir={"1", "2", "3"})._enlaces(pagina, "x")
    assert [u.rsplit("-", 1)[-1] for u in urls] == ["4"]


def test_se_entrega_termino_por_termino(monkeypatch):
    """Una carga de horas no pierde lo ya descargado si se corta: cada término se escribe al terminar."""
    fuente = FuenteMagnetoDetalle(["a", "b"], 1)
    pedidos = []
    monkeypatch.setattr(fuente, "_descargar", lambda termino: pedidos.append(termino) or [termino])
    entregas = fuente.obtener()
    assert next(entregas) == "a" and pedidos == ["a"]
    assert list(entregas) == ["b"] and pedidos == ["a", "b"]


@pytest.mark.lento
def test_la_paginacion_funciona_en_magneto_de_verdad():
    """Una página falsa no basta: la primera versión pasaba sus pruebas y en el sitio real siempre traía la página 1."""
    from playwright.sync_api import sync_playwright

    fuente = FuenteMagnetoDetalle(["auxiliar administrativo"], 45, CHROME)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=CHROME, headless=True)
        try:
            urls = fuente._enlaces(navegador.new_page(viewport={"width": 1440, "height": 1400}), "auxiliar administrativo")
        finally:
            navegador.close()
    assert len(urls) == 45 and len(set(urls)) == 45
