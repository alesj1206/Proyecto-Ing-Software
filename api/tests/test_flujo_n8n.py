"""El día completo como lo orquesta n8n: ingesta → decidir (encola) → batch → notificaciones, y luego el candidato
mueve la postulación a entrevista y queda el resultado ligado a la decisión."""

import json

from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from matching.models import Decision
from matching.tests.test_decidir import VACANTES, _perfil
from notificaciones.models import Notificacion
from postulaciones.models import Postulacion, ResultadoDecision
from postulaciones.services import cambiar_estado, postular
from vacantes.models import Vacante
from vacantes.tests.test_ingesta import FuenteEnMemoria, cruda

TOKEN = "token-de-prueba-n8n"


def _post(client, nombre):
    return client.post(reverse(nombre), data="{}", content_type="application/json", HTTP_X_SCOUTLY_TOKEN=TOKEN)


def test_flujo_diario_como_n8n(client, usuario, settings, monkeypatch):
    settings.N8N_SCORING_TOKEN = TOKEN
    monkeypatch.setattr("vacantes.services.lanzar_hilo", lambda funcion: funcion())
    monkeypatch.setattr("api.views.fuente_para", lambda datos: FuenteEnMemoria([cruda("vpost", VACANTES["vpost"])]))
    perfil = _perfil(usuario, evidencia=["Reportes de ventas en Excel", "Atención de clientes en tienda"],
                     contacto="ana@correo-ficticio.co")

    assert _post(client, "api_importar_vacantes").status_code == 202
    assert _post(client, "api_decidir").json() == {"encolados": 1}
    call_command("decidir", "--pendientes")  # lo que hace `decidir --escuchar` en producción
    assert Decision.objects.get(perfil=perfil, vacante_id="vpost").accion == "POSTULAR"

    assert _post(client, "api_generar_notificaciones").json() == {"creadas": 1, "correos": 1}
    assert Notificacion.objects.filter(perfil=perfil).count() == 1 and len(mail.outbox) == 1

    postular(perfil, Vacante.objects.get(id="vpost"))
    cambiar_estado(Postulacion.objects.get(perfil=perfil), "entrevista")
    resultado = ResultadoDecision.objects.get()
    assert (resultado.resultado, resultado.accion) == ("entrevista", "POSTULAR")
