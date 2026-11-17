"""Fixtures compartidas por todas las apps."""

import pytest

CLAVE_DE_PRUEBA = "Lienzo-Tardio-73"


@pytest.fixture(autouse=True)
def embedder_falso(settings):
    """Ningún test carga modelos reales salvo los marcados `lento`."""
    settings.SCOUTLY_EMBEDDER = "falso"
    settings.SCOUTLY_RERANKER = ""


@pytest.fixture(autouse=True)
def cache_en_memoria(settings):
    """Los tests no dependen de la tabla de caché de Postgres, y cada uno empieza con la caché vacía."""
    from django.core.cache import cache

    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


@pytest.fixture
def usuario(db):
    from cuentas.services import crear_usuario_con_autorizacion

    return crear_usuario_con_autorizacion("ana@ejemplo.com", CLAVE_DE_PRUEBA)


@pytest.fixture
def vacante_v1(db):
    from datetime import date

    from vacantes.models import Requisito, Vacante

    vacante = Vacante.objects.create(id="v1", titulo="Analista de Datos Junior", empresa="ACME", ubicacion="Medellín",
                                     modalidad="Presencial", fecha_publicacion=date(2026, 10, 30), fuente="prueba",
                                     hash_contenido="x", texto_completo="Requisitos:\n- SQL\n- Excel")
    Requisito.objects.create(vacante=vacante, texto="SQL", tipo="obligatorio", origen="texto", posicion=0)
    return vacante


@pytest.fixture
def client_con_cv(client, usuario):
    from cuentas.services import guardar_perfil_desde_cv
    from cuentas.tests.cvs import pdf_cv

    guardar_perfil_desde_cv(usuario, pdf_cv())
    client.force_login(usuario)
    return client
