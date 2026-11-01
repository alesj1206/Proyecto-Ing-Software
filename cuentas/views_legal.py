from django.conf import settings
from django.shortcuts import render

from .legal import FINALIDAD, VERSION_POLITICA, VERSION_TERMINOS


def privacidad_view(request):
    return render(request, "cuentas/privacidad.html", {
        "version": VERSION_POLITICA, "finalidad": FINALIDAD, "contacto": settings.SCOUTLY_CONTACTO_DATOS,
    })


def terminos_view(request):
    return render(request, "cuentas/terminos.html", {"version": VERSION_TERMINOS})
