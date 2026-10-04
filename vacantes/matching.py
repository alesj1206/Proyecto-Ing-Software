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


def _modalidad_coincide(perfil, vacante):
    return bool(perfil.exp_modalidad) and perfil.exp_modalidad == vacante.modalidad


def _salario_coincide(perfil, vacante):
    return (
        bool(perfil.exp_salario_min)
        and vacante.salario_max is not None
        and vacante.salario_max >= perfil.exp_salario_min
    )


def _ubicacion_coincide(perfil, vacante):
    if not perfil.exp_ubicacion:
        return False
    # Comparación por partes separadas por coma (el placeholder del
    # formulario sugiere "Medellín, remoto en Colombia"): una coincidencia
    # de cualquiera de los dos lados basta, porque vacante.ubicacion es solo
    # una ciudad ("Medellín") y una comparación exacta del texto completo
    # casi nunca sería substring de la otra.
    ubicacion_vacante = vacante.ubicacion.lower()
    partes_esperadas = [p.strip() for p in perfil.exp_ubicacion.lower().split(",") if p.strip()]
    return any(p in ubicacion_vacante or ubicacion_vacante in p for p in partes_esperadas)


def _score_expectativas(perfil, vacante):
    """Fracción (0-1) de expectativas declaradas que la vacante cumple.
    Solo cuenta los criterios que el candidato efectivamente definió."""
    if perfil is None or not perfil.tiene_expectativas():
        return None

    criterios_definidos = 0
    criterios_cumplidos = 0

    if perfil.exp_modalidad:
        criterios_definidos += 1
        criterios_cumplidos += _modalidad_coincide(perfil, vacante)

    if perfil.exp_salario_min:
        criterios_definidos += 1
        criterios_cumplidos += _salario_coincide(perfil, vacante)

    if perfil.exp_ubicacion:
        criterios_definidos += 1
        criterios_cumplidos += _ubicacion_coincide(perfil, vacante)

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


def explicar_match(perfil, vacante):
    """HU-07: razones legibles de por qué se recomendó esta vacante.
    Construidas con los mismos helpers que compute_match usa para el score
    (_score_habilidades, _modalidad_coincide, _salario_coincide,
    _ubicacion_coincide) — nunca puede mostrar una razón que el número no
    respalde, porque no hay una segunda copia de la lógica de comparación."""
    if perfil is None:
        return []

    razones = []
    _, coincidencias = _score_habilidades(perfil, vacante)
    if len(coincidencias) == 1:
        razones.append(f'Tienes la habilidad "{coincidencias[0]}", que esta vacante requiere.')
    elif coincidencias:
        listadas = ", ".join(coincidencias[:4])
        razones.append(
            f"Coincides en {len(coincidencias)} de {len(vacante.requisitos)} "
            f"habilidades requeridas: {listadas}."
        )

    if _modalidad_coincide(perfil, vacante):
        razones.append(f"La modalidad ({vacante.modalidad}) es la que buscas.")
    if _salario_coincide(perfil, vacante):
        razones.append("El salario ofrecido cumple tu expectativa mínima.")
    if _ubicacion_coincide(perfil, vacante):
        razones.append(f"La ubicación ({vacante.ubicacion}) coincide con tu preferencia.")

    if len(razones) < 2:
        score, _ = compute_match(perfil, vacante)
        if score > 0:
            razones.append(f"En conjunto, coincides en el {round(score * 100)}% de lo que pide esta vacante.")

    return razones


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
