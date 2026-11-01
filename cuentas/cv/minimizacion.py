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
    for palabra in (nombre or "").split():  # el nombre de la persona, palabra por palabra
        if len(palabra) >= MIN_LARGO_PALABRA_NOMBRE:
            texto = re.sub(rf"\b{re.escape(palabra)}\b", MARCA, texto, flags=re.IGNORECASE)
    return texto
