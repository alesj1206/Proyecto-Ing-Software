"""benchmark_escala (spec §6): nunca contra la base real, datos sintéticos reproducibles y un informe honesto."""

import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from matching.benchmark.medir import UMBRALES, Medicion, informe_markdown
from matching.benchmark.sintetico import FuenteSintetica

PLANTILLAS = json.loads(Path("matching/evaluacion/vacantes.json").read_text(encoding="utf-8"))


def test_se_niega_fuera_de_bench(db):
    with pytest.raises(CommandError, match="_bench"):
        call_command("benchmark_escala", vacantes=10, muestra=5, candidatos=1)


def test_fuente_sintetica_es_determinista_y_variada():
    una = list(FuenteSintetica(PLANTILLAS, 200, semilla=7).obtener())
    otra = list(FuenteSintetica(PLANTILLAS, 200, semilla=7).obtener())
    assert una == otra and len(una) == 200 and len({v.id for v in una}) == 200
    assert len({v.titulo for v in una}) >= 150
    assert all(v.id.startswith("syn-") and "@" not in v.texto_completo for v in una)
    assert all("Requisitos" in v.texto_completo for v in una)


def test_informe_separa_medido_de_proyectado():
    mediciones = [Medicion("delta_diario_min", 3000, 240.0, "medido"),
                  Medicion("carga_inicial_cpu_h", 120000, 9600.0, "proyectado"),
                  Medicion("decision_candidato_s", 11, 6.0, "medido")]
    texto = informe_markdown(mediciones, {"cpu": "x"})
    filas = {f.split("|")[1].strip(): f for f in texto.splitlines() if f.startswith("| ") and "etapa" not in f}
    assert "medido" in filas["delta_diario_min"] and "sí" in filas["delta_diario_min"]  # 4 min ≤ 15
    assert "proyectado" in filas["carga_inicial_cpu_h"] and "sí" in filas["carga_inicial_cpu_h"]  # 2,7 h ≤ 8
    assert "no" in filas["decision_candidato_s"].split("|")[-2]  # 6 s > 5
    assert set(UMBRALES) >= {"delta_diario_min", "carga_inicial_cpu_h", "decision_candidato_s"}


def test_corrida_minima_de_punta_a_punta(db, embedder_falso, monkeypatch, tmp_path):
    from django.db import connection
    monkeypatch.setitem(connection.settings_dict, "NAME", "prueba_bench")
    salida = tmp_path / "BENCHMARK.md"
    call_command("benchmark_escala", vacantes=60, muestra=20, candidatos=2, salida=salida)
    texto = salida.read_text(encoding="utf-8")
    for etapa in ("delta_diario_min", "carga_inicial_cpu_h", "carga_masiva_min", "decision_candidato_s"):
        assert f"| {etapa} |" in texto
    from vacantes.models import Vacante
    assert Vacante.objects.filter(id__startswith="syn-").count() == 60


def test_cada_vacante_sintetica_es_de_un_area():
    """Los requisitos de una vacante vienen de una misma vacante real (un catálogo real está agrupado por área)."""
    fuente = FuenteSintetica(PLANTILLAS, 50, semilla=3)
    for v in fuente.obtener():
        lineas = [l[2:] for l in v.texto_completo.splitlines() if l.startswith("- ")]
        plantilla = fuente.plantilla_de[v.id]
        propios = sum(any(r.lower() in l.lower() for r in fuente.requisitos_de[plantilla]) for l in lineas)
        assert propios >= len(lineas) - 1


def test_etapa_sin_umbral_muestra_guion():
    texto = informe_markdown([Medicion("carga_masiva_min", 10, 60.0, "medido")], {})
    fila = [f for f in texto.splitlines() if f.startswith("| carga_masiva_min")][0]
    assert "None" not in fila and fila.split("|")[4].strip() == "—"
