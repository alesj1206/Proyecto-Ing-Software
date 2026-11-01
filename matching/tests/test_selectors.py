from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone

from cuentas.models import Perfil
from matching import selectors
from matching.models import Decision, FotoDiaria
from vacantes.models import Vacante

HOY = date(2026, 11, 2)


def _req(texto, estado, tipo="obligatorio", evidencia=None):
    return {"texto": texto, "tipo": tipo, "origen": "texto", "estado": estado, "similitud": 0.6, "evidencia": evidencia}


def _decision(perfil, id_, accion, orden=0.5, empresa="ACME", dias=1, cobertura=None, restricciones=None):
    v = Vacante.objects.create(id=id_, titulo=f"Cargo {id_}", empresa=empresa, ubicacion="Medellín",
                               modalidad="Presencial", fecha_publicacion=HOY - timedelta(days=dias), fuente="t",
                               hash_contenido="x")
    return Decision.objects.create(
        perfil=perfil, vacante=v, accion=accion, solidez="alta", motivo_solidez="ok", motivos=[f"motivo {id_}"],
        similitud=0.8, cobertura_pct=75, orden=orden, version_politica="t",
        cobertura=cobertura or [_req("SQL", "cubierto", evidencia="Usé SQL"), _req("Excel", "faltante")],
        restricciones=restricciones or [{"criterio": c, "estado": "cumple", "motivo": "ok"}
                                        for c in ("modalidad", "salario", "ubicacion", "experiencia")])


@pytest.fixture
def perfil(usuario):
    return Perfil.objects.create(usuario=usuario, cv_nombre_archivo="cv.pdf")


def test_plan_de_hoy_una_por_empresa_normalizada(perfil):
    _decision(perfil, "a", "POSTULAR", 0.9, "ACME S.A.S."), _decision(perfil, "b", "POSTULAR", 0.8, "Acme SAS")
    _decision(perfil, "c", "AJUSTAR_CV", 0.7, "Otra Ltda")
    assert [i.vacante.id for i in selectors.plan_de_hoy(perfil, ahora=HOY)] == ["a", "c"]


def test_plan_de_hoy_marca_postular_hoy_antes_de_72h(perfil):
    _decision(perfil, "nueva", "POSTULAR", dias=2, empresa="A"), _decision(perfil, "vieja", "POSTULAR", dias=10, empresa="B")
    marcas = {i.vacante.id: i.postular_hoy for i in selectors.plan_de_hoy(perfil, ahora=HOY)}
    assert marcas == {"nueva": True, "vieja": False}


def test_plan_de_hoy_prefiere_lo_fresco_a_igual_ajuste(perfil):
    _decision(perfil, "vieja", "POSTULAR", 0.8, "A", dias=20), _decision(perfil, "nueva", "POSTULAR", 0.7, "B", dias=1)
    assert selectors.plan_de_hoy(perfil, ahora=HOY)[0].vacante.id == "nueva"


def test_plan_de_hoy_excluye_descartar_y_sin_datos(perfil):
    _decision(perfil, "d", "DESCARTAR", empresa="A"), _decision(perfil, "s", "SIN_DATOS", empresa="B")
    _decision(perfil, "c", "CERRAR_BRECHA", empresa="C")
    assert selectors.plan_de_hoy(perfil, ahora=HOY) == []


def test_item_del_plan_trae_los_campos_del_template_de_v2(perfil):
    _decision(perfil, "a", "POSTULAR")
    [item] = selectors.plan_de_hoy(perfil, ahora=HOY)
    assert (item.score_pct, item.coincidencias, item.razon_principal, item.cubres) == (75, ["SQL"], "motivo a", "1/2")


def test_decisiones_por_accion_en_orden(perfil):
    _decision(perfil, "d", "DESCARTAR"), _decision(perfil, "p1", "POSTULAR", 0.4), _decision(perfil, "p2", "POSTULAR", 0.9)
    grupos = selectors.decisiones_por_accion(perfil)
    assert list(grupos) == ["POSTULAR", "AJUSTAR_CV", "CERRAR_BRECHA", "SIN_DATOS", "DESCARTAR"]
    assert [d.vacante_id for d in grupos["POSTULAR"]] == ["p2", "p1"]


def test_plan_de_aprendizaje_cuenta_frecuencias(perfil):
    for i, faltantes in enumerate([["Docker", "Inglés"], ["docker"], ["Docker", "SQL"]]):
        _decision(perfil, f"c{i}", "CERRAR_BRECHA", cobertura=[_req(f, "faltante") for f in faltantes])
    _decision(perfil, "d", "DESCARTAR", cobertura=[_req("Docker", "faltante")])
    assert selectors.plan_de_aprendizaje(perfil)[0] == ("Docker", 3)


def test_detalle_arma_las_cinco_barras(perfil):
    d = _decision(perfil, "a", "POSTULAR", restricciones=[
        {"criterio": "modalidad", "estado": "parcial", "motivo": "Es híbrida y buscas remoto"},
        {"criterio": "salario", "estado": "sin_datos", "motivo": "No declaraste tu salario mínimo"},
        {"criterio": "ubicacion", "estado": "cumple", "motivo": "Queda en Medellín"},
        {"criterio": "experiencia", "estado": "no_cumple", "motivo": "Pide 3 años"}])
    ctx = selectors.detalle(perfil, d.vacante)
    assert ctx["match"]["score"] == 75 and ctx["match"]["coincidencias"] == ["SQL"]
    assert [c["etiqueta"] for c in ctx["criterios"]] == ["Habilidades", "Experiencia", "Salario", "Modalidad", "Ubicación"]
    salario = ctx["criterios"][2]
    assert (salario["aplica"], salario["es_del_candidato"], salario["razon_no_aplica"]) == (
        False, True, "No declaraste tu salario mínimo")
    assert ctx["criterios"][3]["score_pct"] == 50 and ctx["criterios"][0]["peso_pct"] is None
    assert ctx["requisitos"]["cubiertos"][0]["evidencia"] == "Usé SQL"


def test_detalle_sin_decision_es_none(perfil):
    v = Vacante.objects.create(id="x", titulo="x", empresa="x", ubicacion="x", modalidad="Remoto",
                               fecha_publicacion=HOY, fuente="t", hash_contenido="x")
    assert selectors.detalle(perfil, v) is None


def test_historial_compara_con_la_foto_anterior(perfil):
    _decision(perfil, "a", "POSTULAR"), _decision(perfil, "b", "AJUSTAR_CV")
    FotoDiaria.objects.create(perfil=perfil, fecha=HOY - timedelta(days=1), conteos={},
                              top={"POSTULAR": [{"vacante_id": "a", "cobertura_pct": 60, "orden": 0.5}]})
    FotoDiaria.objects.create(perfil=perfil, fecha=HOY, conteos={}, top={
        "POSTULAR": [{"vacante_id": "a", "cobertura_pct": 75, "orden": 0.9}],
        "AJUSTAR_CV": [{"vacante_id": "b", "cobertura_pct": 50, "orden": 0.4}],
        "DESCARTAR": [{"vacante_id": "a", "cobertura_pct": 10, "orden": 0.1}]})
    ctx = selectors.historial(perfil)
    assert ctx["fecha_sel"] == HOY and ctx["fecha_anterior"] == HOY - timedelta(days=1)
    assert [(r["vacante"].id, r["score_pct"], r["delta_pct"], r["es_nuevo"]) for r in ctx["ranking"]] == [
        ("a", 75, 15, False), ("b", 50, None, True)]


def test_pendiente_de_decision(perfil):
    from matching.services import solicitar_decision

    assert not selectors.pendiente_de_decision(perfil)
    solicitar_decision(perfil)
    assert selectors.pendiente_de_decision(perfil)
