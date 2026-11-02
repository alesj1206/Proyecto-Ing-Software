"""Fachada del decisor (spec §7.2): `decidir_para_perfil` es la única puerta que usan el batch y la API."""

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from django.db import transaction
from django.db.models import F, Q
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
from .vectores import de_bytes, embeber_perfil, firma_modelos

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
    matriz_req = de_bytes(vacante.matriz_requisitos, len(requisitos))
    if matriz_req is None or matriz_evid is None:
        return None  # vectores desalineados con el texto: se conserva la decisión anterior (_guardar)
    if len(matriz_req) and len(matriz_evid) and matriz_req.shape[1] != matriz_evid.shape[1]:
        return None  # embebidas con modelos distintos (por ejemplo, a mitad de un cambio de modelo)
    if not len(matriz_req):
        matriz_req = np.zeros((0, matriz_evid.shape[1]), dtype=np.float32)
    cobertura = cubrir(requisitos, matriz_req, evidencias, matriz_evid, politica.tau_alto, politica.tau_bajo)
    restricciones = [res for r in RESTRICCIONES if (res := r.evaluar(perfil, vacante, politica)) is not None]
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
    return _decision(perfil, vacante, similitud, evidencias, de_bytes(perfil.matriz_evidencia, len(evidencias)),
                     politica)


TOP_EMPRESAS = 3


# "Tu mercado" y el plan de aprendizaje miran solo lo de verdad cercano al perfil. τ_relevancia (0,25) deja pasar casi
# todo el catálogo para que el decisor vea las vacantes escuetas; para describir el mercado de la persona hace falta
# un corte más estricto (el τ_relevancia anterior a la Fase 4).
SIMILITUD_CERCANA = 0.40


def _mercado(decisiones: list[Decision]) -> dict:
    """Sobre las cercanas que no son DESCARTAR: cuántas, el rango de salarios y las empresas que más publican."""
    utiles = [d.vacante for d in decisiones if d.accion != Accion.DESCARTAR and d.similitud >= SIMILITUD_CERCANA]
    minimos = [v.salario_min for v in utiles if v.salario_min]
    maximos = [v.salario_max for v in utiles if v.salario_max]
    empresas = Counter(v.empresa for v in utiles if v.empresa).most_common(TOP_EMPRESAS)
    return {"relevantes": len(utiles), "salario_min": min(minimos, default=None),
            "salario_max": max(maximos, default=None), "empresas": [list(e) for e in empresas]}


# Lo que no entra en la huella: claves, la fecha de escritura y lo que se deriva de la decisión anterior.
FUERA_DE_HUELLA = {"id", "perfil", "vacante", "fecha_decision", "accion_anterior", "cambio_en", "huella"}


def huella(decision: Decision) -> str:
    """sha256 del contenido de la decisión: si es igual a la guardada, no hace falta reescribirla."""
    valores = [(f.name, getattr(decision, f.attname)) for f in Decision._meta.concrete_fields
               if f.name not in FUERA_DE_HUELLA]
    return hashlib.sha256(json.dumps(valores, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _guardar(perfil: Perfil, decisiones: list[Decision], hoy: date, ocultas: int, inicio,
            conservar: set[str] = frozenset()) -> None:
    """`conservar`: vacantes que no se pudieron decidir por tener los vectores desactualizados; su decisión anterior
    se deja tal cual (sin volver a "NUEVA", que las notificaría otra vez)."""
    anteriores = {v: (a, c, aa, h) for v, a, c, aa, h in Decision.objects.filter(perfil=perfil)
                  .values_list("vacante_id", "accion", "cambio_en", "accion_anterior", "huella")}
    cambiadas = []
    for d in decisiones:
        accion_previa, cambio_previo, anterior_guardada, huella_guardada = anteriores.get(d.vacante_id,
                                                                                         (NUEVA, None, None, None))
        d.accion_anterior = accion_previa
        d.cambio_en = cambio_previo if accion_previa == d.accion and cambio_previo else inicio
        d.huella = huella(d)
        # Una corrida diaria repite casi todas las decisiones de ayer: escribir solo las que cambiaron ahorra el upsert
        # de ~3.000 filas con JSON. Una que acaba de cambiar se escribe una vez más, para que accion_anterior alcance
        # a la acción (las notificaciones dependen de eso).
        if (d.huella, d.accion_anterior, d.cambio_en) != (huella_guardada, anterior_guardada, cambio_previo):
            cambiadas.append(d)
    (Decision.objects.filter(perfil=perfil).exclude(vacante_id__in=[d.vacante_id for d in decisiones])
     .exclude(vacante_id__in=conservar).delete())
    campos = [f.name for f in Decision._meta.concrete_fields if f.name not in ("id", "perfil", "vacante")]
    Decision.objects.bulk_create(cambiadas, update_conflicts=True, unique_fields=["perfil", "vacante"],
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


def _con_vectores_viejos(perfil: Perfil, modelos: str) -> set[str]:
    """Vacantes activas con decisión de este perfil cuyos vectores todavía no están al día (contenido o modelos): otro
    proceso las está re-embebiendo. No entran a la preselección, pero tampoco se borra lo que ya se había decidido."""
    al_dia = Q(vacante__hash_embebido=F("vacante__hash_contenido")) & Q(vacante__modelos_embebido=modelos)
    return set(Decision.objects.filter(perfil=perfil, vacante__activa=True).exclude(al_dia)
               .values_list("vacante_id", flat=True))


def decidir_para_perfil(perfil: Perfil, embedder: Embedder, ordenador: Ordenador | None = None,
                        politica: Politica = POLITICA, hoy: date | None = None,
                        cobertura: Embedder | None = None) -> ResumenDecision:
    """`embedder` da el vector de la preselección y `cobertura` (mpnet en producción) la matriz de la evidencia."""
    inicio, reloj = timezone.now(), time.perf_counter()
    evidencias = list(perfil.evidencias.order_by("posicion").values_list("texto", flat=True))  # se leen una vez
    embeber_perfil(perfil, embedder, evidencias, cobertura)
    modelos = firma_modelos(embedder, cobertura)
    preseleccion = preseleccionar(perfil, politica.tau_relevancia, modelos=modelos)
    similitudes = dict(preseleccion.relevantes)
    vacantes = Vacante.objects.filter(id__in=similitudes).prefetch_related("requisito_set")
    matriz_evid = de_bytes(perfil.matriz_evidencia, len(evidencias))
    decisiones, saltadas = [], set()
    for v in vacantes:
        if d := _decision(perfil, v, similitudes[v.id], evidencias, matriz_evid, politica):
            decisiones.append(d)
        else:
            saltadas.add(v.id)
    (ordenador or OrdenSimilitudCobertura()).ordenar(perfil, decisiones)
    with transaction.atomic():
        _guardar(perfil, decisiones, hoy or timezone.localdate(), preseleccion.ocultas_por_modalidad, inicio,
                 conservar=saltadas | _con_vectores_viejos(perfil, modelos))
    return ResumenDecision(len(decisiones), dict(Counter(d.accion for d in decisiones)),
                           preseleccion.ocultas_por_modalidad, time.perf_counter() - reloj)
