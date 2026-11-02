import numpy as np
import pytest

from cuentas.services import guardar_perfil_desde_cv
from cuentas.tests.cvs import pdf_cv
from matching.ia.fakes import EmbedderFalso
from matching.puertos import ModelosEmbebido
from matching.vectores import a_bytes, de_bytes, embeber_perfil, embeber_vacantes
from vacantes.models import Vacante
from vacantes.services import ingerir
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

E = EmbedderFalso()
M = ModelosEmbebido(E, E)


def _ingerir(*crudas):
    ingerir(FuenteEnMemoria(list(crudas)))


def test_bytes_ida_y_vuelta():
    m = np.random.default_rng(0).normal(size=(3, 384)).astype(np.float32)
    assert np.allclose(de_bytes(a_bytes(m), 3), m, atol=1e-2) and de_bytes(b"", 0).shape == (0, 0)
    assert de_bytes(a_bytes(m), 4) is None  # no alcanza para esas filas: matriz vieja


def test_embeber_vacantes_solo_las_nuevas_o_cambiadas(db):
    _ingerir(cruda("v1", "Requisitos:\n- SQL\n- Excel"), cruda("v2", "Requisitos:\n- Python\n- Docker"))
    assert embeber_vacantes(M) == 2
    assert embeber_vacantes(M) == 0
    _ingerir(cruda("v1", "Requisitos:\n- Power BI\n- Tableau"))
    assert embeber_vacantes(M) == 1


def test_la_matriz_sigue_el_orden_de_posicion(db):
    _ingerir(cruda("v1", "Requisitos:\n- SQL avanzado\n- Excel intermedio", etiquetas=["Docker"]))
    embeber_vacantes(M)
    v = Vacante.objects.get(id="v1")
    textos = [r.texto for r in v.requisito_set.order_by("posicion")]
    assert np.allclose(de_bytes(v.matriz_requisitos, len(textos)), E.embeber(textos), atol=1e-2)


def test_el_vector_de_la_vacante_es_el_promedio_normalizado(db):
    _ingerir(cruda("v1", "Requisitos:\n- SQL avanzado\n- Excel intermedio", etiquetas=["Docker"]))
    embeber_vacantes(M)
    v = Vacante.objects.get(id="v1")
    esperado = E.embeber([v.titulo, "SQL avanzado", "Excel intermedio"]).mean(axis=0)
    esperado /= np.linalg.norm(esperado)
    assert np.allclose(np.asarray(v.vector, dtype=np.float32), esperado, atol=1e-2)


def test_vacante_sin_requisitos_tiene_vector_solo_del_titulo(db):
    _ingerir(cruda("v1", "Importante empresa te invita a unirte."))
    embeber_vacantes(M)
    v = Vacante.objects.get(id="v1")
    assert np.allclose(np.asarray(v.vector, dtype=np.float32), E.embeber([v.titulo])[0], atol=1e-2)


def test_perfil_sin_evidencia_no_tiene_vector(usuario):
    from cuentas.tests.cvs import pdf_sin_texto

    perfil = guardar_perfil_desde_cv(usuario, pdf_sin_texto())
    embeber_perfil(perfil, M)
    assert perfil.vector is None


def test_embeber_perfil_no_repite_si_no_cambio(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv())
    assert embeber_perfil(perfil, M) is True
    assert embeber_perfil(perfil, M) is False
    perfil.refresh_from_db()
    assert perfil.vector is not None and de_bytes(perfil.matriz_evidencia, perfil.evidencias.count()) is not None


def test_modalidad_por_defecto_queda_marcada_como_inferida(db):
    _ingerir(cruda("v1", "Requisitos:\n- SQL\n- Excel", modalidad=""), cruda("v2", "Requisitos:\n- SQL\n- Excel"))
    assert Vacante.objects.get(id="v1").modalidad_inferida and not Vacante.objects.get(id="v2").modalidad_inferida


def test_experiencia_con_area_entra_al_vector_por_su_nucleo_y_a_la_matriz_completa(db):
    """`nucleo` es el ajuste de MiniLM para la preselección; la cobertura (mpnet) se midió con el texto completo."""
    _ingerir(cruda("v1", "Requisitos:\n- Experiencia mínima de 2 años en análisis de datos\n- Manejo de Excel"))
    embeber_vacantes(M)
    v = Vacante.objects.get(id="v1")
    reqs = sorted(v.requisito_set.all(), key=lambda r: r.posicion)
    assert reqs[0].texto.startswith("Experiencia mínima")  # el texto que se muestra no cambia
    assert np.allclose(de_bytes(v.matriz_requisitos, len(reqs))[0], E.embeber([reqs[0].texto])[0], atol=1e-2)
    esperado = E.embeber([v.titulo, "análisis de datos", reqs[1].texto]).mean(axis=0)
    assert np.allclose(np.asarray(v.vector, dtype=np.float32), esperado / np.linalg.norm(esperado), atol=1e-2)


class EmbedderQueCuenta(EmbedderFalso):
    def __init__(self, dimension=384):
        super().__init__(dimension)
        self.recibidos = []

    def embeber(self, textos):
        self.recibidos += textos
        return super().embeber(textos)


def test_cada_texto_distinto_se_embebe_una_vez_por_lote(db):
    _ingerir(cruda("v1", "Requisitos:\n- Trabajo en equipo\n- SQL"), cruda("v2", "Requisitos:\n- Trabajo en equipo\n- Excel"))
    busqueda, cobertura = EmbedderQueCuenta(), EmbedderQueCuenta(768)
    embeber_vacantes(ModelosEmbebido(busqueda, cobertura))
    assert busqueda.recibidos.count("Trabajo en equipo") == 1 and cobertura.recibidos.count("Trabajo en equipo") == 1
    for v in Vacante.objects.all():  # el resultado es el mismo que embebiendo todo
        textos = [r.texto for r in v.requisito_set.order_by("posicion")]
        assert np.allclose(de_bytes(v.matriz_requisitos, len(textos)), cobertura.embeber(textos), atol=1e-2)
