"""Quita datos personales del texto antes de guardarlo como evidencia (Ley 1581, §13.5)."""

import re

MARCA = "[dato personal]"

_PATRONES = [
    # correo
    re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE),
    # celular colombiano (3xx xxx xxxx), con o sin +57
    re.compile(r"(?:\+?57[\s-]?)?\(?\b3\d{2}\)?[\s-]?\d{3}[\s-]?\d{4}\b"),
    # fijo colombiano (60x xxx xxxx)
    re.compile(r"(?:\+?57[\s-]?)?\b60\d[\s-]?\d{3}[\s-]?\d{4}\b"),
    # documento de identidad, solo con palabra guía (para no borrar cifras del CV)
    re.compile(r"\b(?:c\.?\s?c\.?|c[eé]dula|documento|t\.?\s?i\.?|nit)(?=[\s:.#°º]|\b)[\s:.#°ºnNo]*\d[\d.\s-]{5,}\d",
               re.IGNORECASE),
    # dirección: tipo de vía seguido de número
    re.compile(r"\b(?:calle|cl|carrera|cra|kr|avenida|av|diagonal|dg|transversal|tv)\.?\s+\d+\s?[a-z]?"
               r"(?:\s*(?:#|no\.?|n°)\s*\d+\s?[a-z]?(?:\s*-\s*\d+)?)?", re.IGNORECASE),
]


def minimizar(texto: str) -> str:
    for patron in _PATRONES:
        texto = patron.sub(MARCA, texto)
    return texto
