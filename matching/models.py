from django.db import models
from django.utils import timezone

from cuentas.models import Perfil
from vacantes.models import Vacante

from .politica import Accion


class Decision(models.Model):
    """La decisión vigente para un par (perfil, vacante), con los insumos que la produjeron (spec §5.5, §7.3)."""

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="decisiones")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="decisiones")
    accion = models.CharField(max_length=16, choices=Accion.choices)
    accion_anterior = models.CharField(max_length=16, blank=True)  # la acción previa, o "NUEVA" si recién es relevante
    cambio_en = models.DateTimeField(null=True, blank=True)  # cuándo cambió la acción por última vez (o apareció)
    con_nota = models.CharField(max_length=255, blank=True)
    solidez = models.CharField(max_length=5)  # alta | media | baja
    motivo_solidez = models.CharField(max_length=255)
    motivos = models.JSONField(default=list)
    similitud = models.FloatField()
    cobertura_pct = models.PositiveSmallIntegerField()
    relevancia = models.FloatField(null=True, blank=True)  # del reranker, si está encendido
    orden = models.FloatField(default=0)
    cobertura = models.JSONField(default=list)  # [{texto, tipo, origen, estado, similitud, evidencia}]
    restricciones = models.JSONField(default=list)  # [{criterio, estado, motivo}]
    fecha_decision = models.DateTimeField(auto_now=True)
    version_politica = models.CharField(max_length=20)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "vacante"], name="una_decision_por_par")]
        indexes = [models.Index(fields=["perfil", "accion", "-orden"])]

    def __str__(self):
        return f"{self.perfil} / {self.vacante_id}: {self.accion}"


class FotoDiaria(models.Model):
    """Resumen por candidato y día para /historial, sin guardar miles de filas diarias por persona (§5.7)."""

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="fotos")
    fecha = models.DateField()
    conteos = models.JSONField(default=dict)  # {accion: n}
    top = models.JSONField(default=dict)  # {accion: [{vacante_id, cobertura_pct, orden}]} (hasta 10 por acción)
    ocultas_por_modalidad = models.PositiveIntegerField(default=0)  # lo lee el dashboard sin buscar de nuevo

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "fecha"], name="una_foto_por_dia")]
        ordering = ["-fecha"]


class SolicitudDecision(models.Model):
    """Un perfil que cambió (CV o expectativas) y espera que el batch lo decida. La web no carga modelos (§13.4)."""

    perfil = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name="solicitud_decision")
    creada_en = models.DateTimeField(default=timezone.now)  # se refresca en cada solicitud
    intentos = models.PositiveSmallIntegerField(default=0)  # fallos del batch con este perfil
