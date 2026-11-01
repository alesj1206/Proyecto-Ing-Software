from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


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
