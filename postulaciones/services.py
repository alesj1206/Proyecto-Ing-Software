from django.db import IntegrityError

from cuentas.models import Perfil
from vacantes.models import Vacante

from .models import Postulacion, ResultadoDecision


def postular(perfil: Perfil, vacante: Vacante) -> bool:
    """Idempotente: devuelve True solo si la postulación es nueva (un doble clic no crea dos)."""
    try:
        _, creada = Postulacion.objects.get_or_create(perfil=perfil, vacante=vacante)
    except IntegrityError:  # dos peticiones a la vez: la segunda choca con la restricción única
        return False
    return creada


def cambiar_estado(postulacion: Postulacion, estado: str) -> bool:
    if estado not in Postulacion.Estado.values:
        return False
    postulacion.estado = estado
    postulacion.save(update_fields=["estado", "actualizado_en"])
    if estado in ResultadoDecision.Resultado.values:
        registrar_resultado(postulacion, estado)
    return True


def registrar_resultado(postulacion: Postulacion, resultado: str) -> ResultadoDecision:
    """Guarda el resultado con una copia de los insumos de la decisión vigente (si la hay). Idempotente por estado."""
    from matching.models import Decision  # postulaciones no depende de matching al importar

    decision = Decision.objects.filter(perfil_id=postulacion.perfil_id, vacante_id=postulacion.vacante_id).first()
    datos = {"accion": "", "solidez": "", "cobertura_pct": None, "version_politica": "", "insumos": {}}
    if decision:
        datos = {"accion": decision.accion, "solidez": decision.solidez, "cobertura_pct": decision.cobertura_pct,
                 "version_politica": decision.version_politica,
                 "insumos": {"cobertura": decision.cobertura, "restricciones": decision.restricciones}}
    registro, _ = ResultadoDecision.objects.get_or_create(postulacion=postulacion, resultado=resultado, defaults=datos)
    return registro
