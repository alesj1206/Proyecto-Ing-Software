from django.urls import path

from . import views, views_auth, views_legal

urlpatterns = [
    path("privacidad", views_legal.privacidad_view, name="privacidad"),
    path("terminos", views_legal.terminos_view, name="terminos"),
    path("login", views_auth.login_view, name="login"),
    path("registro", views_auth.registro_view, name="registro"),
    path("logout", views_auth.logout_view, name="logout"),
    path("onboarding", views.onboarding_view, name="onboarding"),
    path("perfil", views.perfil_view, name="perfil"),
    path("expectativas", views.expectativas_view, name="expectativas"),
]
