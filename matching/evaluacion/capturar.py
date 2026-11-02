"""Exporta vacantes reales de una fuente al formato de `vacantes.json`, sin datos de contacto (spec §10: sin datos
personales). Se usa para ampliar el set de evaluación con vacantes que ninguna mitad ha visto."""

import re

from vacantes.fuentes import FuenteVacantes

CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celulares (3xx xxx xxxx) y fijos con indicativo (60x, con o sin +57). No toca años ("2023 - 2025") ni salarios.
TELEFONO = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\b3\d{2}|\(?\b60\d\)?)[\s-]?\d{3}[\s-]?\d{2,4}\b|\+\d{1,3}")


def sin_contactos(texto: str) -> str:
    return TELEFONO.sub("", CORREO.sub("", texto))


def exportar(fuente: FuenteVacantes, excluir_ids: set[str]) -> list[dict]:
    return [{"id": v.id, "titulo": v.titulo, "empresa": v.empresa, "ubicacion": v.ubicacion, "modalidad": v.modalidad,
             "descripcion": sin_contactos(v.texto_completo), "requisitos": list(v.etiquetas), "url": v.url,
             "fechaPublicacion": v.fecha_publicacion.isoformat(),
             "salario": {"min": v.salario_min, "max": v.salario_max}, "urgente": v.urgente}
            for v in fuente.obtener() if v.id not in excluir_ids]
