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
NUEVA = "NUEVA"  # accion_anterior de una vacante que recién entra al conjunto relevante (spec §5.7)


@dataclass
class ResumenDecision:
    relevantes: int = 0
    por_accion: dict = field(default_factory=dict)
    ocultas_por_modalidad: int = 0
    segundos: float = 0.0


def solicitar_decision(perfil: Perfil) -> None:
    """Lo llama la web cuando cambian el CV o las expectativas: el batch (`decidir --escuchar`) lo atiende. Refresca la
    fecha para que una solicitud hecha mientras el batch decide no se borre al terminar."""
    SolicitudDecision.objects.update_or_create(perfil=perfil, defaults={"creada_en": timezone.now(), "intentos": 0})


def _decision(perfil, vacante, similitud, evidencias, matriz_evid, politica) -> Decision | None:
    requisitos = sorted(vacante.requisito_set.all(), key=lambda r: r.posicion)
    matriz_req = de_bytes(vacante.matriz_requisitos)
    if len(matriz_req) != len(requisitos) or len(matriz_evid) != len(evidencias):
        return None  # vectores desalineados con el texto: se decide en la próxima corrida, ya re-embebida
    cobertura = cubrir(requisitos, matriz_req, evidencias, matriz_evid, politica.tau_alto, politica.tau_bajo)
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


TOP_EMPRESAS = 3


def _mercado(decisiones: list[Decision]) -> dict:
    """Sobre las relevantes que no son DESCARTAR: cuántas, el rango de salarios y las empresas que más publican."""
    utiles = [d.vacante for d in decisiones if d.accion != Accion.DESCARTAR]
    minimos = [v.salario_min for v in utiles if v.salario_min]
    maximos = [v.salario_max for v in utiles if v.salario_max]
    empresas = Counter(v.empresa for v in utiles if v.empresa).most_common(TOP_EMPRESAS)
    return {"relevantes": len(utiles), "salario_min": min(minimos, default=None),
            "salario_max": max(maximos, default=None), "empresas": [list(e) for e in empresas]}


def _guardar(perfil: Perfil, decisiones: list[Decision], hoy: date, ocultas: int, inicio) -> None:
    anteriores = {v: (a, c) for v, a, c in Decision.objects.filter(perfil=perfil)
                  .values_list("vacante_id", "accion", "cambio_en")}
    for d in decisiones:
        accion_previa, cambio_previo = anteriores.get(d.vacante_id, (NUEVA, None))
        d.accion_anterior = accion_previa
        d.cambio_en = cambio_previo if accion_previa == d.accion and cambio_previo else inicio
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
        "conteos": dict(Counter(str(d.accion) for d in decisiones)), "top": top, "ocultas_por_modalidad": ocultas,
        "mercado": _mercado(decisiones)})
    SolicitudDecision.objects.filter(perfil=perfil, creada_en__lte=inicio).delete()  # las nuevas se quedan


def decidir_para_perfil(perfil: Perfil, embedder: Embedder, ordenador: Ordenador | None = None,
                        politica: Politica = POLITICA, hoy: date | None = None) -> ResumenDecision:
    inicio, reloj = timezone.now(), time.perf_counter()
    evidencias = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))  # se leen una vez
    embeber_perfil(perfil, embedder, evidencias)
    preseleccion = preseleccionar(perfil, politica.tau_relevancia)
    similitudes = dict(preseleccion.relevantes)
    vacantes = Vacante.objects.filter(id__in=similitudes).prefetch_related("requisito_set")
    matriz_evid = de_bytes(perfil.matriz_evidencia)
    decisiones = [d for v in vacantes if (d := _decision(perfil, v, similitudes[v.id], evidencias, matriz_evid,
                                                         politica))]
    (ordenador or OrdenSimilitudCobertura()).ordenar(perfil, decisiones)
    with transaction.atomic():
        _guardar(perfil, decisiones, hoy or timezone.localdate(), preseleccion.ocultas_por_modalidad, inicio)
    return ResumenDecision(len(decisiones), dict(Counter(d.accion for d in decisiones)),
                           preseleccion.ocultas_por_modalidad, time.perf_counter() - reloj)
