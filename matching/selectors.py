from vacantes.models import Vacante


def catalogo(modalidad: str = ""):
    vacantes = Vacante.objects.filter(activa=True)
    return vacantes.filter(modalidad=modalidad) if modalidad else vacantes


def total_vacantes() -> int:
    return Vacante.objects.filter(activa=True).count()
