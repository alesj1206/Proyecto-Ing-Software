from django.urls import path

from . import views

urlpatterns = [
    path("dashboard", views.dashboard_view, name="dashboard"),
    path("historial", views.historial_view, name="historial"),
    path("vacantes/<str:vacante_id>", views.detalle_view, name="vacante_detalle"),
    path("vacantes/<str:vacante_id>/taller", views.taller_view, name="taller"),
    path("vacantes/<str:vacante_id>/explicacion", views.explicacion_view, name="explicacion"),
    path("vacantes/<str:vacante_id>/taller/<int:sugerencia_id>", views.taller_responder_view,
         name="taller_responder"),
]
