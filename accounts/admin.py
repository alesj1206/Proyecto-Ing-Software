from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


class UsuarioAdmin(UserAdmin):
    model = Usuario
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "password1", "password2")}),
    )
    list_display = ("email", "is_staff", "is_active")
    ordering = ("email",)


admin.site.register(Usuario, UsuarioAdmin)
