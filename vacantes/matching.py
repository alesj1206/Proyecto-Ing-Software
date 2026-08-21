"""Port directo de matching.ts: score por coincidencia de palabras clave."""

from dataclasses import dataclass


@dataclass
class MatchVacante:
    vacante: object
    score: float
    coincidencias: list


def compute_match(perfil, vacante):
    """score = |requisitos ∩ habilidades| / |requisitos| (case-insensitive)."""
    requisitos = vacante.requisitos
    if not requisitos:
        return 0.0, []

    habilidades_lower = {h.lower() for h in perfil.habilidades} if perfil else set()
    coincidencias = [r for r in requisitos if r.lower() in habilidades_lower]
    score = len(coincidencias) / len(requisitos)
    return score, coincidencias


def compute_matches_de_hoy(perfil, vacantes):
    """Vacantes con score > 0, ordenadas descendente (el orden de entrada ya
    viene por fecha_publicacion desc, que actúa como desempate estable)."""
    resultados = []
    for vacante in vacantes:
        score, coincidencias = compute_match(perfil, vacante)
        if score > 0:
            resultados.append(MatchVacante(vacante=vacante, score=score, coincidencias=coincidencias))

    resultados.sort(key=lambda m: m.score, reverse=True)
    return resultados
