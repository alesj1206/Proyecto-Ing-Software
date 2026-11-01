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
from vacantes.management.commands.ingerir_vacantes import TERMINOS_POR_DEFECTO
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


def _datos(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def fuente_para(datos: dict) -> FuenteMagnetoDetalle:
    return FuenteMagnetoDetalle(datos.get("terminos") or TERMINOS_POR_DEFECTO,
                                int(datos.get("por_termino") or POR_TERMINO_POR_DEFECTO))


@para_n8n
def importar_vacantes(request):
    if not ingerir_en_segundo_plano(fuente_para(_datos(request))):
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
