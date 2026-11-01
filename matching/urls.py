from django.urls import path

from scoutly.views import pendiente

urlpatterns = [
    path("dashboard", pendiente, name="dashboard"),
    path("historial", pendiente, name="historial"),
    path("vacantes/<str:vacante_id>", pendiente, name="vacante_detalle"),
]
