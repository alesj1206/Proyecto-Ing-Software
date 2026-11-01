import hmac

from django.conf import settings
from django.http import JsonResponse


def token_invalido(request) -> JsonResponse | None:
    """None si el header X-Scoutly-Token es válido; si no, la respuesta de error. Sin DEBUG, el token de desarrollo
    (conocido, está en el repo) no se acepta."""
    configurado = settings.N8N_SCORING_TOKEN
    if not settings.DEBUG and configurado == settings.N8N_SCORING_TOKEN_DEV_DEFAULT:
        return JsonResponse({"error": "N8N_SCORING_TOKEN no configurado"}, status=503)
    recibido = request.headers.get("X-Scoutly-Token", "")
    if not configurado or not hmac.compare_digest(recibido, configurado):
        return JsonResponse({"error": "token inválido"}, status=401)
    return None
