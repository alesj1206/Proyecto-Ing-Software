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

    # Criterio "experiencia" del matching (Sprint 2, rediseño de criterios).
    # Declarado por el candidato, igual que las expectativas — no se intenta
    # parsear años de experiencia del texto libre del CV (los formatos de
    # fecha varían demasiado para que una heurística sea confiable).
    anios_experiencia = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Perfil de {self.usuario.email}"

    def tiene_cv(self):
        """False para el Perfil vacío que expectativas_view crea con
        get_or_create cuando alguien visita /expectativas sin haber pasado
        por onboarding. Única fuente de verdad para "¿ya cargó su hoja de
        vida?" — la usan tanto views._perfil_con_cv (candidato individual)
        como scoring.recalcular_matches_todos (batch diario)."""
        return bool(self.cv_nombre_archivo)

    def tiene_expectativas(self):
        """True si hay al menos una expectativa que matching.py puede llegar
        a usar para el score. exp_disponibilidad entró aquí cuando se agregó
        el modificador de "vacante urgente" (matching.py) — antes de eso no
        afectaba el score y quedaba fuera a propósito; ahora sí puede sumar
        o restar puntos, igual que los otros tres, así que cuenta igual
        aunque su efecto dependa de que la vacante concreta sea urgente."""
        return bool(
            self.exp_salario_min or self.exp_modalidad or self.exp_ubicacion or self.exp_disponibilidad
        )


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

    # Criterio "experiencia" del matching (Sprint 2). None = la vacante no
    # exige una antigüedad mínima, así que el criterio no aplica para ella
    # (se excluye del promedio ponderado en vez de contar como 0%).
    experiencia_minima = models.PositiveIntegerField(null=True, blank=True)

    # Señal real de Magneto ("Requerido con urgencia"). No es un criterio
    # más del promedio ponderado — es un modificador: solo ajusta el score
    # final cuando la vacante es urgente Y el candidato declaró su
    # disponibilidad (matching.py::_modificador_disponibilidad).
    urgente = models.BooleanField(default=False)

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


class MatchDiario(models.Model):
    """HU-06: ranking de 'Matches de hoy' persistido, para que no dependa de
    recalcular el score en cada request. Lo escribe scoring.recalcular_matches_de_perfil,
    llamado por el workflow de n8n (vía /api/recalcular-matches, una vez al
    día) y también de inmediato cuando el candidato actualiza su CV o sus
    expectativas (para que el ranking se sienta al día sin esperar al
    siguiente ciclo del workflow)."""

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="matches_diarios")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE)
    score = models.FloatField()
    coincidencias = models.JSONField(default=list)
    fecha = models.DateField()
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["perfil", "vacante", "fecha"], name="unico_match_por_dia")
        ]
        ordering = ["-fecha", "-score"]

    def __str__(self):
        return f"{self.perfil} ↔ {self.vacante} ({self.fecha}): {self.score:.2f}"


class Postulacion(models.Model):
    """HU-08 (postularse, simulado) + HU-10 (tablero de estado): una fila es
    la evidencia de que el candidato aplicó (con timestamp) y, a la vez, la
    tarjeta que aparece en el tablero Kanban. No hay integración real con
    Magneto — "simulada" significa que el estado lo mueve el propio
    candidato desde /postulaciones, no un sistema externo."""

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
        constraints = [
            models.UniqueConstraint(fields=["perfil", "vacante"], name="una_postulacion_por_vacante")
        ]
        ordering = ["-fecha_aplicacion"]

    def __str__(self):
        return f"{self.perfil} → {self.vacante} ({self.get_estado_display()})"


class ExplicacionCriterio(models.Model):
    """Explicación en lenguaje natural (generada por IA, Groq) de por qué un
    criterio de matching obtuvo cierto puntaje para un candidato y una
    vacante específicos. Se cachea aquí para no llamar la API en cada vista
    de página — matching.evaluar_criterios compara el score_pct guardado
    contra el recién calculado y solo regenera si cambió (CV o expectativas
    actualizadas)."""

    class Criterio(models.TextChoices):
        HABILIDADES = "habilidades", "Habilidades"
        EXPERIENCIA = "experiencia", "Experiencia"
        SALARIO = "salario", "Salario"
        MODALIDAD = "modalidad", "Modalidad"
        UBICACION = "ubicacion", "Ubicación"

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="explicaciones")
    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE, related_name="explicaciones")
    criterio = models.CharField(max_length=20, choices=Criterio.choices)
    score_pct = models.FloatField()
    texto = models.TextField()
    generado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["perfil", "vacante", "criterio"], name="una_explicacion_por_criterio"
            )
        ]

    def __str__(self):
        return f"{self.perfil} / {self.vacante} / {self.criterio}: {self.score_pct:.0f}%"
