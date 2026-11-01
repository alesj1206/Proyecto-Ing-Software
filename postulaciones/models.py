from django.db import models

from cuentas.models import Perfil
from vacantes.models import Vacante


class Postulacion(models.Model):
    """Postulación simulada (HU-08) y tarjeta del tablero (HU-10): el estado lo mueve el candidato."""

    class Estado(models.TextChoices):
        POSTULADO = "postulado", "Postulado"
        EN_REVISION = "en_revision", "En revisión"
        ENTREVISTA = "entrevista", "Entrevista"
        DESCARTADO = "descartado", "Descartado"

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="postulaciones")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="postulaciones")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.POSTULADO)
    fecha_aplicacion = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "vacante"], name="una_postulacion_por_vacante")]
        ordering = ["-fecha_aplicacion"]

    def __str__(self):
        return f"{self.perfil} → {self.vacante} ({self.get_estado_display()})"


class ResultadoDecision(models.Model):
    """Lo que pasó con una postulación (entrevista o descartado) junto a la decisión que la produjo (spec §5.5): son
    los datos con que se calibrará el decisor más adelante."""

    class Resultado(models.TextChoices):
        ENTREVISTA = "entrevista", "Entrevista"
        DESCARTADO = "descartado", "Descartado"

    postulacion = models.ForeignKey(Postulacion, on_delete=models.CASCADE, related_name="resultados")
    resultado = models.CharField(max_length=12, choices=Resultado.choices)
    accion = models.CharField(max_length=16, blank=True)  # "" si la vacante no tenía decisión
    solidez = models.CharField(max_length=5, blank=True)
    cobertura_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    version_politica = models.CharField(max_length=20, blank=True)
    insumos = models.JSONField(default=dict, blank=True)  # copia de cobertura y restricciones en ese momento
    registrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["postulacion", "resultado"], name="un_resultado_por_estado")]
