from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegistroForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    login_form = LoginForm(request.POST or None) if request.method == "POST" else LoginForm()

    if request.method == "POST" and login_form.is_valid():
        login(request, login_form.get_usuario())
        return redirect("dashboard")

    return render(
        request,
        "accounts/login.html",
        {"login_form": login_form, "registro_form": RegistroForm(), "modo": "login"},
    )


@require_POST
def registro_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    registro_form = RegistroForm(request.POST)
    if registro_form.is_valid():
        usuario = registro_form.guardar()
        login(request, usuario)
        return redirect("onboarding")

    return render(
        request,
        "accounts/login.html",
        {"login_form": LoginForm(), "registro_form": registro_form, "modo": "registro"},
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")
