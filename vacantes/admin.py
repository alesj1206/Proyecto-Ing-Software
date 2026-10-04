from django.contrib import admin

from .models import MatchDiario, Perfil, Postulacion, Vacante

admin.site.register(Perfil)
admin.site.register(Vacante)
admin.site.register(MatchDiario)
admin.site.register(Postulacion)
