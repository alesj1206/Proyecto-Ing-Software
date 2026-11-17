from django.contrib import admin

from .models import Corrida


@admin.register(Corrida)
class CorridaAdmin(admin.ModelAdmin):
    list_display = ("paso", "inicio", "fin", "ok", "resumen")
    list_filter = ("paso", "ok")
