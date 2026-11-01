"""B1 (spec §13.3): `candidate.job_detail` del MCP oficial de candidatos de Magneto, detrás del mismo puerto que el
scraping. Trae el texto completo y las preguntas de prefiltro. APAGADO por defecto (`SCOUTLY_MAGNETO_MCP`) hasta que el
equipo revise los términos de uso. Solo lectura: no hay job_apply ni job_applications.

El formato de la respuesta (title, company, location, description, skills, prefilter…) es el documentado por Magneto
para la herramienta; si al activarlo difiere, solo cambia `_a_vacante`."""

import logging
import time
from collections.abc import Iterator
from datetime import date
from typing import Protocol

import requests
from django.conf import settings

from . import VacanteCruda

MAX_REINTENTOS = 3
ESPERA_POR_DEFECTO_S = 2
TIMEOUT_S = 20
log = logging.getLogger(__name__)


class ClienteMCP(Protocol):
    def job_detail(self, vacante_id: str) -> dict: ...


class ClienteMCPHttp:
    """JSON-RPC `tools/call` sobre HTTP con el token OAuth del candidato. Respeta los 429 con Retry-After."""

    def __init__(self, token: str, url: str | None = None, sesion=None):
        self.token, self.url = token, url or settings.SCOUTLY_MAGNETO_MCP_URL
        self.sesion = sesion or requests.Session()

    def job_detail(self, vacante_id: str) -> dict:
        cuerpo = {"jsonrpc": "2.0", "id": vacante_id, "method": "tools/call",
                  "params": {"name": "candidate.job_detail", "arguments": {"id": vacante_id}}}
        for intento in range(MAX_REINTENTOS + 1):
            respuesta = self.sesion.post(self.url, json=cuerpo, timeout=TIMEOUT_S,
                                         headers={"Authorization": f"Bearer {self.token}",
                                                  "Accept": "application/json"})
            if respuesta.status_code == 429 and intento < MAX_REINTENTOS:
                time.sleep(int(respuesta.headers.get("Retry-After", ESPERA_POR_DEFECTO_S)))
                continue
            respuesta.raise_for_status()
            return respuesta.json()["result"]["structuredContent"]
        raise RuntimeError("Magneto sigue respondiendo 429")


class ClienteMCPFalso:
    def __init__(self, respuestas: dict[str, dict]):
        self.respuestas = respuestas

    def job_detail(self, vacante_id: str) -> dict:
        return self.respuestas[vacante_id]


def _a_vacante(d: dict) -> VacanteCruda:
    salario = d.get("salary") or {}
    return VacanteCruda(
        id=f"mag-{d['id']}", titulo=d["title"], empresa=d.get("company", ""), ubicacion=d.get("location", ""),
        modalidad=d.get("modality", ""), texto_completo=d.get("description", ""),
        etiquetas=tuple(d.get("skills", [])), url=d.get("url", ""),
        fecha_publicacion=date.fromisoformat(d["publishedAt"][:10]),
        salario_min=salario.get("min"), salario_max=salario.get("max"),
        prefiltro=tuple(p["question"] for p in d.get("prefilter", []) if p.get("question")))


class FuenteMagnetoMCP:
    nombre = "magneto-mcp"

    def __init__(self, cliente: ClienteMCP, ids: list[str]):
        self.cliente, self.ids = cliente, ids

    def obtener(self) -> Iterator[VacanteCruda]:
        for vacante_id in self.ids:
            try:
                yield _a_vacante(self.cliente.job_detail(vacante_id))
            except Exception:  # una vacante que falla no corta la ingesta
                log.exception("job_detail falló para %s", vacante_id)
