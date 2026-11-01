"""Explicación en prosa de una decisión (spec §5.6). Las razones estructuradas se muestran siempre; esto es un extra a
pedido. A Groq solo van campos de criterio: nunca la evidencia del CV, el nombre ni el correo (§13.5)."""

import hashlib
import json

from .models import Decision, ExplicacionDecision
from .politica import Accion
from .puertos import Redactor


def insumos_publicos(decision: Decision) -> dict:
    return {
        "accion": Accion(decision.accion).label,
        "solidez": decision.solidez,
        "cobertura_pct": decision.cobertura_pct,
        "requisitos": [{"texto": r["texto"], "estado": r["estado"]} for r in decision.cobertura],  # sin evidencia
        "restricciones": [{"criterio": r["criterio"], "estado": r["estado"], "motivo": r["motivo"]}
                          for r in decision.restricciones],
    }


def _respaldo(decision: Decision) -> str:
    return f"{Accion(decision.accion).label}: " + "; ".join(decision.motivos) + "."


def explicar(decision: Decision, redactor: Redactor | None) -> str:
    insumos = insumos_publicos(decision)
    firma = hashlib.sha256(json.dumps(insumos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if cache := ExplicacionDecision.objects.filter(decision=decision, firma=firma).first():
        return cache.texto
    texto = redactor.redactar(insumos) if redactor else None
    if not texto:
        return _respaldo(decision)  # no se guarda: cuando Groq vuelva, se intenta de nuevo
    ExplicacionDecision.objects.create(decision=decision, firma=firma, texto=texto)
    return texto
