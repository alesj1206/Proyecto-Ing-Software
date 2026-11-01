"""Fachada del decisor (spec §7.2): `decidir_para_perfil` es la única puerta que usan el batch y la API."""

import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from cuentas.models import Perfil
from vacantes.models import Vacante

from .cobertura import cubrir
from .models import Decision, FotoDiaria, SolicitudDecision
from .orden import Ordenador, OrdenSimilitudCobertura
from .politica import POLITICA, Accion, ContextoDecision, Politica, decidir
from .preseleccion import preseleccionar
from .puertos import Embedder
from .restricciones import RESTRICCIONES
from .solidez import calcular_solidez
from .vectores import de_bytes, embeber_perfil

TOP_POR_ACCION_EN_FOTO = 10


@dataclass
class ResumenDecision:
    relevantes: int = 0
    por_accion: dict = field(default_factory=dict)
    ocultas_por_modalidad: int = 0
    segundos: float = 0.0


def solicitar_decision(perfil: Perfil) -> None:
    """Lo llama la web cuando cambian el CV o las expectativas: el batch (`decidir --escuchar`) lo atiende."""
    SolicitudDecision.objects.get_or_create(perfil=perfil)


def _decision(perfil, vacante, similitud, evidencias, matriz_evid, politica) -> Decision:
    requisitos = sorted(vacante.requisito_set.all(), key=lambda r: r.posicion)
    cobertura = cubrir(requisitos, de_bytes(vacante.matriz_requisitos), evidencias, matriz_evid,
                       politica.tau_alto, politica.tau_bajo)
    restricciones = [r.evaluar(perfil, vacante, politica) for r in RESTRICCIONES]
    contexto = ContextoDecision(cobertura, restricciones, requisitos, politica)
    veredicto = decidir(contexto)
    solidez, motivo_solidez = calcular_solidez(contexto, veredicto)
    return Decision(
        perfil=perfil, vacante=vacante, accion=veredicto.accion, con_nota=veredicto.con_nota or "",
        motivos=veredicto.motivos, solidez=solidez, motivo_solidez=motivo_solidez, similitud=similitud,
        cobertura_pct=cobertura.porcentaje, version_politica=politica.version,
        cobertura=[{"texto": r.texto, "tipo": r.tipo, "origen": r.origen, "estado": r.estado,
                    "similitud": r.similitud, "evidencia": r.evidencia} for r in cobertura.requisitos],
        restricciones=[{"criterio": r.criterio, "estado": r.estado, "motivo": r.motivo} for r in restricciones],
    )


def decidir_par(perfil: Perfil, vacante: Vacante, similitud: float, politica: Politica = POLITICA) -> Decision:
    """La decisión para un solo par, sin guardarla (la usa la evaluación)."""
    evidencias = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
    return _decision(perfil, vacante, similitud, evidencias, de_bytes(perfil.matriz_evidencia), politica)


def _guardar(perfil: Perfil, decisiones: list[Decision], hoy: date) -> None:
    anteriores = dict(Decision.objects.filter(perfil=perfil).values_list("vacante_id", "accion"))
    for d in decisiones:
        anterior = anteriores.get(d.vacante_id, "")
        d.accion_anterior = anterior if anterior != d.accion else ""
    Decision.objects.filter(perfil=perfil).exclude(vacante_id__in=[d.vacante_id for d in decisiones]).delete()
    campos = [f.name for f in Decision._meta.concrete_fields if f.name not in ("id", "perfil", "vacante")]
    Decision.objects.bulk_create(decisiones, update_conflicts=True, unique_fields=["perfil", "vacante"],
                                 update_fields=campos)
    top = {}
    for accion in Accion.values:
        de_accion = sorted((d for d in decisiones if d.accion == accion), key=lambda d: -d.orden)
        top[accion] = [{"vacante_id": d.vacante_id, "cobertura_pct": d.cobertura_pct, "orden": d.orden}
                       for d in de_accion[:TOP_POR_ACCION_EN_FOTO]]
    FotoDiaria.objects.update_or_create(perfil=perfil, fecha=hoy, defaults={
        "conteos": dict(Counter(d.accion for d in decisiones)), "top": top})
    SolicitudDecision.objects.filter(perfil=perfil).delete()


def decidir_para_perfil(perfil: Perfil, embedder: Embedder, ordenador: Ordenador | None = None,
                        politica: Politica = POLITICA, hoy: date | None = None) -> ResumenDecision:
    inicio = time.perf_counter()
    embeber_perfil(perfil, embedder)
    preseleccion = preseleccionar(perfil, politica.tau_relevancia)
    similitudes = dict(preseleccion.relevantes)
    vacantes = Vacante.objects.filter(id__in=similitudes).prefetch_related("requisito_set")
    evidencias = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))
    matriz_evid = de_bytes(perfil.matriz_evidencia)
    decisiones = [_decision(perfil, v, similitudes[v.id], evidencias, matriz_evid, politica) for v in vacantes]
    (ordenador or OrdenSimilitudCobertura()).ordenar(perfil, decisiones)
    with transaction.atomic():
        _guardar(perfil, decisiones, hoy or timezone.localdate())
    return ResumenDecision(len(decisiones), dict(Counter(d.accion for d in decisiones)),
                           preseleccion.ocultas_por_modalidad, time.perf_counter() - inicio)
