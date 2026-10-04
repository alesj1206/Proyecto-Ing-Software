from django.urls import path

from . import views

urlpatterns = [
    path("onboarding", views.onboarding_view, name="onboarding"),
    path("perfil", views.perfil_view, name="perfil"),
    path("expectativas", views.expectativas_view, name="expectativas"),
    path("dashboard", views.dashboard_view, name="dashboard"),
    path("vacantes/<str:vacante_id>", views.detalle_view, name="vacante_detalle"),
    path("api/recalcular-matches", views.recalcular_matches_api, name="recalcular_matches_api"),
]
