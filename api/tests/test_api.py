import json
from pathlib import Path

import pytest
from django.urls import reverse

from cuentas.models import Perfil
from matching.models import SolicitudDecision
from vacantes.models import EstadoIngesta, Vacante
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

TOKEN = "token-de-prueba-n8n"


@pytest.fixture(autouse=True)
def token(settings):
    settings.N8N_SCORING_TOKEN = TOKEN


@pytest.fixture
def sincronico(monkeypatch):
    """La ingesta corre en un hilo; en los tests se ejecuta en el mismo hilo para ver el resultado."""
    monkeypatch.setattr("vacantes.services.lanzar_hilo", lambda funcion: funcion())
    monkeypatch.setattr("api.views.fuente_para", lambda datos: FuenteEnMemoria([cruda("v1", "Requisitos:\n- SQL\n- Excel")]))


def _post(client, nombre, datos=None, token=TOKEN):
    return client.post(reverse(nombre), data=json.dumps(datos or {}), content_type="application/json",
                       HTTP_X_SCOUTLY_TOKEN=token)


def test_sin_token_401(client, db):
    assert _post(client, "api_decidir", token="").status_code == 401


def test_token_de_desarrollo_rechazado_sin_debug(client, db, settings):
    settings.N8N_SCORING_TOKEN = settings.N8N_SCORING_TOKEN_DEV_DEFAULT
    assert _post(client, "api_decidir", token=settings.N8N_SCORING_TOKEN_DEV_DEFAULT).status_code == 503


def test_solo_post(client, db):
    assert client.get(reverse("api_decidir"), HTTP_X_SCOUTLY_TOKEN=TOKEN).status_code == 405


def test_decidir_encola_y_responde_202_sin_cargar_modelos(client, usuario, monkeypatch):
    import sys

    monkeypatch.delitem(sys.modules, "matching.ia.fastembed", raising=False)
    Perfil.objects.create(usuario=usuario, cv_nombre_archivo="cv.pdf")
    r = _post(client, "api_decidir")
    assert (r.status_code, r.json()) == (202, {"encolados": 1})
    assert SolicitudDecision.objects.count() == 1 and "matching.ia.fastembed" not in sys.modules


def test_importar_responde_202_y_corre_la_ingesta(client, db, sincronico):
    r = _post(client, "api_importar_vacantes", {"terminos": ["analista"], "por_termino": 2})
    assert r.status_code == 202 and Vacante.objects.filter(id="v1").exists()
    assert not EstadoIngesta.objects.get().en_curso


def test_importar_409_si_ya_corre(client, db, sincronico):
    EstadoIngesta.objects.update_or_create(id=1, defaults={"en_curso": True})
    assert _post(client, "api_importar_vacantes").status_code == 409


def test_generar_notificaciones_devuelve_el_resumen(client, db):
    r = _post(client, "api_generar_notificaciones")
    assert r.status_code == 200 and r.json() == {"creadas": 0, "correos": 0}


def test_el_workflow_llama_los_tres_endpoints_en_orden():
    flujo = json.loads(Path("n8n/workflow-matches-diarios.json").read_text(encoding="utf-8"))
    nodos = {n["name"]: n.get("parameters", {}).get("url", "") for n in flujo["nodes"]}
    orden, actual = [], next(n["name"] for n in flujo["nodes"] if n["type"].endswith("scheduleTrigger"))
    while actual in flujo["connections"]:
        actual = flujo["connections"][actual]["main"][0][0]["node"]
        orden.append(nodos[actual].rsplit("/", 1)[-1])
    assert orden == ["importar-vacantes", "decidir", "generar-notificaciones"]
