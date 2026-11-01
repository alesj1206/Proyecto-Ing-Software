import base64
import hashlib

import pytest
from cryptography.fernet import Fernet
from django.urls import reverse

from cuentas.models import ConexionMagneto
from cuentas.oauth_magneto import generar_pkce, guardar_token, leer_token


@pytest.fixture(autouse=True)
def clave(settings):
    settings.SCOUTLY_CLAVE_TOKENS = Fernet.generate_key().decode()


def test_el_token_se_guarda_cifrado(usuario):
    guardar_token(usuario, "token-secreto-123", expira_en_s=3600)
    conexion = ConexionMagneto.objects.get(usuario=usuario)
    assert "token-secreto-123" not in conexion.token_cifrado and leer_token(usuario) == "token-secreto-123"


def test_desconectar_borra_el_token(client, usuario, settings):
    settings.SCOUTLY_MAGNETO_MCP = "1"
    guardar_token(usuario, "token-secreto-123", expira_en_s=3600)
    client.force_login(usuario)
    client.post(reverse("desconectar_magneto"))
    assert not ConexionMagneto.objects.exists()


def test_conectar_magneto_apagado_es_404(client, usuario, settings):
    settings.SCOUTLY_MAGNETO_MCP = ""
    client.force_login(usuario)
    assert client.get(reverse("conectar_magneto")).status_code == 404


def test_pkce_challenge_es_s256():
    verificador, desafio = generar_pkce()
    esperado = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    assert desafio == esperado and 43 <= len(verificador) <= 128
