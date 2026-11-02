"""Exploración: fusionar POSTULAR y AJUSTAR_CV (docs/exploracion/2026-11-02-mejoras-decisor.md). Apagada por defecto."""

from dataclasses import replace
from types import SimpleNamespace as N

from django.urls import reverse

from matching.cobertura import Cobertura
from matching.models import Decision
from matching.politica import POLITICA, Accion, ContextoDecision, decidir
from matching.selectors import detalle

from .test_politica import ctx, ok, r

PARCIAL = [r("SQL", "cubierto"), r("Excel", "cubierto"), r("Power BI", "parcial", evidencia="Hice tableros")]


def test_sin_fusion_sigue_ajustar_cv():
    assert decidir(ctx(PARCIAL)).accion == Accion.AJUSTAR_CV


def test_con_fusion_es_postular_con_lo_que_hay_que_resaltar():
    contexto = ContextoDecision(Cobertura(PARCIAL), [ok()], [N(origen="texto")] * 3,
                                replace(POLITICA, fusionar_ajustar=True))
    veredicto = decidir(contexto)
    assert veredicto.accion == Accion.POSTULAR and veredicto.con_nota.startswith("Resalta en tu hoja de vida")
    assert "Power BI" in veredicto.con_nota


def test_el_detalle_ofrece_el_taller_si_hay_algo_que_resaltar(client_con_cv, usuario, vacante_v1, monkeypatch):
    monkeypatch.setattr("matching.politica.POLITICA", replace(POLITICA, fusionar_ajustar=True))
    cobertura = [{"texto": "Power BI", "tipo": "obligatorio", "origen": "texto", "estado": "parcial",
                  "similitud": 0.4, "evidencia": "Hice tableros"}]
    Decision.objects.create(perfil=usuario.perfil, vacante=vacante_v1, accion="POSTULAR", solidez="media",
                            motivo_solidez="ok", motivos=["Cubres 1/1"], similitud=0.8, cobertura_pct=50,
                            version_politica="t", cobertura=cobertura, restricciones=[],
                            con_nota="Resalta en tu hoja de vida: Power BI")
    assert detalle(usuario.perfil, vacante_v1)["ofrece_taller"]
    assert reverse("taller", args=[vacante_v1.id]) in client_con_cv.get(reverse("vacante_detalle",
                                                                                 args=[vacante_v1.id])).content.decode()
