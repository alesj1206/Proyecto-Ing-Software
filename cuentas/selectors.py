from .models import Perfil, Usuario


def perfil_con_cv(usuario: Usuario) -> Perfil | None:
    """El perfil solo si ya cargó la hoja de vida (el de /expectativas puede existir vacío)."""
    perfil = Perfil.objects.filter(usuario=usuario).first()
    return perfil if perfil and perfil.tiene_cv() else None
