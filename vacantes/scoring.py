"""HU-06: cálculo y persistencia del ranking diario de 'Matches de hoy'.

matching.py sabe calcular un score; este módulo sabe cuándo y dónde
guardarlo. Lo llaman tres caminos distintos que todos deben terminar en el
mismo lugar (MatchDiario), para que el dashboard nunca tenga que decidir
entre "¿leo la tabla o recalculo en vivo?":

1. El workflow de n8n, vía POST /api/recalcular-matches (una vez al día,
   para todos los perfiles con CV) — views.recalcular_matches_api.
2. El comando `manage.py recalcular_matches`, para probar lo mismo sin
   depender de que n8n esté corriendo.
3. Las propias vistas de Scoutly, para un solo perfil, justo después de que
   el candidato actualiza su CV o sus expectativas — así el ranking no se
   siente desactualizado hasta el siguiente ciclo del workflow.
"""

from django.db import transaction
from django.utils import timezone

from .matching import compute_matches_de_hoy
from .models import MatchDiario, Perfil, Vacante


def recalcular_matches_de_perfil(perfil, fecha=None, vacantes=None):
    """Calcula y persiste el ranking de hoy para un único perfil.
    Reemplaza por completo las filas de ese perfil para esa fecha (en vez de
    updatear una por una) porque una vacante que ya no hace match debe
    desaparecer del ranking, no quedar con un score viejo.

    delete()+bulk_create() van en una transacción: sin esto, dos llamadas
    concurrentes para el mismo perfil+fecha (p. ej. el batch de n8n
    corriendo justo cuando el candidato guarda sus expectativas) pueden
    pisarse — la segunda bulk_create choca con el UniqueConstraint de
    MatchDiario porque la primera ya reinsertó filas que la segunda cree
    que no existen. atomic() serializa esas dos llamadas en vez de dejar
    que una reviente con IntegrityError."""
    fecha = fecha or timezone.localdate()
    vacantes = vacantes if vacantes is not None else list(Vacante.objects.all())

    matches = compute_matches_de_hoy(perfil, vacantes)

    with transaction.atomic():
        MatchDiario.objects.filter(perfil=perfil, fecha=fecha).delete()
        MatchDiario.objects.bulk_create(
            [
                MatchDiario(
                    perfil=perfil,
                    vacante=m.vacante,
                    score=m.score,
                    coincidencias=m.coincidencias,
                    fecha=fecha,
                )
                for m in matches
            ]
        )
    return matches


def recalcular_matches_todos(fecha=None):
    """Corre el batch diario completo: un perfil con CV cargado = un
    candidato real a quien mostrarle matches. Perfiles sin CV (p. ej. uno
    creado solo por haber visitado /expectativas) no tienen habilidades que
    cruzar contra nada, así que se excluyen."""
    fecha = fecha or timezone.localdate()
    vacantes = list(Vacante.objects.all())
    perfiles = [p for p in Perfil.objects.all() if p.tiene_cv()]

    total_matches = 0
    for perfil in perfiles:
        matches = recalcular_matches_de_perfil(perfil, fecha=fecha, vacantes=vacantes)
        total_matches += len(matches)

    return {"perfiles_procesados": len(perfiles), "matches_guardados": total_matches, "fecha": fecha}
