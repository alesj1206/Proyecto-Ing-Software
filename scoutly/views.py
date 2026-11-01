from django.http import HttpResponse
from django.shortcuts import redirect


def raiz(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")


def pendiente(request, *args, **kwargs):
    """Ruta reservada: su vista la implementa una tarea posterior de la Fase 1 (se borra en la Task 10)."""
    return HttpResponse("En construcción", status=501)
