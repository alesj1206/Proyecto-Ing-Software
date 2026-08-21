from django.urls import path

from . import views

urlpatterns = [
    path("onboarding", views.onboarding_view, name="onboarding"),
    path("perfil", views.perfil_view, name="perfil"),
    path("dashboard", views.dashboard_view, name="dashboard"),
    path("vacantes/<str:vacante_id>", views.detalle_view, name="vacante_detalle"),
]
