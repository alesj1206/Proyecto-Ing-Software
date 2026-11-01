from spike.fase0.textos import documentos_vacante, unidades_evidencia, unidades_requisito


def test_deterministico_y_tamanos():
    assert unidades_requisito(50, 1) == unidades_requisito(50, 1)
    docs = documentos_vacante(200, 2)
    assert len(docs) == 200 and all(300 <= len(d) <= 2500 for d in docs)
    assert all(5 <= len(u.split()) <= 25 for u in unidades_requisito(200, 3))


def test_variedad():
    assert len(set(unidades_requisito(1000, 4))) >= 900


def test_evidencia_es_distinta_de_requisito():
    assert unidades_evidencia(30, 5) != unidades_requisito(30, 5)
    assert all(5 <= len(u.split()) <= 25 for u in unidades_evidencia(200, 6))


def test_resumenes_cortos_con_titulo_y_requisitos():
    from spike.fase0.textos import resumenes_vacante

    rs = resumenes_vacante(200, 7)
    assert rs == resumenes_vacante(200, 7)
    assert all(150 <= len(r) <= 700 for r in rs)
    assert all(";" in r for r in rs)
