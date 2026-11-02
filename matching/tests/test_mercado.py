import pytest
from django.urls import reverse

from matching.models import FotoDiaria
from matching.services import decidir_para_perfil
from vacantes.models import Vacante

from .test_decidir import M, TODAS, _perfil, catalogo  # noqa: F401 (fixture)



@pytest.fixture
def sin_corte_de_cercania(monkeypatch):
    """El embedder falso da similitudes bajas; estas pruebas miran otra cosa que el corte (test_revision_fase4)."""
    monkeypatch.setattr("matching.services.SIMILITUD_CERCANA", 0.0)

def test_mercado_excluye_descartar(usuario, catalogo, sin_corte_de_cercania):
    Vacante.objects.filter(id="vpost").update(salario_min=2000000, salario_max=3000000, empresa="Andina")
    Vacante.objects.filter(id="vdesc").update(salario_min=9000000, salario_max=9900000)  # DESCARTAR: no cuenta
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, M, politica=TODAS)
    m = FotoDiaria.objects.get(perfil=perfil).mercado
    assert m["relevantes"] == 4 and (m["salario_min"], m["salario_max"]) == (2000000, 3000000)
    assert m["empresas"][0] == ["ACME", 3]


def test_mercado_sin_salarios(usuario, catalogo):
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, M, politica=TODAS)
    m = FotoDiaria.objects.get(perfil=perfil).mercado
    assert (m["salario_min"], m["salario_max"]) == (None, None)


def test_la_tarjeta_aparece_en_el_dashboard(client, usuario, catalogo, sin_corte_de_cercania):
    Vacante.objects.filter(id="vpost").update(salario_min=2000000, salario_max=3000000)
    perfil = _perfil(usuario)
    decidir_para_perfil(perfil, M, politica=TODAS)
    client.force_login(usuario)
    html = client.get(reverse("dashboard")).content.decode()
    assert "Tu mercado" in html and "4 vacantes relevantes para ti" in html and "$ 2.000.000 a $ 3.000.000" in html
