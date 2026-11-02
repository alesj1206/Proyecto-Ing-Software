"""Exporta vacantes reales de una fuente al formato de `vacantes.json`, sin datos de contacto (spec §10: sin datos
personales). Se usa para ampliar el set de evaluación con vacantes que ninguna mitad ha visto."""

import re

from vacantes.fuentes import FuenteVacantes

MAX_LARGO = 20_000  # las expresiones son lineales, pero el texto scrapeado puede ser enorme
SEP = r"[\s.\-()]*"
CORREO = re.compile(r"[\w.+-]{1,64}\s*(?:@|\[at\]|\(at\)|\barroba\b)\s*[\w-]{1,63}(?:\.[\w-]{1,63})+", re.IGNORECASE)
WHATSAPP = re.compile(r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com)/\S*", re.IGNORECASE)
TELEFONO = re.compile(
    rf"(?:\+?57{SEP})?(?:3\d{{2}}|60\d){SEP}\d{{3}}{SEP}\d{{2}}{SEP}\d{{2}}"  # celular y fijo con indicativo 60x
    rf"|(?<![\d$.,])\d{{3}}[\s\-]\d{{2}}[\s\-]\d{{2}}(?!\d|\.\d)"               # fijo viejo de 7 dígitos: 444 55 66
    rf"|\+\d{{1,3}}")
CEDULA = re.compile(r"\b(?:c\.?\s?c\.?|c[eé]dula)\s*(?:no\.?|n[°º])?\s*[\d.\s]{6,15}", re.IGNORECASE)
# Lo que quede después de limpiar y aún parezca un contacto obliga a revisar la vacante a mano.
SOSPECHOSO = re.compile(r"@|\d{7,}")


def sin_contactos(texto: str) -> str:
    texto = texto[:MAX_LARGO]
    for patron in (WHATSAPP, CORREO, CEDULA, TELEFONO):
        texto = patron.sub("", texto)
    return texto


CODIGO_MAGNETO = re.compile(r"\b\d{5,10}-\d{1,5}\b|\bmag-\d+\b")  # 1626532605-3, 224827-36415
SALARIO = re.compile(r"(?:\$|\bcop\b|salari\w*|asignaci\w*|entre|hasta)[^\d\n]{0,15}[\d.,]+(?:\s*(?:a|-|y)\s*[\d.,]+)?",
                     re.IGNORECASE)


def _sospechoso(texto: str) -> bool:
    sin_conocidos = SALARIO.sub("", CODIGO_MAGNETO.sub("", texto))
    sin_separadores = re.sub(r"(?<=\d)[\s\-]+(?=\d)", "", sin_conocidos)  # "444 55 66" → 4445566
    return bool(SOSPECHOSO.search(sin_separadores))


def exportar(fuente: FuenteVacantes, excluir_ids: set[str], rechazadas: list[str] | None = None) -> list[dict]:
    """Las vacantes nuevas, limpias. Las que aún parecen tener un contacto van a `rechazadas` para revisarlas a mano."""
    registros = []
    for v in fuente.obtener():
        if v.id in excluir_ids:
            continue
        descripcion = sin_contactos(v.texto_completo)
        if _sospechoso(descripcion):
            if rechazadas is not None:
                rechazadas.append(v.id)
            continue
        registros.append({"id": v.id, "titulo": v.titulo, "empresa": v.empresa, "ubicacion": v.ubicacion,
                          "modalidad": v.modalidad, "descripcion": descripcion, "requisitos": list(v.etiquetas),
                          "url": v.url, "fechaPublicacion": v.fecha_publicacion.isoformat(),
                          "salario": {"min": v.salario_min, "max": v.salario_max}, "urgente": v.urgente})
    return registros
