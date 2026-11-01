from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command

from vacantes import services
from vacantes.fuentes import VacanteCruda
from vacantes.fuentes.fixture import FuenteFixture
from vacantes.fuentes.magneto_detalle import FuenteMagnetoDetalle, parsear_detalle
from vacantes.models import Requisito, Vacante
from vacantes.services import ingerir

RUTA_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vacantes_magneto.json"


class FuenteEnMemoria:
    nombre = "memoria"

    def __init__(self, vacantes):
        self.vacantes = vacantes

    def obtener(self):
        return iter(self.vacantes)


def cruda(id_, texto, etiquetas=(), **otros):
    base = VacanteCruda(id=id_, titulo=f"Vacante {id_}", empresa="ACME", ubicacion="Medellín", modalidad="Presencial",
                        texto_completo=texto, etiquetas=tuple(etiquetas), url=f"https://ejemplo.co/{id_}",
                        fecha_publicacion=date(2026, 10, 30))
    return replace(base, **otros)


# --- ingesta incremental ---------------------------------------------------------------------------

def test_ingesta_crea_vacantes_y_requisitos(db):
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL avanzado\n- Excel")]))
    assert (r.creadas, Requisito.objects.filter(vacante_id="v1").count()) == (1, 2)
    assert Vacante.objects.get(id="v1").fuente == "memoria"


def test_misma_vacante_sin_cambios_no_se_toca(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    assert (r.creadas, r.actualizadas, r.sin_cambios) == (0, 0, 1)


def test_vacante_modificada_reemplaza_requisitos_sin_duplicar(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel\n- Python")]))
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- Power BI")]))
    assert r.actualizadas == 1
    assert list(Requisito.objects.filter(vacante_id="v1").values_list("posicion", "texto")) == [(0, "Power BI")]


def test_una_vacante_que_falla_no_tumba_la_ingesta(db, monkeypatch):
    original = services.extraer_requisitos

    def explota_en_v2(texto, etiquetas):
        if "ROMPER" in texto:
            raise ValueError("texto ilegible")
        return original(texto, etiquetas)

    monkeypatch.setattr(services, "extraer_requisitos", explota_en_v2)
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel"), cruda("v2", "ROMPER"),
                                 cruda("v3", "Requisitos:\n- Excel\n- Word")]))
    assert (r.creadas, r.errores) == (2, 1)
    assert set(Vacante.objects.values_list("id", flat=True)) == {"v1", "v3"}


def test_vacante_sin_requisitos_legibles_cuenta_como_insuficiente(db):
    r = ingerir(FuenteEnMemoria([cruda("v1", "Importante empresa te invita a unirte. ¡Te apasiona crecer!")]))
    assert (r.creadas, r.insuficientes) == (1, 1)


def test_restricciones_del_texto_llenan_los_campos(db):
    texto = ("Requisitos para aplicar a la vacante:\n\n2 años de experiencia, Técnico hasta Profesional\n"
             "$ 2.100.000\nBogotá, D.C.\nRequisitos:\n- Excel\n- SQL")
    ingerir(FuenteEnMemoria([cruda("v1", texto)]))
    v = Vacante.objects.get(id="v1")
    assert (v.experiencia_minima, v.salario_min, v.nivel_formacion) == (2, 2100000, "Técnico hasta Profesional")


def test_el_salario_estructurado_de_la_fuente_manda(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- Excel\n- SQL", salario_min=3000000, salario_max=4000000)]))
    v = Vacante.objects.get(id="v1")
    assert (v.salario_min, v.salario_max) == (3000000, 4000000)


def test_fuente_fixture_lee_las_18_vacantes_de_v2(db):
    assert ingerir(FuenteFixture(RUTA_FIXTURE)).creadas == 18


def test_comando_ingerir_vacantes_con_fixture(db, capsys):
    call_command("ingerir_vacantes", "--fuente", "fixture")
    assert Vacante.objects.count() == 18 and "creadas: 18" in capsys.readouterr().out


# --- página de detalle de Magneto -------------------------------------------------------------------

PAGINA = """Iniciar sesión
Crear cuenta
/ empleos
/ Auxiliar Contable
Requerido con urgencia
Auxiliar Contable

IMPOCOSER S.A.S. | Término indefinido, 1 cupos
Fecha de publicación 2026-10-31
Aplicar
Guardar

Requisitos para aplicar a la vacante:

2 años de experiencia, Técnico hasta Profesional
$ 2.100.000
Bogotá, D.C.
Requerimientos:
Dominio de Excel intermedio.
Manejo de software contable.

Habilidades

Facturación electrónica
Excel intermedio

Palabras clave:

Auxiliar contable

Ver empresa: IMPOCOSER S.A.S.

¡Ten cuidado con el fraude!
Magneto y sus empresas aliadas nunca te pedirán dinero."""


def test_parsear_detalle_de_magneto():
    v = parsear_detalle(PAGINA, "https://www.magneto365.com/co/empleos/auxiliar-contable-1121542")
    assert (v.id, v.titulo, v.empresa, v.fecha_publicacion) == ("mag-1121542", "Auxiliar Contable",
                                                                 "IMPOCOSER S.A.S.", date(2026, 10, 31))
    assert v.etiquetas == ("Facturación electrónica", "Excel intermedio")
    assert v.texto_completo.startswith("Requisitos para aplicar a la vacante:")
    assert "Dominio de Excel intermedio." in v.texto_completo
    assert "Habilidades" not in v.texto_completo and "fraude" not in v.texto_completo
    assert v.urgente and v.ubicacion == "Bogotá, D.C."


def test_parsear_detalle_sin_bloque_devuelve_none():
    assert parsear_detalle("Página de error", "https://www.magneto365.com/co/empleos/x-1") is None


@pytest.mark.lento
def test_magneto_detalle_trae_texto_sin_truncar():
    [v] = list(FuenteMagnetoDetalle(["analista de datos"], 1).obtener())
    assert len(v.texto_completo) > 500


@pytest.mark.lento
def test_ingerir_desde_magneto_guarda_en_la_base(db):
    # Playwright sync deja un event loop activo: la fuente no puede ceder vacantes mientras el navegador está abierto.
    resumen = ingerir(FuenteMagnetoDetalle(["auxiliar contable"], 1))
    assert (resumen.creadas, resumen.errores) == (1, 0)


# --- regresiones de la revisión final ------------------------------------------------------------

def test_cambiar_urgencia_o_fecha_actualiza_la_vacante(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    r = ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel", urgente=True)]))
    assert r.actualizadas == 1 and Vacante.objects.get(id="v1").urgente


def test_solo_se_siguen_enlaces_de_magneto():
    from vacantes.fuentes.magneto_detalle import enlaces_validos

    hrefs = ["https://www.magneto365.com/co/empleos/analista-1", "https://evil.co/co/empleos/x-2",
             "javascript:alert(1)//co/empleos/x-3", "https://www.magneto365.com/co/empleos/analista-1?ref=a"]
    assert enlaces_validos(hrefs) == ["https://www.magneto365.com/co/empleos/analista-1"]


class _PaginaFalsa:
    """Una página de Playwright de mentira: la URL que contiene 'rota' falla al abrirse."""

    def __init__(self):
        self.url = None

    def goto(self, url, timeout=None):
        if "rota" in url:
            raise TimeoutError("la página no respondió")
        self.url = url

    def wait_for_timeout(self, ms):
        pass

    def inner_text(self, selector):
        return PAGINA


def test_una_pagina_que_falla_no_tira_la_corrida(monkeypatch):
    fuente = FuenteMagnetoDetalle(["x"], 2)
    monkeypatch.setattr(fuente, "_enlaces", lambda pagina, termino: [
        "https://www.magneto365.com/co/empleos/rota-1", "https://www.magneto365.com/co/empleos/buena-2"])
    monkeypatch.setattr("vacantes.fuentes.magneto_detalle.PAUSA_ENTRE_PAGINAS_S", 0)
    vacantes = fuente._recorrer(_PaginaFalsa())
    assert [v.id for v in vacantes] == ["mag-2"]


def test_un_termino_que_falla_no_tira_la_corrida(monkeypatch):
    fuente = FuenteMagnetoDetalle(["roto", "bueno"], 1)

    def enlaces(pagina, termino):
        if termino == "roto":
            raise TypeError("no apareció la caja de búsqueda")
        return ["https://www.magneto365.com/co/empleos/buena-2"]

    monkeypatch.setattr(fuente, "_enlaces", enlaces)
    monkeypatch.setattr("vacantes.fuentes.magneto_detalle.PAUSA_ENTRE_PAGINAS_S", 0)
    assert len(fuente._recorrer(_PaginaFalsa())) == 1
