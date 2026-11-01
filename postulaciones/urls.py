from django.urls import path

from . import views

urlpatterns = [
    path("postulaciones", views.tablero_view, name="tablero"),
    path("vacantes/<str:vacante_id>/postularme", views.postular_view, name="postularme"),
    path("postulaciones/<int:postulacion_id>/estado", views.cambiar_estado_postulacion_view,
         name="cambiar_estado_postulacion"),
]
