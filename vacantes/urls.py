from django.urls import path

from . import views

urlpatterns = [
    path("onboarding", views.onboarding_view, name="onboarding"),
    path("perfil", views.perfil_view, name="perfil"),
    path("expectativas", views.expectativas_view, name="expectativas"),
    path("dashboard", views.dashboard_view, name="dashboard"),
    path("vacantes/<str:vacante_id>", views.detalle_view, name="vacante_detalle"),
    path("vacantes/<str:vacante_id>/postularme", views.postular_view, name="postularme"),
    path("postulaciones", views.tablero_view, name="tablero"),
    path(
        "postulaciones/<int:postulacion_id>/estado",
        views.cambiar_estado_postulacion_view,
        name="cambiar_estado_postulacion",
    ),
    path("notificaciones", views.notificaciones_view, name="notificaciones"),
    path(
        "api/importar-vacantes",
        views.importar_vacantes_api,
        name="importar_vacantes_api",
    ),
    path("api/recalcular-matches", views.recalcular_matches_api, name="recalcular_matches_api"),
    path(
        "api/generar-notificaciones",
        views.generar_notificaciones_api,
        name="generar_notificaciones_api",
    ),
]
