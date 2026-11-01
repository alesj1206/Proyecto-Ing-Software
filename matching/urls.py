from django.urls import path

from . import views

urlpatterns = [
    path("dashboard", views.dashboard_view, name="dashboard"),
    path("historial", views.historial_view, name="historial"),
    path("vacantes/<str:vacante_id>", views.detalle_view, name="vacante_detalle"),
]
