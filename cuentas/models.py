from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from pgvector.django import HalfVectorField


def normalizar_correo(email: str) -> str:
    return email.strip().lower()


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        usuario = self.model(email=normalizar_correo(email), **extra_fields)
        usuario.set_password(password)  # None deja la contraseña inutilizable (login social)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    """Se identifica por correo; no tiene nombre de usuario."""

    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def __str__(self):
        return self.email


class Autorizacion(models.Model):
    """Autorización previa, expresa e informada del tratamiento de datos (Ley 1581 de 2012)."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    version_politica = models.CharField(max_length=20)
    version_terminos = models.CharField(max_length=20)
    finalidad = models.TextField()
    aceptada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "autorizaciones"

    def __str__(self):
        return f"{self.usuario} · política {self.version_politica}"


class Perfil(models.Model):
    class Disponibilidad(models.TextChoices):
        INMEDIATA = "inmediata", "Inmediata"
        DOS_SEMANAS = "dos_semanas", "2 semanas"
        UN_MES = "un_mes", "1 mes"

    class Modalidad(models.TextChoices):
        REMOTO = "Remoto", "Remoto"
        PRESENCIAL = "Presencial", "Presencial"
        HIBRIDO = "Híbrido", "Híbrido"

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    nombre = models.CharField(max_length=150, null=True, blank=True)
    contacto = models.EmailField(null=True, blank=True)
    experiencia = models.JSONField(null=True, blank=True)
    educacion = models.JSONField(null=True, blank=True)
    habilidades = models.JSONField(default=list, blank=True)
    campos_pendientes = models.JSONField(default=list, blank=True)
    cv_nombre_archivo = models.CharField(max_length=255, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    exp_salario_min = models.PositiveIntegerField(null=True, blank=True)
    exp_modalidad = models.CharField(max_length=20, choices=Modalidad.choices, blank=True)
    exp_ubicacion = models.CharField(max_length=150, blank=True)
    exp_disponibilidad = models.CharField(max_length=20, choices=Disponibilidad.choices, blank=True)
    anios_experiencia = models.PositiveIntegerField(null=True, blank=True)

    class ModoNotificacion(models.TextChoices):  # spec §5.7: preferencia del candidato
        RESUMEN = "resumen", "Un resumen diario por correo"
        INDIVIDUAL = "individual", "Un correo por vacante (con un máximo al día)"
        DESACTIVADO = "desactivado", "Solo en la campana, sin correos"

    notif_modo = models.CharField(max_length=12, choices=ModoNotificacion.choices, default=ModoNotificacion.RESUMEN)
    notif_max = models.PositiveSmallIntegerField(default=3)

    # Vectores (Fase 2): promedio normalizado de la evidencia y su matriz (float16), al día si hash_embebido coincide.
    vector = HalfVectorField(dimensions=settings.SCOUTLY_DIMENSION, null=True, blank=True)
    matriz_evidencia = models.BinaryField(null=True, blank=True)
    hash_embebido = models.CharField(max_length=64, blank=True, default="")

    def __str__(self):
        return f"Perfil de {self.usuario.email}"

    def tiene_cv(self) -> bool:
        """False para el perfil vacío que crea /expectativas antes de cargar la hoja de vida."""
        return bool(self.cv_nombre_archivo)

    def tiene_expectativas(self) -> bool:
        return bool(self.exp_salario_min or self.exp_modalidad or self.exp_ubicacion or self.exp_disponibilidad)

    def puede_notificar(self) -> bool:
        return bool(self.contacto)


class EvidenciaPerfil(models.Model):
    """Una viñeta u oración del CV, ya sin datos personales. El vector lo agrega la Fase 2."""

    class Seccion(models.TextChoices):
        EXPERIENCIA = "experiencia", "Experiencia"
        HABILIDADES = "habilidades", "Habilidades"
        EDUCACION = "educacion", "Educación"

    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name="evidencias")
    texto = models.TextField()
    seccion = models.CharField(max_length=20, choices=Seccion.choices)
    posicion = models.PositiveIntegerField()

    class Meta:
        ordering = ["posicion"]
        constraints = [models.UniqueConstraint(fields=["perfil", "posicion"], name="evidencia_posicion_unica")]
