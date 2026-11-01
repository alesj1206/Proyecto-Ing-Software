"""OAuth 2.1 con PKCE para conectar la cuenta de Magneto del candidato (B1). Las URLs y el client_id salen del entorno;
el token se guarda cifrado con Fernet (SCOUTLY_CLAVE_TOKENS) y nunca en texto plano."""

import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone

from .models import ConexionMagneto, Usuario

ALCANCE = "candidate.job_detail"  # solo lectura: B2 (postular) queda fuera


def _fernet() -> Fernet:
    if not settings.SCOUTLY_CLAVE_TOKENS:
        raise RuntimeError("Falta SCOUTLY_CLAVE_TOKENS para cifrar los tokens de Magneto")
    return Fernet(settings.SCOUTLY_CLAVE_TOKENS.encode())


def generar_pkce() -> tuple[str, str]:
    verificador = secrets.token_urlsafe(64)[:96]
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    return verificador, desafio


def url_autorizacion(estado: str, desafio: str, redirigir_a: str) -> str:
    return settings.SCOUTLY_MAGNETO_OAUTH_AUTORIZAR + "?" + urlencode({
        "response_type": "code", "client_id": settings.SCOUTLY_MAGNETO_OAUTH_CLIENT_ID, "redirect_uri": redirigir_a,
        "scope": ALCANCE, "state": estado, "code_challenge": desafio, "code_challenge_method": "S256"})


def intercambiar_codigo(codigo: str, verificador: str, redirigir_a: str) -> tuple[str, int]:
    respuesta = requests.post(settings.SCOUTLY_MAGNETO_OAUTH_TOKEN, timeout=20, data={
        "grant_type": "authorization_code", "code": codigo, "code_verifier": verificador,
        "client_id": settings.SCOUTLY_MAGNETO_OAUTH_CLIENT_ID, "redirect_uri": redirigir_a})
    respuesta.raise_for_status()
    datos = respuesta.json()
    return datos["access_token"], int(datos.get("expires_in", 3600))


def guardar_token(usuario: Usuario, token: str, expira_en_s: int) -> None:
    ConexionMagneto.objects.update_or_create(usuario=usuario, defaults={
        "token_cifrado": _fernet().encrypt(token.encode()).decode(),
        "expira_en": timezone.now() + timedelta(seconds=expira_en_s)})


def leer_token(usuario: Usuario) -> str | None:
    conexion = ConexionMagneto.objects.filter(usuario=usuario, expira_en__gt=timezone.now()).first()
    return _fernet().decrypt(conexion.token_cifrado.encode()).decode() if conexion else None
