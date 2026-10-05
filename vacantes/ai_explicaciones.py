"""Explicaciones por criterio generadas por IA (Groq, modelo gratuito) para
el desglose de compatibilidad en el detalle de vacante.

Nunca se llama a la API en cada vista de página: obtener_explicacion()
primero busca en ExplicacionCriterio (vacantes/models.py) una fila para
ese candidato+vacante+criterio, y solo llama a Groq si no existe o si el
score_pct cambió desde la última vez (CV o expectativas actualizadas). Si
la llamada falla por cualquier motivo (sin API key, red caída, límite de
cuota), se devuelve un texto de respaldo simple en vez de romper la
página — la explicación es un complemento, no algo de lo que depender
para que /vacantes/<id> cargue.
"""

import logging

import requests
from django.conf import settings

from .models import ExplicacionCriterio

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 8  # segundos — una explicación no debe colgar la carga de la página

# Tolerancia al comparar el score_pct cacheado contra el recién calculado:
# redondeos de punto flotante entre llamadas no deben disparar una
# regeneración innecesaria.
TOLERANCIA_SCORE = 0.5

SYSTEM_PROMPT = (
    "Eres el motor de explicaciones de Scoutly, una plataforma de empleo "
    "colombiana. Para un criterio de compatibilidad entre un candidato y "
    "una vacante, recibes el puntaje ya calculado y los datos exactos que "
    "lo producen. Escribe UNA sola oración en español, clara y específica, "
    "que justifique ese puntaje citando los datos reales que te dan — "
    "nunca una frase genérica que serviría para cualquier vacante. No "
    "repitas el número de puntaje en la respuesta (ya se muestra aparte). "
    "No uses markdown. Máximo 220 caracteres."
)


def _prompt_usuario(criterio):
    c = criterio.criterio
    d = criterio.detalle

    if c == "habilidades":
        if d["coincidencias"]:
            return (
                f"Criterio: habilidades. El candidato tiene {len(d['coincidencias'])} de "
                f"{d['total_requisitos']} habilidades que pide la vacante: "
                f"{', '.join(d['coincidencias'])}. "
                f"Le faltan: {', '.join(d['faltantes']) or 'ninguna'}."
            )
        return (
            f"Criterio: habilidades. El candidato no tiene ninguna de las "
            f"{d['total_requisitos']} habilidades que pide la vacante: "
            f"{', '.join(d['faltantes'])}."
        )

    if c == "experiencia":
        return (
            f"Criterio: experiencia. El candidato declara {d['anios_candidato']} años de "
            f"experiencia; la vacante exige un mínimo de {d['anios_minimos']} años."
        )

    if c == "salario":
        moneda = d.get("moneda") or "COP"
        return (
            f"Criterio: salario. La vacante ofrece hasta {moneda} {d['salario_ofrecido']:,.0f}; "
            f"el candidato espera un mínimo de {moneda} {d['salario_esperado']:,.0f}."
        ).replace(",", ".")

    if c == "modalidad":
        return (
            f"Criterio: modalidad. La vacante es {d['modalidad_vacante']}; "
            f"el candidato busca {d['modalidad_esperada']}."
        )

    if c == "ubicacion":
        return (
            f"Criterio: ubicación. La vacante está en {d['ubicacion_vacante']}; "
            f"el candidato busca en {d['ubicacion_esperada']}."
        )

    raise ValueError(f"criterio desconocido: {c}")


def _texto_respaldo(criterio):
    """Si Groq no responde, una frase simple derivada del mismo detalle —
    no tan rica como la de la IA, pero nunca genérica ni inventada."""
    c = criterio.criterio
    d = criterio.detalle

    if c == "habilidades":
        if d.get("coincidencias"):
            return f"Coincide en {len(d['coincidencias'])} de {d['total_requisitos']} habilidades pedidas."
        return "No coincide en ninguna de las habilidades que pide esta vacante."
    if c == "experiencia":
        return f"Declaras {d['anios_candidato']} años de experiencia; la vacante pide {d['anios_minimos']}."
    if c == "salario":
        return "El salario ofrecido cumple tu mínimo esperado." if criterio.score_pct >= 100 else "El salario ofrecido no alcanza tu mínimo esperado."
    if c == "modalidad":
        return f"La vacante es {d['modalidad_vacante']}; buscas {d['modalidad_esperada']}."
    if c == "ubicacion":
        return f"La vacante está en {d['ubicacion_vacante']}; buscas en {d['ubicacion_esperada']}."
    return ""


def _llamar_groq(criterio):
    api_key = settings.GROQ_API_KEY
    if not api_key:
        return None

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _prompt_usuario(criterio)},
                ],
                "temperature": 0.4,
                "max_tokens": 120,
            },
            timeout=GROQ_TIMEOUT,
        )
        resp.raise_for_status()
        texto = resp.json()["choices"][0]["message"]["content"].strip()
        return texto or None
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.warning("Groq no respondió para el criterio %s: %s", criterio.criterio, exc)
        return None


def obtener_explicacion(perfil, vacante, criterio):
    """criterio: un matching.CriterioResultado. Devuelve el texto (de caché,
    de Groq, o de respaldo) — nunca None ni levanta una excepción."""
    if not criterio.aplica:
        return None

    texto, score_a_guardar = resolver_explicacion(perfil, vacante, criterio)
    if score_a_guardar is not None:
        guardar_explicacion(perfil, vacante, criterio.criterio, score_a_guardar, texto)
    return texto


def resolver_explicacion(perfil, vacante, criterio):
    """Mitad "lectura" de obtener_explicacion: consulta la caché y, si hace
    falta, llama a Groq — pero NUNCA escribe en la base de datos. Pensada
    para llamarse desde varios hilos a la vez (detalle_view paraleliza las
    llamadas a Groq de los criterios sin caché): SQLite no tolera
    escrituras concurrentes — un segundo hilo escribiendo mientras otro
    todavía no confirma su INSERT/UPDATE revienta con
    "django.db.utils.OperationalError: database is locked", así que la
    escritura real queda en guardar_explicacion(), para que el caller la
    haga en serie en el hilo principal después de juntar todos los
    resultados.

    Devuelve (texto, score_pct_a_guardar). score_pct_a_guardar es None
    cuando el texto vino de la caché y no hay nada que reescribir."""
    if not criterio.aplica:
        return None, None

    cacheada = ExplicacionCriterio.objects.filter(
        perfil=perfil, vacante=vacante, criterio=criterio.criterio
    ).first()
    if cacheada and abs(cacheada.score_pct - criterio.score_pct) <= TOLERANCIA_SCORE:
        return cacheada.texto, None

    texto = _llamar_groq(criterio) or _texto_respaldo(criterio)
    return texto, criterio.score_pct


def guardar_explicacion(perfil, vacante, criterio_nombre, score_pct, texto):
    ExplicacionCriterio.objects.update_or_create(
        perfil=perfil,
        vacante=vacante,
        criterio=criterio_nombre,
        defaults={"score_pct": score_pct, "texto": texto},
    )
