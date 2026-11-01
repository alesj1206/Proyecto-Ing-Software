"""Lecturas para las pantallas del decisor. Arman el mismo contexto que esperaban los templates de v2 a partir de las
`Decision` ya calculadas (la web nunca decide ni carga modelos)."""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from vacantes.extraccion import normalizar
from vacantes.models import Vacante

from .models import Decision, FotoDiaria, SolicitudDecision
from .politica import Accion

ACCIONES_DEL_PLAN = (Accion.POSTULAR, Accion.AJUSTAR_CV)
ORDEN_ACCIONES = (Accion.POSTULAR, Accion.AJUSTAR_CV, Accion.CERRAR_BRECHA, Accion.SIN_DATOS, Accion.DESCARTAR)
ACCIONES_DEL_RANKING = (Accion.POSTULAR, Accion.AJUSTAR_CV, Accion.CERRAR_BRECHA)
HORAS_POSTULAR_HOY = 72
TOP_HISTORIAL = 10
SUFIJOS_EMPRESA = re.compile(r"\b(?:s a s|sas|s a|sa|ltda|s en c)\b")
CRITERIOS = (("experiencia", "Experiencia"), ("salario", "Salario"), ("modalidad", "Modalidad"),
             ("ubicacion", "Ubicación"))


def catalogo(modalidad: str = ""):
    vacantes = Vacante.objects.filter(activa=True)
    return vacantes.filter(modalidad=modalidad) if modalidad else vacantes


def total_vacantes() -> int:
    return Vacante.objects.filter(activa=True).count()


def _contables(decision: Decision) -> list[dict]:
    return [r for r in decision.cobertura if r["tipo"] == "obligatorio" and r["estado"] != "formacion"]


def _cubres(decision: Decision) -> str:
    contables = _contables(decision)
    return f"{sum(r['estado'] == 'cubierto' for r in contables)}/{len(contables)}"


def _textos(decision: Decision, estado: str) -> list[str]:
    return [r["texto"] for r in decision.cobertura if r["estado"] == estado]


@dataclass
class ItemPlan:
    """Una tarjeta del Plan de hoy, con los campos que ya usaba el template de v2 (vacante, score_pct, …)."""

    decision: Decision
    postular_hoy: bool

    @property
    def vacante(self):
        return self.decision.vacante

    @property
    def score_pct(self) -> int:
        return self.decision.cobertura_pct

    @property
    def coincidencias(self) -> list[str]:
        return _textos(self.decision, "cubierto")

    @property
    def razon_principal(self) -> str | None:
        return self.decision.con_nota or (self.decision.motivos[0] if self.decision.motivos else None)

    @property
    def cubres(self) -> str:
        return _cubres(self.decision)


def clave_empresa(nombre: str) -> str:
    """"ACME S.A.S." y "Acme SAS" son la misma empresa."""
    return " ".join(SUFIJOS_EMPRESA.sub(" ", normalizar(nombre)).split())


def _frescura(publicada: date, hoy: date) -> float:
    dias = (hoy - publicada).days
    return 1.0 if dias * 24 < HORAS_POSTULAR_HOY else 0.8 if dias <= 7 else 0.6


def plan_de_hoy(perfil, n: int = 5, ahora: date | None = None) -> list[ItemPlan]:
    """3–5 vacantes para postularse hoy: como máximo una por empresa, por ajuste × frescura (spec §13.2)."""
    hoy = ahora or timezone.localdate()
    candidatas = Decision.objects.filter(perfil=perfil, accion__in=ACCIONES_DEL_PLAN).select_related("vacante")
    ordenadas = sorted(candidatas, key=lambda d: -d.orden * _frescura(d.vacante.fecha_publicacion, hoy))
    plan, empresas = [], set()
    for d in ordenadas:
        if (clave := clave_empresa(d.vacante.empresa)) in empresas:
            continue
        empresas.add(clave)
        plan.append(ItemPlan(d, (hoy - d.vacante.fecha_publicacion).days * 24 < HORAS_POSTULAR_HOY))
        if len(plan) == n:
            break
    return plan


def decisiones_por_accion(perfil) -> dict[str, list[Decision]]:
    decisiones = Decision.objects.filter(perfil=perfil).select_related("vacante").order_by("-orden")
    grupos = {accion.value: [] for accion in ORDEN_ACCIONES}
    for d in decisiones:
        grupos[d.accion].append(d)
    return grupos


def plan_de_aprendizaje(perfil, n: int = 5) -> list[tuple[str, int]]:
    """Las brechas agregadas: qué requisito obligatorio te falta en más vacantes de CERRAR_BRECHA."""
    conteo, nombres = Counter(), {}
    for cobertura in Decision.objects.filter(perfil=perfil, accion=Accion.CERRAR_BRECHA).values_list("cobertura",
                                                                                                      flat=True):
        for r in cobertura:
            if r["estado"] == "faltante" and r["tipo"] == "obligatorio":
                clave = normalizar(r["texto"])
                nombres.setdefault(clave, r["texto"])
                conteo[clave] += 1
    return [(nombres[c], veces) for c, veces in conteo.most_common(n)]


def detalle(perfil, vacante) -> dict | None:
    decision = Decision.objects.filter(perfil=perfil, vacante=vacante).first()
    if decision is None:
        return None
    por_criterio = {r["criterio"]: r for r in decision.restricciones}
    criterios = [{"etiqueta": "Habilidades", "peso_pct": None, "score_pct": decision.cobertura_pct, "aplica": True,
                  "razon_no_aplica": "", "es_del_candidato": False,
                  "explicacion": f"Cubres {_cubres(decision)} requisitos obligatorios"}]
    for clave, etiqueta in CRITERIOS:
        r = por_criterio.get(clave, {"estado": "sin_datos", "motivo": "Sin datos"})
        aplica = r["estado"] != "sin_datos"
        criterios.append({"etiqueta": etiqueta, "peso_pct": None,
                          "score_pct": {"cumple": 100, "parcial": 50}.get(r["estado"], 0), "aplica": aplica,
                          "razon_no_aplica": "" if aplica else r["motivo"],
                          "es_del_candidato": r["motivo"].startswith("No declaraste"),
                          "explicacion": r["motivo"] if aplica else None})
    return {
        "decision": decision,
        "match": {"score": decision.cobertura_pct, "coincidencias": _textos(decision, "cubierto"),
                  "faltantes": [r["texto"] for r in _contables(decision) if r["estado"] == "faltante"],
                  "razones": decision.motivos},
        "criterios": criterios,
        "modificador": None,
        "requisitos": {grupo: [r for r in decision.cobertura if r["estado"] == estado]
                       for grupo, estado in (("cubiertos", "cubierto"), ("parciales", "parcial"),
                                             ("faltantes", "faltante"))},
    }


def _ranking(foto: FotoDiaria) -> list[dict]:
    filas = [f for accion in ACCIONES_DEL_RANKING for f in foto.top.get(accion, [])]
    return sorted(filas, key=lambda f: -f["orden"])[:TOP_HISTORIAL]


def historial(perfil, fecha: date | None = None) -> dict:
    fotos = list(FotoDiaria.objects.filter(perfil=perfil))
    fechas = [f.fecha for f in fotos]
    seleccionada = next((f for f in fotos if f.fecha == fecha), fotos[0] if fotos else None)
    if seleccionada is None:
        return {"perfil": perfil, "fechas_disponibles": [], "fecha_sel": None, "fecha_anterior": None, "ranking": []}
    anterior = next((f for f in fotos if f.fecha < seleccionada.fecha), None)
    antes = {f["vacante_id"]: f["cobertura_pct"] for f in _ranking(anterior)} if anterior else {}
    filas = _ranking(seleccionada)
    vacantes = Vacante.objects.in_bulk([f["vacante_id"] for f in filas])
    ranking = [{"puesto": i, "vacante": vacantes[f["vacante_id"]], "score_pct": f["cobertura_pct"],
                "es_nuevo": f["vacante_id"] not in antes,
                "delta_pct": f["cobertura_pct"] - antes[f["vacante_id"]] if f["vacante_id"] in antes else None}
               for i, f in enumerate((f for f in filas if f["vacante_id"] in vacantes), start=1)]
    return {"perfil": perfil, "fechas_disponibles": fechas, "fecha_sel": seleccionada.fecha,
            "fecha_anterior": anterior.fecha if anterior else None, "ranking": ranking}


MODALIDAD_OPUESTA = {"Remoto": "Presencial", "Presencial": "Remoto"}


def ocultas_por_modalidad(perfil) -> int:
    """Cuántas vacantes relevantes se ocultaron por modalidad opuesta (§5.7: nada desaparece en silencio)."""
    from .politica import POLITICA
    from .preseleccion import preseleccionar

    return preseleccionar(perfil, POLITICA.tau_relevancia).ocultas_por_modalidad


def pendiente_de_decision(perfil) -> bool:
    return SolicitudDecision.objects.filter(perfil=perfil).exists()
