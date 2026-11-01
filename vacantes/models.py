from django.conf import settings
from django.db import models
from pgvector.django import HalfVectorField


class Vacante(models.Model):
    """Una vacante del catálogo, con su texto completo (sin truncar). Los vectores llegan en la Fase 2."""

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
    salario_periodo = models.CharField(max_length=10, choices=Periodo.choices, null=True, blank=True)
    descripcion = models.TextField(blank=True)
    fecha_publicacion = models.DateField()
    experiencia_minima = models.PositiveIntegerField(null=True, blank=True)
    nivel_formacion = models.CharField(max_length=80, blank=True)
    urgente = models.BooleanField(default=False)

    texto_completo = models.TextField(blank=True)
    url = models.URLField(max_length=500, blank=True)
    fuente = models.CharField(max_length=40)
    hash_contenido = models.CharField(max_length=64)
    activa = models.BooleanField(default=True)
    etiquetas = models.JSONField(default=list, blank=True)  # las "Habilidades" que trae Magneto
    prefiltro = models.JSONField(default=list, blank=True)  # preguntas de prefiltro (B1, Fase 3)
    ingerida_en = models.DateTimeField(auto_now=True)
    modalidad_inferida = models.BooleanField(default=False)  # True si ni la fuente ni el texto la decían

    # Vectores (Fase 2): promedio normalizado de título + requisitos de texto, y la matriz de todos los requisitos
    # en orden de posicion (float16). hash_embebido == hash_contenido cuando están al día.
    vector = HalfVectorField(dimensions=settings.SCOUTLY_DIMENSION, null=True, blank=True)
    matriz_requisitos = models.BinaryField(null=True, blank=True)
    hash_embebido = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-fecha_publicacion"]

    def __str__(self):
        return f"{self.titulo} ({self.empresa})"

    @property
    def requisitos(self) -> list[str]:
        """Compatibilidad con los templates de v2, que listan `vacante.requisitos` como textos."""
        return [r.texto for r in self.requisito_set.all()]

    def salario_formateado(self) -> str:
        if self.salario_min is None or self.salario_max is None:
            return "No especificado"
        periodo = self.get_salario_periodo_display() or "Mensual"
        return (f"{self.salario_moneda or 'COP'} {self.salario_min:,.0f}-{self.salario_max:,.0f}"
                f" / {periodo.lower()}").replace(",", ".")


class Requisito(models.Model):
    class Tipo(models.TextChoices):
        OBLIGATORIO = "obligatorio", "Obligatorio"
        DESEABLE = "deseable", "Deseable"

    class Origen(models.TextChoices):
        TEXTO = "texto", "Texto de la vacante"
        ETIQUETA = "etiqueta", "Etiqueta de Magneto"

    vacante = models.ForeignKey(Vacante, on_delete=models.CASCADE)
    texto = models.TextField()
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    origen = models.CharField(max_length=10, choices=Origen.choices)
    posicion = models.PositiveIntegerField()

    class Meta:
        ordering = ["posicion"]
        constraints = [models.UniqueConstraint(fields=["vacante", "posicion"], name="requisito_posicion_unica")]

    def __str__(self):
        return self.texto


class EstadoIngesta(models.Model):
    """Fila única que evita dos ingestas a la vez (n8n puede reintentar mientras la anterior sigue corriendo)."""

    en_curso = models.BooleanField(default=False)
    iniciada_en = models.DateTimeField(null=True, blank=True)
    ultimo_resumen = models.CharField(max_length=255, blank=True)
    corrida = models.CharField(max_length=32, blank=True)  # dueño del candado: solo él lo suelta
