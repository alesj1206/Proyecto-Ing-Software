import pytest

from spike.fase0.reporte import elegir, veredictos

BASE = {"unidades_por_s": 100, "docs_por_s": 20, "segundos_indice_hnsw": 600,
        "ms_busqueda_p95": 80, "ms_cobertura": 150, "pares_por_s": 30, "exactitud": 0.9}


def test_veredicto_con_valores_conocidos():
    v = {x["umbral"]: x for x in veredictos(BASE)}
    assert v["carga_inicial_cpu_h"]["medido"] == pytest.approx(4.83, abs=0.01)
    assert v["carga_inicial_cpu_h"]["cumple"] is True
    assert v["decision_candidato_s"]["medido"] == pytest.approx(1.563, abs=0.01)
    assert v["pagina_s"]["cumple"] is True
    assert v["delta_diario_min"]["medido"] == pytest.approx(7.0, abs=0.01)
    assert v["calidad"]["cumple"] is True


def test_no_cumple_si_lento():
    r = BASE | {"unidades_por_s": 20, "docs_por_s": 2, "pares_por_s": 5}
    v = {x["umbral"]: x for x in veredictos(r)}
    assert v["carga_inicial_cpu_h"]["cumple"] is False
    assert v["pagina_s"]["cumple"] is False


def test_lectura_de_requisitos_cuenta_en_la_decision():
    v = {x["umbral"]: x for x in veredictos(BASE | {"ms_fetch_requisitos_3000": 1000})}
    assert v["decision_candidato_s"]["medido"] == pytest.approx(2.563, abs=0.01)


def test_gpu_solo_si_se_midio():
    assert "carga_inicial_gpu_h" not in {x["umbral"] for x in veredictos(BASE)}
    v = {x["umbral"]: x for x in veredictos(BASE | {"gpu_unidades_por_s": 1000, "gpu_docs_por_s": 200})}
    assert v["carga_inicial_gpu_h"]["cumple"] is True


def test_elegir_mejor_calidad_y_desempate_por_velocidad():
    cands = [
        {"nombre": "lento_bueno", "exactitud": 0.95, "unidades_por_s": 50, "cumple_todo": True},
        {"nombre": "rapido_casi", "exactitud": 0.94, "unidades_por_s": 500, "cumple_todo": True},
        {"nombre": "excelente_pero_no_cumple", "exactitud": 0.99, "unidades_por_s": 10, "cumple_todo": False},
    ]
    assert elegir(cands)["nombre"] == "rapido_casi"
    assert elegir([c | {"cumple_todo": False} for c in cands]) is None


def test_carga_sin_documentos_largos_usa_solo_unidades():
    r = {k: v for k, v in BASE.items() if k != "docs_por_s"}
    v = {x["umbral"]: x for x in veredictos(r)}
    # 120k × (9 requisitos + 1 título) / 100 por s + 600 s de índice
    assert v["carga_inicial_cpu_h"]["medido"] == pytest.approx((1_200_000 / 100 + 600) / 3600, abs=0.01)
    assert v["delta_diario_min"]["medido"] == pytest.approx(3_000 * 10 / 100 / 60, abs=0.01)


def test_desempate_prefiere_recall_y_mejor_reranker():
    base = {"exactitud": 0.9, "unidades_por_s": 400, "cumple_todo": True, "pares_por_s": 60}
    cands = [
        base | {"nombre": "hnsw", "recall": 0.93, "calidad_rer": 0.95},
        base | {"nombre": "exacta_jina", "recall": 1.0, "calidad_rer": 0.90, "pares_por_s": 178},
        base | {"nombre": "exacta_bge", "recall": 1.0, "calidad_rer": 0.95},
    ]
    assert elegir(cands)["nombre"] == "exacta_bge"
