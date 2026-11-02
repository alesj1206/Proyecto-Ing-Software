import sys
from datetime import date

import pytest
from django.core.management import call_command
from django.urls import reverse

from cuentas.models import EvidenciaPerfil, Perfil
from matching.ia.fakes import EmbedderFalso, ReordenadorFalso
from matching.models import Decision, FotoDiaria, SolicitudDecision
from matching.orden import OrdenConReranker
from matching.politica import Politica
from matching.services import decidir_para_perfil, solicitar_decision
from matching.vectores import embeber_vacantes
from vacantes.models import Vacante
from vacantes.services import ingerir
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

E = EmbedderFalso()
# Estos tests miden la cadena completa, no la relevancia: con banda parcial y sin fusión, para que existan las cinco
# acciones (la política vigente, sin banda parcial, nunca produce AJUSTAR_CV).
TODAS = Politica(tau_relevancia=0.0, tau_alto=0.45, tau_bajo=0.35, fusionar_ajustar=False)
EVIDENCIA = ["Reportes de ventas en Excel", "Atención de clientes en tienda", "Excel tablas compartidas equipo"]
VACANTES = {
    "vpost": "Requisitos:\n- Reportes de ventas en Excel\n- Atención de clientes en tienda",
    "vajuste": "Requisitos:\n- Reportes de ventas en Excel\n- Excel tablas dinamicas macros avanzadas",
    "vbrecha": "Requisitos:\n- Reportes de ventas en Excel\n- Docker Kubernetes despliegue",
    "vdesc": "Requisitos:\n- Reportes de ventas en Excel\n- Docker Kubernetes\n- Python Django\n- Linux redes",
    "vsin": "Importante empresa te invita a unirte.",
}


def _perfil(usuario, evidencia=EVIDENCIA, **expectativas):
    perfil = Perfil.objects.create(usuario=usuario, cv_nombre_archivo="cv.pdf", **expectativas)
    for i, texto in enumerate(evidencia):
        EvidenciaPerfil.objects.create(perfil=perfil, texto=texto, seccion="experiencia", posicion=i)
    return perfil


@pytest.fixture
def catalogo(db):
    ingerir(FuenteEnMemoria([cruda(i, t) for i, t in VACANTES.items()]))
    embeber_vacantes(E)


def _acciones(perfil):
    return dict(Decision.objects.filter(perfil=perfil).values_list("vacante_id", "accion"))


def test_decide_las_cinco_acciones(usuario, catalogo):
    perfil = _perfil(usuario)
    resumen = decidir_para_perfil(perfil, E, politica=TODAS)
    assert _acciones(perfil) == {"vpost": "POSTULAR", "vajuste": "AJUSTAR_CV", "vbrecha": "CERRAR_BRECHA",
                                 "vdesc": "DESCARTAR", "vsin": "SIN_DATOS"}
    assert resumen.relevantes == 5 and resumen.por_accion["POSTULAR"] == 1
    d = Decision.objects.get(perfil=perfil, vacante_id="vajuste")
    assert d.version_politica == TODAS.version and d.solidez in ("alta", "media", "baja") and d.motivo_solidez
    parcial = next(r for r in d.cobertura if r["estado"] == "parcial")
    assert parcial["evidencia"] == "Excel tablas compartidas equipo"


def test_redecidir_actualiza_y_guarda_accion_anterior(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS)
    EvidenciaPerfil.objects.create(perfil=perfil, texto="Docker Kubernetes despliegue", seccion="experiencia", posicion=9)
    decidir_para_perfil(perfil, E, politica=TODAS)
    d = Decision.objects.get(perfil=perfil, vacante_id="vbrecha")
    assert (d.accion_anterior, d.accion) == ("CERRAR_BRECHA", "POSTULAR")


def test_las_vacantes_que_dejan_de_ser_relevantes_se_borran(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS)
    Vacante.objects.filter(id="vpost").update(activa=False)
    decidir_para_perfil(perfil, E, politica=TODAS)
    assert "vpost" not in _acciones(perfil)


def test_un_salario_bajo_descarta_con_su_motivo(usuario, catalogo):
    Vacante.objects.filter(id="vpost").update(salario_max=1000000)
    perfil = _perfil(usuario, exp_salario_min=3000000)
    decidir_para_perfil(perfil, E, politica=TODAS)
    d = Decision.objects.get(perfil=perfil, vacante_id="vpost")
    assert d.accion == "DESCARTAR" and "Ofrece $ 1.000.000" in d.motivos[0]


def test_la_foto_diaria_es_una_por_dia(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS, hoy=date(2026, 11, 2))
    decidir_para_perfil(perfil, E, politica=TODAS, hoy=date(2026, 11, 2))
    decidir_para_perfil(perfil, E, politica=TODAS, hoy=date(2026, 11, 3))
    foto = FotoDiaria.objects.get(perfil=perfil, fecha=date(2026, 11, 3))
    assert FotoDiaria.objects.count() == 2 and foto.conteos["POSTULAR"] == 1
    assert foto.top["POSTULAR"][0]["vacante_id"] == "vpost"


def test_decidir_atiende_la_solicitud(usuario, catalogo):
    perfil = _perfil(usuario)
    solicitar_decision(perfil)
    decidir_para_perfil(perfil, E, politica=TODAS)
    assert not SolicitudDecision.objects.exists()


def test_cargar_cv_encola_sin_cargar_modelos(client, usuario, monkeypatch):
    from cuentas.tests.cvs import pdf_cv

    monkeypatch.delitem(sys.modules, "matching.ia.fastembed", raising=False)
    client.force_login(usuario)
    client.post(reverse("onboarding"), {"cv": pdf_cv()})
    client.post(reverse("expectativas"), {"exp_modalidad": "Remoto"})
    assert SolicitudDecision.objects.filter(perfil__usuario=usuario).count() == 1
    assert "matching.ia.fastembed" not in sys.modules


def test_comando_pendientes_atiende_la_cola(usuario, catalogo, capsys):
    perfil = _perfil(usuario, evidencia=["Reportes de ventas en Excel", "Atención de clientes en tienda"])
    solicitar_decision(perfil)
    call_command("decidir", "--pendientes")
    assert not SolicitudDecision.objects.exists() and Decision.objects.filter(perfil=perfil).exists()


def test_vacante_sin_vector_se_embebe_antes_de_decidir(usuario, catalogo):
    perfil = _perfil(usuario, evidencia=["Reportes de ventas en Excel", "Atención de clientes en tienda"])
    ingerir(FuenteEnMemoria([cruda("vnueva", VACANTES["vpost"])]))  # ingerida después: sin vector
    call_command("decidir", "--todos")
    assert Decision.objects.filter(perfil=perfil, vacante_id="vnueva").exists()


def test_orden_por_similitud_y_cobertura(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS)
    for d in Decision.objects.filter(perfil=perfil):
        assert d.orden == pytest.approx(d.similitud * d.cobertura_pct / 100, abs=1e-6)


def test_reranker_solo_reordena_la_primera_pagina(usuario, db):
    textos = {f"v{i:02d}": "Requisitos:\n- Reportes de ventas en Excel\n- Atención de clientes en tienda"
              for i in range(22)}
    ingerir(FuenteEnMemoria([cruda(i, t, titulo=("Reportes ventas Excel" if i == "v21" else f"Cargo {i}"))
                             for i, t in textos.items()]))
    embeber_vacantes(E)
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, OrdenConReranker(ReordenadorFalso()), politica=TODAS)
    con_relevancia = Decision.objects.filter(perfil=perfil, relevancia__isnull=False)
    assert con_relevancia.count() == 20


# --- no reescribir lo que no cambió (docs/exploracion/2026-11-02-eficiencia.md, propuesta 1) -------------------------

def _escrituras(perfil):
    return dict(Decision.objects.filter(perfil=perfil).values_list("vacante_id", "fecha_decision"))


def test_redecidir_sin_cambios_no_reescribe_ninguna_decision(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS)
    decidir_para_perfil(perfil, E, politica=TODAS)  # deja accion_anterior igual a la acción
    antes = _escrituras(perfil)
    decidir_para_perfil(perfil, E, politica=TODAS)
    assert _escrituras(perfil) == antes


def test_solo_se_reescribe_la_decision_que_cambio(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS)
    decidir_para_perfil(perfil, E, politica=TODAS)
    antes = _escrituras(perfil)
    EvidenciaPerfil.objects.create(perfil=perfil, texto="Docker Kubernetes despliegue", seccion="experiencia", posicion=9)
    decidir_para_perfil(perfil, E, politica=TODAS)
    despues = _escrituras(perfil)
    assert despues["vbrecha"] > antes["vbrecha"]
    assert Decision.objects.get(perfil=perfil, vacante_id="vbrecha").accion == "POSTULAR"


def test_un_cambio_de_contenido_sin_cambio_de_accion_se_reescribe(usuario, catalogo):
    from dataclasses import replace

    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, E, politica=TODAS)
    decidir_para_perfil(perfil, E, politica=replace(TODAS, version="otra"))
    assert set(Decision.objects.filter(perfil=perfil).values_list("version_politica", flat=True)) == {"otra"}
