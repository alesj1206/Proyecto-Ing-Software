"""Fusión de POSTULAR y AJUSTAR_CV (docs/exploracion/2026-11-02-mejoras-decisor.md), activa desde la política
2026-11-05.1. El detalle que ofrece el Taller lo cubre test_taller."""

from dataclasses import replace
from types import SimpleNamespace as N


from matching.cobertura import Cobertura
from matching.politica import POLITICA, Accion, ContextoDecision, decidir

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


def test_la_politica_vigente_fusiona():
    assert decidir(ContextoDecision(Cobertura(PARCIAL), [ok()], [N(origen="texto")] * 3, POLITICA)).accion == Accion.POSTULAR
