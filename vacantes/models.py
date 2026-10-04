from django.conf import settings
from django.db import models


class Perfil(models.Model):
    class Disponibilidad(models.TextChoices):
        INMEDIATA = "inmediata", "Inmediata"
        DOS_SEMANAS = "dos_semanas", "2 semanas"
        UN_MES = "un_mes", "1 mes"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil"
    )
    nombre = models.CharField(max_length=150, null=True, blank=True)
    contacto = models.EmailField(null=True, blank=True)
    experiencia = models.JSONField(null=True, blank=True)
    educacion = models.JSONField(null=True, blank=True)
    habilidades = models.JSONField(default=list, blank=True)
    campos_pendientes = models.JSONField(default=list, blank=True)
    cv_nombre_archivo = models.CharField(max_length=255)
    actualizado_en = models.DateTimeField(auto_now=True)

    # HU-02: expectativas laborales — alimentan el motor de scoring (matching.py).
    # Mismos valores que Vacante.Modalidad; duplicados aquí (en vez de
    # referenciar Vacante, definida más abajo en este módulo) para no crear
    # una dependencia de orden de declaración entre los dos modelos.
    class ModalidadExpectativa(models.TextChoices):
        REMOTO = "Remoto", "Remoto"
        PRESENCIAL = "Presencial", "Presencial"
        HIBRIDO = "Híbrido", "Híbrido"

    exp_salario_min = models.PositiveIntegerField(null=True, blank=True)
    exp_modalidad = models.CharField(
        max_length=20, choices=ModalidadExpectativa.choices, blank=True
    )
    exp_ubicacion = models.CharField(max_length=150, blank=True)
    exp_disponibilidad = models.CharField(
        max_length=20, choices=Disponibilidad.choices, blank=True
    )

    def __str__(self):
        return f"Perfil de {self.usuario.email}"

    def tiene_expectativas(self):
        """True si hay al menos una expectativa que matching.py realmente usa
        para el score. exp_disponibilidad queda fuera a propósito: se guarda
        y se muestra en el perfil, pero el motor de scoring no la lee (no
        hay una fecha límite por vacante contra la cual compararla), así que
        no cuenta como "usada en tu ranking de hoy"."""
        return bool(self.exp_salario_min or self.exp_modalidad or self.exp_ubicacion)


class Vacante(models.Model):
    class Modalidad(models.TextChoices):
        REMOTO = "Remoto", "Remoto"
        PRESENCIAL = "Presencial", "Presencial"
        HIBRIDO = "Híbrido", "Híbrido"

    class Periodo(models.TextChoices):
        MENSUAL = "mensual", "Mensual"
        ANUAL = "anual", "Anual"

    id = models.CharField(max_length=20, primary_key=True)
    titulo = models.CharField(max_length=200)
    empresa = models.CharField(max_length=150)
    ubicacion = models.CharField(max_length=150)
    modalidad = models.CharField(max_length=20, choices=Modalidad.choices)
    salario_min = models.PositiveIntegerField(null=True, blank=True)
    salario_max = models.PositiveIntegerField(null=True, blank=True)
    salario_moneda = models.CharField(max_length=10, null=True, blank=True)
    salario_periodo = models.CharField(
        max_length=10, choices=Periodo.choices, null=True, blank=True
    )
    requisitos = models.JSONField(default=list)
    descripcion = models.TextField()
    fecha_publicacion = models.DateField()

    class Meta:
        ordering = ["-fecha_publicacion"]

    def __str__(self):
        return f"{self.titulo} ({self.empresa})"

    def salario_formateado(self):
        if self.salario_min is None or self.salario_max is None:
            return "No especificado"
        return (
            f"{self.salario_moneda} {self.salario_min:,.0f}-{self.salario_max:,.0f}"
            f" / {self.get_salario_periodo_display().lower()}"
        ).replace(",", ".")
