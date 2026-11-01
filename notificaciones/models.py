from django.db import models

from cuentas.models import Perfil
from vacantes.models import Vacante


class Notificacion(models.Model):
    """Aviso de una vacante nueva para el candidato (HU-11). La genera el batch de la Fase 3."""

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="notificaciones")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="notificaciones")
    score_pct = models.PositiveIntegerField()
    mensaje = models.CharField(max_length=255)
    enviada = models.BooleanField(default=False)
    leida = models.BooleanField(default=False)
    fecha = models.DateField()
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "vacante", "fecha"],
                                               name="una_notificacion_por_vacante_por_dia")]
        indexes = [models.Index(fields=["perfil", "leida"])]
        ordering = ["-creada_en"]
