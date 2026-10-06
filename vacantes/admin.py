from django.contrib import admin

from .models import ExplicacionCriterio, MatchDiario, Notificacion, Perfil, Postulacion, Vacante

admin.site.register(Perfil)
admin.site.register(Vacante)
admin.site.register(MatchDiario)
admin.site.register(Postulacion)
admin.site.register(ExplicacionCriterio)
admin.site.register(Notificacion)
