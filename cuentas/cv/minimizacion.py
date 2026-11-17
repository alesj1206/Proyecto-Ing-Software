"""Quita datos personales del texto antes de guardarlo como evidencia (Ley 1581, spec §13.5): correo,
teléfono, documento, dirección, edad, género, estado civil y el nombre de la persona."""

import re

MARCA = "[dato personal]"
SEP = r"[\s.-]?"  # 300 123 4567, 300-123-4567 y 300.123.4567

_PATRONES = [
    # correo
    re.compile(r"[\w.%+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE),
    # celular colombiano (3xx xxx xxxx) y fijo (60x xxx xxxx), con o sin +57
    re.compile(rf"(?:\+?57{SEP})?\(?\b(?:3\d{{2}}|60\d)\)?{SEP}\d{{3}}{SEP}\d{{4}}\b"),
    # documento: solo con palabra guía seguida de ":", "#", "No." o directamente de un número largo, para no
    # confundir "Soporte TI 2018 - 2020" o "el documento 2020-2021" con un documento de identidad
    re.compile(r"\b(?:c\.?\s?c\.?|c[eé]dula(?: de ciudadan[ií]a)?|documento(?: de identidad)?|t\.?\s?i\.?|nit)"
               r"\s*(?:[:#]|no\.?|n[°º])?\s*\d[\d.]{5,}\d\b", re.IGNORECASE),
    # dirección: tipo de vía + número [+ letra o sur/este/bis] [# número - número]
    re.compile(r"\b(?:calle|cl|carrera|cra|kr|avenida|av|diagonal|dg|transversal|tv)\.?\s+\d+"
               r"(?:\s?[a-z]\b)?(?:\s+(?:sur|este|norte|bis)\b)?"
               r"(?:\s*(?:#|no\.?|n°)\s*\d+\s?[a-z]?\b(?:\s*-\s*\d+)?)?", re.IGNORECASE),
    # edad, género y estado civil declarados
    re.compile(r"\bedad\s*:?\s*\d{1,2}(?:\s*años)?|\b\d{1,2}\s*años de edad\b", re.IGNORECASE),
    re.compile(r"\b(?:g[eé]nero|sexo)\s*:\s*\w+", re.IGNORECASE),
    re.compile(r"\bestado civil\s*:\s*\w+", re.IGNORECASE),
]
MIN_LARGO_PALABRA_NOMBRE = 3


def minimizar(texto: str, nombre: str | None = None) -> str:
    for patron in _PATRONES:
        texto = patron.sub(MARCA, texto)
    palabras = [re.escape(p) for p in (nombre or "").split() if len(p) >= MIN_LARGO_PALABRA_NOMBRE]
    if palabras:
        una = "(?:" + "|".join(palabras) + ")"
        # Dos o más palabras del nombre seguidas ("Laura Gómez"). Una suelta no se tacha: un apellido como "Cruz" o
        # "León" también puede ser parte de la experiencia ("Cruz Verde"). Un nombre de una sola palabra sí.
        patron = rf"\b{una}(?:\s+{una})+\b" if len(palabras) > 1 else rf"\b{una}\b"
        texto = re.sub(patron, MARCA, texto, flags=re.IGNORECASE)
    return texto
