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
    fecha_decision = models.DateTimeField(auto_now=True)  # la última vez que se escribió: lo que no cambia no se reescribe
    huella = models.CharField(max_length=64, blank=True, default="")  # sha256 del contenido (services.huella)
    version_politica = models.CharField(max_length=20)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "vacante"], name="una_decision_por_par")]
        indexes = [models.Index(fields=["perfil", "accion", "-orden"])]

    @property
    def contables(self) -> list[dict]:
        """Los obligatorios que se pueden comparar con el CV (formación, experiencia y blandos se evalúan aparte)."""
        return [r for r in self.cobertura
                if r["tipo"] == "obligatorio" and r["estado"] not in ("formacion", "experiencia", "blando")]

    @property
    def cubres(self) -> str:
        return f"{sum(r['estado'] == 'cubierto' for r in self.contables)}/{len(self.contables)}"

    @property
    def cubres_visible(self) -> str:
        """Para mostrar solo: un "0/0" se lee como un error."""
        return self.cubres if self.contables else "—"

    @property
    def compatibilidad_visible(self) -> str:
        """El porcentaje para el anillo; sin obligatorios comparables, un guion en vez de un "0%" engañoso."""
        return f"{self.cobertura_pct}%" if self.contables else "—"

    def __str__(self):
        return f"{self.perfil} / {self.vacante_id}: {self.accion}"


class FotoDiaria(models.Model):
    """Resumen por candidato y día para /historial, sin guardar miles de filas diarias por persona (§5.7)."""

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="fotos")
    fecha = models.DateField()
    conteos = models.JSONField(default=dict)  # {accion: n}
    top = models.JSONField(default=dict)  # {accion: [{vacante_id, cobertura_pct, orden}]} (hasta 10 por acción)
    ocultas_por_modalidad = models.PositiveIntegerField(default=0)  # lo lee el dashboard sin buscar de nuevo
    mercado = models.JSONField(default=dict)  # "Tu mercado": relevantes, rango de salarios y empresas que más publican

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "fecha"], name="una_foto_por_dia")]
        ordering = ["-fecha"]


class SolicitudDecision(models.Model):
    """Un perfil que cambió (CV o expectativas) y espera que el batch lo decida. La web no carga modelos (§13.4)."""

    perfil = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name="solicitud_decision")
    creada_en = models.DateTimeField(default=timezone.now)  # se refresca en cada solicitud
    intentos = models.PositiveSmallIntegerField(default=0)  # fallos del batch con este perfil


class SugerenciaCV(models.Model):
    """Una propuesta del Taller de CV para una vacante (spec §13.3): sale de la evidencia que el CV ya tiene y el
    candidato la acepta o la rechaza. No modifica el CV guardado."""

    class Tipo(models.TextChoices):
        REQUISITO = "requisito", "Requisito"
        RESUMEN = "resumen", "Resumen"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADA = "aceptada", "Aceptada"
        RECHAZADA = "rechazada", "Rechazada"

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="sugerencias_cv")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="sugerencias_cv")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    requisito = models.TextField(blank=True)
    evidencia = models.TextField(blank=True)
    propuesta = models.TextField()  # la pregunta que se le hace al candidato
    respuesta = models.TextField(blank=True)  # lo que el candidato escribió con sus palabras (lo único que se copia)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["perfil", "vacante", "tipo", "requisito"],
                                               name="una_sugerencia_por_requisito")]
        ordering = ["tipo", "id"]


class ExplicacionDecision(models.Model):
    """Caché de la explicación en prosa (Groq) de una decisión, válida mientras no cambien sus insumos (firma)."""

    decision = models.ForeignKey(Decision, on_delete=models.CASCADE, related_name="explicaciones")
    firma = models.CharField(max_length=64)
    texto = models.TextField()
    generada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["decision", "firma"], name="una_explicacion_por_firma")]
