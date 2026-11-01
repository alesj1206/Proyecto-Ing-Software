from django.urls import path

from . import views, views_auth, views_legal

urlpatterns = [
    path("privacidad", views_legal.privacidad_view, name="privacidad"),
    path("terminos", views_legal.terminos_view, name="terminos"),
    path("login", views_auth.login_view, name="login"),
    path("registro", views_auth.registro_view, name="registro"),
    path("logout", views_auth.logout_view, name="logout"),
    path("cuentas/verificar/reenviar", views_auth.reenviar_verificacion_view, name="reenviar_verificacion"),
    path("cuentas/verificar/<str:token>", views_auth.verificar_view, name="verificar"),
    path("onboarding", views.onboarding_view, name="onboarding"),
    path("perfil", views.perfil_view, name="perfil"),
    path("cuenta/eliminar", views.eliminar_cuenta_view, name="eliminar_cuenta"),
    path("cuenta/magneto/conectar", views.conectar_magneto_view, name="conectar_magneto"),
    path("cuenta/magneto/callback", views.callback_magneto_view, name="callback_magneto"),
    path("cuenta/magneto/desconectar", views.desconectar_magneto_view, name="desconectar_magneto"),
    path("expectativas", views.expectativas_view, name="expectativas"),
]
