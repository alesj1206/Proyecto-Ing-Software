"""Adaptador de Groq (gratuito) para redactar la explicación de una decisión. Solo recibe campos de criterio: los
insumos los arma `matching.explicaciones.insumos_publicos`, que nunca incluye texto del CV."""

import json
import logging

import requests
from django.conf import settings

URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S = (3, 5)  # conectar + leer: en total una explicación no cuelga la página más de 8 s
# Holgado para 2 o 3 oraciones. La v2 usaba 120, pero ahí algunos modelos devolvían vacío por gastar el tope razonando.
MAX_TOKENS_RESPUESTA = 300
INSTRUCCIONES = (
    "Eres el asistente de Scoutly, una plataforma colombiana de empleo. Recibes la acción que el sistema recomienda "
    "para una vacante y los datos que la producen. Explica en 2 o 3 oraciones, en español claro y sin markdown, por qué "
    "esa acción tiene sentido y qué debería hacer el candidato. Usa solo los datos que recibes; no inventes nada."
)
log = logging.getLogger(__name__)


class RedactorGroq:
    def __init__(self, api_key: str, modelo: str | None = None, timeout: tuple[int, int] = TIMEOUT_S):
        self.api_key, self.modelo, self.timeout = api_key, modelo or settings.SCOUTLY_GROQ_MODELO, timeout

    def redactar(self, insumos: dict) -> str | None:
        try:
            respuesta = requests.post(
                URL, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout,
                json={"model": self.modelo, "temperature": 0.3, "max_tokens": MAX_TOKENS_RESPUESTA, "messages": [
                    {"role": "system", "content": INSTRUCCIONES},
                    {"role": "user", "content": json.dumps(insumos, ensure_ascii=False)}]})
            respuesta.raise_for_status()
            return (respuesta.json()["choices"][0]["message"]["content"] or "").strip() or None
        except (requests.RequestException, KeyError, IndexError, ValueError, TypeError, AttributeError) as error:
            log.warning("Groq no respondió: %s", error)
            return None
