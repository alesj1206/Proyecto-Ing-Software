from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.raiz, name="raiz"),
    path("", include("cuentas.urls")),
    path("", include("postulaciones.urls")),  # antes que matching: "vacantes/<id>/postularme"
    path("", include("matching.urls")),
    path("", include("notificaciones.urls")),
    path("", include("vacantes.urls")),
]
