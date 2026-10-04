"""Port directo de matching.ts: score por coincidencia de palabras clave,
más un ajuste por expectativas laborales (HU-02) cuando el candidato las
definió."""

from dataclasses import dataclass

# Peso de las expectativas dentro del score final. El resto (1 - este peso)
# sigue siendo la coincidencia de habilidades, que es la señal principal.
PESO_EXPECTATIVAS = 0.15


@dataclass
class MatchVacante:
    vacante: object
    score: float
    coincidencias: list


def _score_habilidades(perfil, vacante):
    requisitos = vacante.requisitos
    if not requisitos:
        return 0.0, []

    habilidades_lower = {h.lower() for h in perfil.habilidades} if perfil else set()
    coincidencias = [r for r in requisitos if r.lower() in habilidades_lower]
    score = len(coincidencias) / len(requisitos)
    return score, coincidencias


def _score_expectativas(perfil, vacante):
    """Fracción (0-1) de expectativas declaradas que la vacante cumple.
    Solo cuenta los criterios que el candidato efectivamente definió."""
    if perfil is None or not perfil.tiene_expectativas():
        return None

    criterios_definidos = 0
    criterios_cumplidos = 0

    if perfil.exp_modalidad:
        criterios_definidos += 1
        if perfil.exp_modalidad == vacante.modalidad:
            criterios_cumplidos += 1

    if perfil.exp_salario_min:
        criterios_definidos += 1
        if vacante.salario_max is not None and vacante.salario_max >= perfil.exp_salario_min:
            criterios_cumplidos += 1

    if perfil.exp_ubicacion:
        criterios_definidos += 1
        # Comparación por partes separadas por coma (el placeholder del
        # formulario sugiere "Medellín, remoto en Colombia"): una
        # coincidencia de cualquiera de los dos lados basta, porque
        # vacante.ubicacion es solo una ciudad ("Medellín") y una
        # comparación exacta del texto completo casi nunca sería substring
        # de la otra.
        ubicacion_vacante = vacante.ubicacion.lower()
        partes_esperadas = [p.strip() for p in perfil.exp_ubicacion.lower().split(",") if p.strip()]
        if any(p in ubicacion_vacante or ubicacion_vacante in p for p in partes_esperadas):
            criterios_cumplidos += 1

    if criterios_definidos == 0:
        return None
    return criterios_cumplidos / criterios_definidos


def compute_match(perfil, vacante):
    """score = (1 - w) * coincidencia_habilidades + w * coincidencia_expectativas.
    Si el candidato no definió expectativas, w se redistribuye por completo a
    habilidades (comportamiento idéntico al de antes de HU-02)."""
    score_habilidades, coincidencias = _score_habilidades(perfil, vacante)
    score_expectativas = _score_expectativas(perfil, vacante)

    if score_expectativas is None:
        return score_habilidades, coincidencias

    score = (1 - PESO_EXPECTATIVAS) * score_habilidades + PESO_EXPECTATIVAS * score_expectativas
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
