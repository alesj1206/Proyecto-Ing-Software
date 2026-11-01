from django.urls import path

from scoutly.views import pendiente

from . import views_legal

urlpatterns = [
    path("privacidad", views_legal.privacidad_view, name="privacidad"),
    path("terminos", views_legal.terminos_view, name="terminos"),
    path("login", pendiente, name="login"),
    path("registro", pendiente, name="registro"),
    path("logout", pendiente, name="logout"),
    path("onboarding", pendiente, name="onboarding"),
    path("perfil", pendiente, name="perfil"),
    path("expectativas", pendiente, name="expectativas"),
]
