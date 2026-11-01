from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.raiz, name="raiz"),
    path("", include("cuentas.urls")),
    path("", include("postulaciones.urls")),  # antes que matching: "vacantes/<id>/postularme"
    path("", include("matching.urls")),
    path("", include("notificaciones.urls")),
    path("", include("vacantes.urls")),
    # allauth solo se usa para el login social: sus pantallas propias redirigen a las nuestras.
    path("cuentas/login/", RedirectView.as_view(pattern_name="login")),
    path("cuentas/signup/", RedirectView.as_view(pattern_name="registro")),
    path("cuentas/", include("allauth.urls")),
]
