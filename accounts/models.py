from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        email = self.normalize_email(email)
        usuario = self.model(email=email, username=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def __str__(self):
        return self.email
