"""De punta a punta con modelos reales: ingesta → CV por la web → batch con MiniLM → dashboard (spec §6)."""

import time
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.urls import reverse

from cuentas.tests.cvs import pdf_cv
from matching.ia.fastembed import EmbedderFastembed
from matching.services import decidir_para_perfil
from vacantes.fuentes.fixture import FuenteFixture
from vacantes.services import ingerir

DATOS = Path("matching/evaluacion")
LIMITE_DECISION_S = 5.0  # §6: decisión por candidato ≤ 5 s en CPU


@pytest.mark.lento
def test_cv_real_hasta_dashboard(client, usuario, settings):
    settings.SCOUTLY_EMBEDDER = "fastembed"
    ingerir(FuenteFixture(DATOS / "vacantes.json"))
    cv = yaml.safe_load((DATOS / "cvs.yaml").read_text(encoding="utf-8"))["datos_junior"]
    client.force_login(usuario)
    client.post(reverse("onboarding"), {"cv": pdf_cv(nombre=cv["nombre"], contacto=cv["contacto"],
                                                     experiencia=cv["experiencia"], educacion=tuple(cv["educacion"]),
                                                     habilidades=cv["habilidades"])})
    assert "Estamos analizando tu hoja de vida" in client.get(reverse("dashboard")).content.decode()

    call_command("decidir", "--pendientes")
    html = client.get(reverse("dashboard")).content.decode()
    assert "Estamos analizando" not in html and "· solidez" in html and "Cubres" in html

    embedder = EmbedderFastembed()  # el modelo ya cargado: se mide solo la decisión
    inicio = time.perf_counter()
    resumen = decidir_para_perfil(usuario.perfil, embedder)
    segundos = time.perf_counter() - inicio
    print(f"\ndecidir_para_perfil: {resumen.relevantes} relevantes en {segundos:.2f} s")
    assert resumen.relevantes > 0 and segundos <= LIMITE_DECISION_S
