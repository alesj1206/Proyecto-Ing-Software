from django.urls import path

from scoutly.views import pendiente

urlpatterns = [
    path("postulaciones", pendiente, name="tablero"),
    path("vacantes/<str:vacante_id>/postularme", pendiente, name="postularme"),
    path("postulaciones/<int:postulacion_id>/estado", pendiente, name="cambiar_estado_postulacion"),
]
