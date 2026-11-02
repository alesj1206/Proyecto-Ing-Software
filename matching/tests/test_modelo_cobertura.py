"""Adopción de mpnet para la cobertura (docs/exploracion/2026-11-02-mejoras-decisor.md, recomendación 0): la
preselección sigue con el modelo de búsqueda (MiniLM, 384) y las matrices requisito × evidencia salen del modelo de
cobertura (mpnet, 768)."""

import numpy as np

from cuentas.services import guardar_perfil_desde_cv
from cuentas.tests.cvs import pdf_cv
from matching.ia import obtener_embedder_cobertura
from matching.ia.fakes import EmbedderFalso
from matching.politica import POLITICA
from matching.services import decidir_para_perfil
from matching.vectores import de_bytes, embeber_perfil, embeber_vacantes
from vacantes.models import Vacante
from vacantes.services import ingerir
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

BUSQUEDA, COBERTURA = EmbedderFalso(384), EmbedderFalso(768)


def test_la_matriz_de_requisitos_sale_del_modelo_de_cobertura(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- Experiencia de 2 años en análisis de datos\n- Excel")]))
    embeber_vacantes(BUSQUEDA, cobertura=COBERTURA)
    v = Vacante.objects.get(id="v1")
    textos = [r.texto for r in v.requisito_set.order_by("posicion")]
    assert len(v.vector) == 384  # la preselección no cambia
    assert np.allclose(de_bytes(v.matriz_requisitos, len(textos)), COBERTURA.embeber(textos), atol=1e-2)


def test_la_evidencia_del_perfil_usa_el_modelo_de_cobertura(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv())
    embeber_perfil(perfil, BUSQUEDA, cobertura=COBERTURA)
    perfil.refresh_from_db()
    n = perfil.evidencias.count()
    assert len(perfil.vector) == 384 and de_bytes(perfil.matriz_evidencia, n).shape == (n, 768)


def test_cambiar_el_modelo_de_cobertura_vuelve_a_embeber_el_perfil(usuario):
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv())
    assert embeber_perfil(perfil, BUSQUEDA) is True
    assert embeber_perfil(perfil, BUSQUEDA, cobertura=COBERTURA) is True  # la firma incluye el modelo
    assert embeber_perfil(perfil, BUSQUEDA, cobertura=COBERTURA) is False


def test_matrices_de_modelos_distintos_no_se_cruzan(usuario):
    """Una vacante embebida con el modelo viejo (384) y un perfil con el nuevo (768) no rompen la decisión: la
    vacante no se decide hasta que se re-embeba (test_decidir: su decisión anterior se conserva)."""
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    embeber_vacantes(BUSQUEDA)
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv())
    resumen = decidir_para_perfil(perfil, BUSQUEDA, cobertura=COBERTURA)
    assert resumen.relevantes == 0


def test_el_modelo_de_cobertura_falso_tiene_la_dimension_de_mpnet(settings):
    settings.SCOUTLY_EMBEDDER = "falso"
    assert obtener_embedder_cobertura().dimension == 768


def test_la_politica_por_defecto_es_la_medida_en_prueba_3():
    assert (POLITICA.tau_alto, POLITICA.tau_bajo, POLITICA.fusionar_ajustar) == (0.425, 0.425, True)
    assert POLITICA.tau_relevancia == 0.25  # la preselección sigue con MiniLM


def test_los_comandos_usan_el_modelo_de_cobertura(usuario, settings):
    from django.core.management import call_command

    settings.SCOUTLY_EMBEDDER = "falso"
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    perfil = guardar_perfil_desde_cv(usuario, pdf_cv())
    call_command("decidir", "--todos")
    v = Vacante.objects.get(id="v1")
    perfil.refresh_from_db()
    assert de_bytes(v.matriz_requisitos, 2).shape == (2, 768)
    assert de_bytes(perfil.matriz_evidencia, perfil.evidencias.count()).shape[1] == 768


def test_el_comando_embeber_vacantes_usa_el_modelo_de_cobertura(db, settings):
    from django.core.management import call_command

    settings.SCOUTLY_EMBEDDER = "falso"
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    call_command("embeber_vacantes")
    assert de_bytes(Vacante.objects.get(id="v1").matriz_requisitos, 2).shape == (2, 768)


def test_cambiar_de_modelo_vuelve_a_embeber_las_vacantes_sin_esperar_la_ingesta(db):
    ingerir(FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))
    assert embeber_vacantes(BUSQUEDA) == 1
    assert embeber_vacantes(BUSQUEDA, cobertura=COBERTURA) == 1  # el contenido no cambió, el modelo sí
    assert embeber_vacantes(BUSQUEDA, cobertura=COBERTURA) == 0
