from datetime import date
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from vacantes.fuentes.magneto_mcp import ClienteMCPFalso, ClienteMCPHttp, FuenteMagnetoMCP
from vacantes.models import Vacante
from vacantes.services import ingerir

DETALLE = {"id": "1121542", "title": "Auxiliar Contable", "company": "IMPOCOSER S.A.S.", "location": "Bogotá, D.C.",
           "modality": "Presencial", "description": "Requisitos:\n- Excel intermedio\n- Facturación electrónica",
           "skills": ["NIIF"], "publishedAt": "2026-10-31", "salary": {"min": 2100000, "max": 2100000},
           "url": "https://www.magneto365.com/co/empleos/auxiliar-contable-1121542",
           "prefilter": [{"question": "¿Tienes experiencia con facturación electrónica?"}]}


def test_job_detail_se_convierte_en_vacante_cruda_con_prefiltro():
    [v] = list(FuenteMagnetoMCP(ClienteMCPFalso({"1121542": DETALLE}), ["1121542"]).obtener())
    assert (v.id, v.titulo, v.empresa, v.salario_min, v.fecha_publicacion) == (
        "mag-1121542", "Auxiliar Contable", "IMPOCOSER S.A.S.", 2100000, date(2026, 10, 31))
    assert v.prefiltro == ("¿Tienes experiencia con facturación electrónica?",) and v.etiquetas == ("NIIF",)


def test_la_ingesta_guarda_el_prefiltro(db):
    ingerir(FuenteMagnetoMCP(ClienteMCPFalso({"1121542": DETALLE}), ["1121542"]))
    assert Vacante.objects.get(id="mag-1121542").prefiltro == ["¿Tienes experiencia con facturación electrónica?"]


def test_un_429_reintenta_con_espera():
    respuestas = [mock.Mock(status_code=429, headers={"Retry-After": "2"}),
                  mock.Mock(status_code=200, headers={}, **{"json.return_value": {"result": {"structuredContent": DETALLE}}})]
    sesion = mock.Mock(**{"post.side_effect": respuestas})
    with mock.patch("vacantes.fuentes.magneto_mcp.time.sleep") as dormir:
        assert ClienteMCPHttp("token", sesion=sesion).job_detail("1121542")["title"] == "Auxiliar Contable"
    dormir.assert_called_once_with(2)
    llamada = sesion.post.call_args
    assert llamada.kwargs["headers"]["Authorization"] == "Bearer token"
    assert llamada.kwargs["json"]["method"] == "tools/call"


def test_la_fuente_mcp_esta_apagada_por_defecto(db, settings):
    settings.SCOUTLY_MAGNETO_MCP = ""
    with pytest.raises(CommandError, match="términos de uso"):
        call_command("ingerir_vacantes", "--fuente", "magneto-mcp")


def test_el_detalle_muestra_las_preguntas_de_la_empresa(client, db):
    ingerir(FuenteMagnetoMCP(ClienteMCPFalso({"1121542": DETALLE}), ["1121542"]))
    html = client.get(reverse("vacante_detalle", args=["mag-1121542"])).content.decode()
    assert "Preguntas de la empresa" in html and "¿Tienes experiencia con facturación electrónica?" in html
