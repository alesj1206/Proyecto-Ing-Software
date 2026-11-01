from django.urls import path

from . import views

urlpatterns = [path("notificaciones", views.notificaciones_view, name="notificaciones")]
