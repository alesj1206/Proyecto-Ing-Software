from django.shortcuts import redirect


def raiz(request):
    """Punto de llegada tras cualquier login: sin hoja de vida se empieza por onboarding."""
    from cuentas.selectors import perfil_con_cv

    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("dashboard" if perfil_con_cv(request.user) else "onboarding")
