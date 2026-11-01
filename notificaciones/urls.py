from django.urls import path

from scoutly.views import pendiente

urlpatterns = [
    path("notificaciones", pendiente, name="notificaciones"),
]
