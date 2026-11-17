from django.urls import path

from . import views

urlpatterns = [
    path("api/importar-vacantes", views.importar_vacantes, name="api_importar_vacantes"),
    path("api/decidir", views.decidir, name="api_decidir"),
    path("api/generar-notificaciones", views.notificar, name="api_generar_notificaciones"),
    path("api/estado", views.estado, name="api_estado"),
]
