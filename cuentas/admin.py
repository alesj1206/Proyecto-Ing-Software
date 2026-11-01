from django.contrib import admin

from .models import Autorizacion, Usuario

admin.site.register(Usuario)
admin.site.register(Autorizacion)
