"""Endpoints que llama n8n (spec §7.4): ingesta → decidir → notificaciones. Ninguno carga modelos: `decidir` solo encola
y el batch (`manage.py decidir --escuchar`) hace el trabajo (§13.4)."""

import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cuentas.models import Perfil
from matching.services import solicitar_decision
from notificaciones.services import generar_notificaciones
from vacantes.fuentes.magneto_detalle import FuenteMagnetoDetalle
from vacantes.fuentes.magneto_detalle import TERMINOS_POR_DEFECTO
from vacantes.services import ingerir_en_segundo_plano

from .autenticacion import token_invalido

POR_TERMINO_POR_DEFECTO = 5


def para_n8n(vista):
    """Solo POST, sin CSRF (no viene de un navegador con sesión) y con el token de n8n."""
    @csrf_exempt
    @require_POST
    @wraps(vista)
    def envoltura(request):
        return token_invalido(request) or vista(request)
    return envoltura


MAX_TERMINOS, MAX_LARGO_TERMINO, MAX_POR_TERMINO = 10, 60, 20


class EntradaInvalida(ValueError):
    pass


def _datos(request) -> dict:
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError as error:
        raise EntradaInvalida("JSON inválido") from error
    if not isinstance(datos, dict):
        raise EntradaInvalida("se esperaba un objeto JSON")
    return datos


def _validar(datos: dict) -> tuple[list[str], int]:
    """Acota lo que n8n puede pedir: el scraping corre con Chromium y no debe durar horas."""
    terminos = datos.get("terminos") or TERMINOS_POR_DEFECTO
    if not (isinstance(terminos, list) and 0 < len(terminos) <= MAX_TERMINOS
            and all(isinstance(t, str) and 0 < len(t) <= MAX_LARGO_TERMINO for t in terminos)):
        raise EntradaInvalida(f"terminos: lista de 1 a {MAX_TERMINOS} textos de hasta {MAX_LARGO_TERMINO} caracteres")
    try:
        por_termino = int(datos.get("por_termino") or POR_TERMINO_POR_DEFECTO)
    except (TypeError, ValueError) as error:
        raise EntradaInvalida("por_termino debe ser un número") from error
    return terminos, min(max(por_termino, 1), MAX_POR_TERMINO)


def fuente_para(datos: dict) -> FuenteMagnetoDetalle:
    return FuenteMagnetoDetalle(*_validar(datos))


@para_n8n
def importar_vacantes(request):
    try:
        datos = _datos(request)
        _validar(datos)
    except EntradaInvalida as error:
        return JsonResponse({"error": str(error)}, status=400)
    if not ingerir_en_segundo_plano(fuente_para(datos)):
        return JsonResponse({"error": "ya hay una ingesta en curso"}, status=409)
    return JsonResponse({"estado": "ingesta iniciada"}, status=202)


@para_n8n
def decidir(request):
    perfiles = Perfil.objects.exclude(cv_nombre_archivo="")
    for perfil in perfiles:
        solicitar_decision(perfil)
    return JsonResponse({"encolados": len(perfiles)}, status=202)


@para_n8n
def notificar(request):
    resumen = generar_notificaciones()
    return JsonResponse({"creadas": resumen.creadas, "correos": resumen.correos})
