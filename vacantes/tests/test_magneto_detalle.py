"""Fuente de Magneto para cargar un catálogo grande: pagina, entrega por término y omite lo conocido."""

from vacantes.fuentes.magneto_detalle import FuenteMagnetoDetalle


class _PaginaFalsa:
    """Un listado de Magneto: tras buscar queda en /buscar/<término> y cada ?paginator[page]=N da sus enlaces."""

    def __init__(self, paginas: dict[int, list[str]]):
        self.paginas, self.actual, self.url, self.visitadas = paginas, 1, "https://www.magneto365.com/co/trabajos/buscar/x", []

    def goto(self, url, timeout=None):
        self.visitadas.append(url)
        self.actual = int(url.rsplit("=", 1)[-1])

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
    assert pagina.visitadas == ["https://www.magneto365.com/co/trabajos/buscar/x?paginator[page]=2"]


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
