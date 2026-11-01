from django.urls import path

from scoutly.views import pendiente

urlpatterns = [
    path("login", pendiente, name="login"),
    path("registro", pendiente, name="registro"),
    path("logout", pendiente, name="logout"),
    path("onboarding", pendiente, name="onboarding"),
    path("perfil", pendiente, name="perfil"),
    path("expectativas", pendiente, name="expectativas"),
]
