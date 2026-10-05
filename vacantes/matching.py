"""Motor de matching — 5 criterios independientes, cada uno con su propio
peso e índice de afinidad continuo (0-100%, no solo sí/no). Si un criterio
no tiene datos suficientes para evaluarse (el candidato no declaró esa
expectativa, o la vacante no exige una antigüedad mínima), se excluye y su
peso se reparte proporcionalmente entre los que sí aplican — habilidades
siempre aplica, así que el score final nunca queda sin ningún criterio.
"""

from dataclasses import dataclass, field

PESOS = {
    "habilidades": 0.40,
    "experiencia": 0.20,
    "salario": 0.15,
    "modalidad": 0.15,
    "ubicacion": 0.10,
}

ETIQUETAS = {
    "habilidades": "Habilidades",
    "experiencia": "Experiencia",
    "salario": "Salario",
    "modalidad": "Modalidad",
    "ubicacion": "Ubicación",
}


@dataclass
class MatchVacante:
    vacante: object
    score: float
    coincidencias: list


@dataclass
class CriterioResultado:
    criterio: str
    etiqueta: str
    peso: float
    score_pct: float
    aplica: bool
    # Datos crudos del cálculo — se los pasamos tal cual al prompt de la IA
    # (vacantes/ai_explicaciones.py) para que la explicación cite números
    # reales en vez de inventar una justificación genérica.
    detalle: dict = field(default_factory=dict)
    # Por qué aplica=False, para que la UI no siempre apunte al candidato
    # ("completa tus expectativas") cuando en realidad es la vacante la que
    # no trae el dato (p. ej. no exige una experiencia mínima).
    razon_no_aplica: str = ""
    # True solo cuando razon_no_aplica describe algo que el candidato puede
    # arreglar en /expectativas — si el dato que falta es de la vacante
    # (salario no especificado, sin experiencia mínima), no tiene sentido
    # mandarlo a ese formulario.
    es_del_candidato: bool = False


def _score_habilidades(perfil, vacante):
    requisitos = vacante.requisitos
    if not requisitos:
        return 0.0, []

    habilidades_lower = {h.lower() for h in perfil.habilidades} if perfil else set()
    coincidencias = [r for r in requisitos if r.lower() in habilidades_lower]
    score = len(coincidencias) / len(requisitos)
    return score, coincidencias


# Afinidad entre la modalidad que pide la vacante y la que busca el
# candidato. No es binario: Híbrido es un punto medio real entre Remoto y
# Presencial, así que pedir Remoto y encontrar un Híbrido no es lo mismo
# que encontrar un Presencial estricto (eso sí es la combinación opuesta,
# 0%). Clave: (vacante.modalidad, perfil.exp_modalidad).
MODALIDAD_AFINIDAD = {
    ("Remoto", "Remoto"): 100,
    ("Presencial", "Presencial"): 100,
    ("Híbrido", "Híbrido"): 100,
    ("Híbrido", "Remoto"): 50,
    ("Remoto", "Híbrido"): 50,
    ("Híbrido", "Presencial"): 50,
    ("Presencial", "Híbrido"): 50,
    ("Remoto", "Presencial"): 0,
    ("Presencial", "Remoto"): 0,
}


def _modalidad_coincide(perfil, vacante):
    return bool(perfil.exp_modalidad) and perfil.exp_modalidad == vacante.modalidad


def _modalidad_afinidad_pct(perfil, vacante):
    return MODALIDAD_AFINIDAD.get((vacante.modalidad, perfil.exp_modalidad), 0)


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


def _criterio_habilidades(perfil, vacante):
    score, coincidencias = _score_habilidades(perfil, vacante)
    faltantes = [r for r in vacante.requisitos if r not in coincidencias]
    return CriterioResultado(
        criterio="habilidades",
        etiqueta=ETIQUETAS["habilidades"],
        peso=PESOS["habilidades"],
        score_pct=score * 100,
        aplica=True,
        detalle={
            "coincidencias": coincidencias,
            "faltantes": faltantes,
            "total_requisitos": len(vacante.requisitos),
        },
    )


def _criterio_experiencia(perfil, vacante):
    minimo = vacante.experiencia_minima
    anios = perfil.anios_experiencia

    if minimo is None:
        return CriterioResultado(
            "experiencia", ETIQUETAS["experiencia"], PESOS["experiencia"], 0.0, False,
            razon_no_aplica="Esta vacante no especifica una experiencia mínima.",
        )
    if anios is None:
        return CriterioResultado(
            "experiencia", ETIQUETAS["experiencia"], PESOS["experiencia"], 0.0, False,
            razon_no_aplica="No declaraste tus años de experiencia.",
            es_del_candidato=True,
        )

    # minimo == 0 ("sin experiencia previa requerida") lo cumple cualquier
    # candidato — min()/max() evita la división por cero sin tratar "0 años
    # mínimos" como "no aplica" (ver hallazgo de revisión: `if not minimo`
    # excluía por error el caso 0, que es un valor válido y distinto de None).
    pct = 100.0 if minimo == 0 else min(100.0, (anios / minimo) * 100)
    return CriterioResultado(
        "experiencia",
        ETIQUETAS["experiencia"],
        PESOS["experiencia"],
        pct,
        True,
        {"anios_candidato": anios, "anios_minimos": minimo},
    )


def _criterio_salario(perfil, vacante):
    if vacante.salario_max is None:
        return CriterioResultado(
            "salario", ETIQUETAS["salario"], PESOS["salario"], 0.0, False,
            razon_no_aplica="Esta vacante no especifica salario.",
        )
    if not perfil.exp_salario_min:
        return CriterioResultado(
            "salario", ETIQUETAS["salario"], PESOS["salario"], 0.0, False,
            razon_no_aplica="No declaraste tu salario mínimo esperado.",
            es_del_candidato=True,
        )

    pct = min(100.0, (vacante.salario_max / perfil.exp_salario_min) * 100)
    return CriterioResultado(
        "salario",
        ETIQUETAS["salario"],
        PESOS["salario"],
        pct,
        True,
        {
            "salario_ofrecido": vacante.salario_max,
            "salario_esperado": perfil.exp_salario_min,
            "moneda": vacante.salario_moneda,
        },
    )


def _criterio_modalidad(perfil, vacante):
    if not perfil.exp_modalidad:
        return CriterioResultado(
            "modalidad", ETIQUETAS["modalidad"], PESOS["modalidad"], 0.0, False,
            razon_no_aplica="No declaraste tu modalidad preferida.",
            es_del_candidato=True,
        )

    return CriterioResultado(
        "modalidad",
        ETIQUETAS["modalidad"],
        PESOS["modalidad"],
        float(_modalidad_afinidad_pct(perfil, vacante)),
        True,
        {"modalidad_vacante": vacante.modalidad, "modalidad_esperada": perfil.exp_modalidad},
    )


def _criterio_ubicacion(perfil, vacante):
    if not perfil.exp_ubicacion:
        return CriterioResultado(
            "ubicacion", ETIQUETAS["ubicacion"], PESOS["ubicacion"], 0.0, False,
            razon_no_aplica="No declaraste tu ubicación preferida.",
            es_del_candidato=True,
        )

    coincide = _ubicacion_coincide(perfil, vacante)
    return CriterioResultado(
        "ubicacion",
        ETIQUETAS["ubicacion"],
        PESOS["ubicacion"],
        100.0 if coincide else 0.0,
        True,
        {"ubicacion_vacante": vacante.ubicacion, "ubicacion_esperada": perfil.exp_ubicacion},
    )


def evaluar_criterios(perfil, vacante):
    """Los 5 criterios para este candidato+vacante. Habilidades siempre
    aparece (y siempre aplica); los demás solo si hay datos para evaluarlos
    — pero igual se incluyen en la lista con aplica=False, para que la UI
    pueda mostrar "no declaraste esta expectativa" en vez de omitirlos."""
    if perfil is None:
        return []
    return [
        _criterio_habilidades(perfil, vacante),
        _criterio_experiencia(perfil, vacante),
        _criterio_salario(perfil, vacante),
        _criterio_modalidad(perfil, vacante),
        _criterio_ubicacion(perfil, vacante),
    ]


def compute_match(perfil, vacante):
    """score = promedio ponderado de los criterios que aplican, con los
    pesos de PESOS renormalizados a 1 entre esos criterios. Devuelve
    (score 0-1, coincidencias de habilidades) — la forma que ya esperan
    scoring.py y las vistas."""
    criterios = evaluar_criterios(perfil, vacante)
    if not criterios:
        return 0.0, []

    aplicables = [c for c in criterios if c.aplica]
    peso_total = sum(c.peso for c in aplicables)
    score = (sum(c.peso * c.score_pct for c in aplicables) / peso_total / 100) if peso_total else 0.0

    coincidencias = next(
        (c.detalle.get("coincidencias", []) for c in criterios if c.criterio == "habilidades"), []
    )
    return score, coincidencias


def explicar_match(perfil, vacante):
    """HU-07: razones cortas (sin IA, instantáneas) para la tarjeta del
    dashboard. El desglose completo con explicación por IA de cada
    criterio vive en vacantes/ai_explicaciones.py y se muestra solo en el
    detalle de la vacante."""
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
