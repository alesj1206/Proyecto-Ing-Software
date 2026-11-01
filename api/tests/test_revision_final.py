"""Regresiones de la revisión final de la Fase 3 (API, flujo diario y B1)."""

import json

import pytest
from django.core.management import call_command
from django.urls import reverse

from matching.models import SolicitudDecision
from matching.tests.test_decidir import VACANTES, _perfil
from notificaciones.models import Notificacion
from vacantes.models import EstadoIngesta
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

TOKEN = "token-de-prueba-n8n"


@pytest.fixture(autouse=True)
def token(settings):
    settings.N8N_SCORING_TOKEN = TOKEN


def _post(client, nombre, datos="{}"):
    return client.post(reverse(nombre), data=datos, content_type="application/json", HTTP_X_SCOUTLY_TOKEN=TOKEN)


def test_el_flujo_real_de_n8n_si_notifica(client, usuario, monkeypatch):
    """n8n no espera al batch: la ingesta encola la decisión al terminar y el batch notifica después de decidir."""
    monkeypatch.setattr("vacantes.services.lanzar_hilo", lambda funcion: funcion())
    monkeypatch.setattr("api.views.fuente_para", lambda datos: FuenteEnMemoria([cruda("vpost", VACANTES["vpost"])]))
    perfil = _perfil(usuario, evidencia=["Reportes de ventas en Excel", "Atención de clientes en tienda"])
    _post(client, "api_importar_vacantes")
    assert SolicitudDecision.objects.filter(perfil=perfil).exists()  # encolada por la ingesta
    _post(client, "api_decidir")
    _post(client, "api_generar_notificaciones")  # llega antes que el batch
    call_command("decidir", "--pendientes")       # el batch decide y notifica
    assert Notificacion.objects.filter(perfil=perfil, vacante_id="vpost").exists()


@pytest.mark.parametrize("cuerpo", ['{"terminos": "abc"}', '{"terminos": ["x"], "por_termino": "mucho"}',
                                    '[1, 2]', '{"terminos": ["' + "x" * 200 + '"]}',
                                    '{"terminos": ' + json.dumps(["t"] * 50) + '}'])
def test_importar_valida_la_entrada(client, db, cuerpo):
    assert _post(client, "api_importar_vacantes", cuerpo).status_code == 400


def test_token_no_ascii_no_da_500(client, db):
    r = client.post(reverse("api_decidir"), data="{}", content_type="application/json",
                    HTTP_X_SCOUTLY_TOKEN="ñandú")
    assert r.status_code == 401


def test_un_hilo_viejo_no_suelta_el_candado_de_otro(db, monkeypatch):
    from vacantes import services

    hilos = []
    monkeypatch.setattr(services, "lanzar_hilo", lambda funcion: hilos.append(funcion))
    assert services.ingerir_en_segundo_plano(FuenteEnMemoria([]))
    EstadoIngesta.objects.filter(id=1).update(iniciada_en="2000-01-01T00:00:00Z")  # el primero parece colgado
    assert services.ingerir_en_segundo_plano(FuenteEnMemoria([]))  # lo retoma un segundo
    hilos[0]()  # el primero termina tarde
    assert EstadoIngesta.objects.get(id=1).en_curso  # el candado sigue siendo del segundo


@pytest.mark.parametrize("valor,activo", [("", False), ("0", False), ("false", False), ("1", True), ("true", True)])
def test_la_bandera_de_b1_se_lee_como_booleano(valor, activo):
    from scoutly.settings import _activado

    assert _activado(valor) is activo
