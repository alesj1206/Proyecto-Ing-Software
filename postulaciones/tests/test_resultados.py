import pytest

from matching.models import Decision
from postulaciones.models import Postulacion, ResultadoDecision
from postulaciones.services import cambiar_estado, postular

COBERTURA = [{"texto": "SQL", "tipo": "obligatorio", "origen": "texto", "estado": "cubierto", "similitud": 0.7,
              "evidencia": "Usé SQL"}]


@pytest.fixture
def postulacion(client_con_cv, usuario, vacante_v1):
    postular(usuario.perfil, vacante_v1)
    return Postulacion.objects.get()


def _decision(usuario, vacante):
    return Decision.objects.create(perfil=usuario.perfil, vacante=vacante, accion="POSTULAR", solidez="alta",
                                   motivo_solidez="ok", motivos=["Cubres 1/1"], similitud=0.8, cobertura_pct=100,
                                   version_politica="2026-11-02.2", cobertura=COBERTURA,
                                   restricciones=[{"criterio": "salario", "estado": "cumple", "motivo": "ok"}])


def test_pasar_a_entrevista_registra_el_resultado_con_los_insumos(postulacion, usuario, vacante_v1):
    _decision(usuario, vacante_v1)
    cambiar_estado(postulacion, "entrevista")
    r = ResultadoDecision.objects.get()
    assert (r.resultado, r.accion, r.cobertura_pct, r.version_politica, r.solidez) == (
        "entrevista", "POSTULAR", 100, "2026-11-02.2", "alta")
    assert r.insumos["cobertura"] == COBERTURA and r.insumos["restricciones"][0]["criterio"] == "salario"


def test_en_revision_no_registra_resultado(postulacion, usuario, vacante_v1):
    _decision(usuario, vacante_v1)
    cambiar_estado(postulacion, "en_revision")
    assert not ResultadoDecision.objects.exists()


def test_sin_decision_registra_igual_sin_accion(postulacion):
    cambiar_estado(postulacion, "descartado")
    r = ResultadoDecision.objects.get()
    assert (r.resultado, r.accion, r.insumos) == ("descartado", "", {})


def test_volver_a_entrevista_no_duplica(postulacion, usuario, vacante_v1):
    _decision(usuario, vacante_v1)
    cambiar_estado(postulacion, "entrevista")
    cambiar_estado(postulacion, "entrevista")
    assert ResultadoDecision.objects.count() == 1


def test_resultado_guarda_insumos_para_calibrar(postulacion, usuario, vacante_v1):
    _decision(usuario, vacante_v1)
    cambiar_estado(postulacion, "entrevista")
    insumos = ResultadoDecision.objects.get().insumos
    assert (insumos["similitud"], insumos["con_nota"], insumos["motivos"]) == (0.8, "", ["Cubres 1/1"])
