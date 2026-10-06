"""Siembra Vacante a partir de los fixtures de vacantes/fixtures/.

vacantes_raw.json es el dataset mock del Sprint 1 — incluye a propósito un
registro duplicado (mismo id) y uno con datos rotos (título vacío), para
ejercitar el filtrado defensivo. vacantes_magneto.json (Sprint 2) son
vacantes reales importadas de magneto365.com — ver
vacantes/management/commands/scrape_magneto.py para cómo se obtuvieron.
Los dos se cargan juntos; los ids no chocan (prefijos "vac-" vs "mag-").
"""

import json

from django.core.management.base import BaseCommand

from vacantes.models import Vacante

FIXTURE_PATHS = [
    "vacantes/fixtures/vacantes_raw.json",
    "vacantes/fixtures/vacantes_magneto.json",
]


def es_vacante_valida(registro):
    return bool(
        registro.get("id")
        and registro.get("titulo", "").strip()
        and registro.get("empresa")
        and registro.get("ubicacion")
        and registro.get("modalidad")
    )


class Command(BaseCommand):
    help = "Carga las vacantes de ejemplo, descartando duplicados y registros inválidos."

    def handle(self, *args, **options):
        registros = []
        for ruta in FIXTURE_PATHS:
            with open(ruta, encoding="utf-8") as f:
                registros.extend(json.load(f))

        vistos = set()
        creadas = 0
        descartadas_invalidas = 0
        descartadas_duplicadas = 0

        for registro in registros:
            if not es_vacante_valida(registro):
                descartadas_invalidas += 1
                continue
            if registro["id"] in vistos:
                descartadas_duplicadas += 1
                continue
            vistos.add(registro["id"])

            salario = registro.get("salario")
            Vacante.objects.update_or_create(
                id=registro["id"],
                defaults={
                    "titulo": registro["titulo"],
                    "empresa": registro["empresa"],
                    "ubicacion": registro["ubicacion"],
                    "modalidad": registro["modalidad"],
                    "salario_min": salario["min"] if salario else None,
                    "salario_max": salario["max"] if salario else None,
                    "salario_moneda": salario["moneda"] if salario else None,
                    "salario_periodo": salario["periodo"] if salario else None,
                    "requisitos": registro["requisitos"],
                    "descripcion": registro["descripcion"],
                    "fecha_publicacion": registro["fechaPublicacion"],
                    "experiencia_minima": registro.get("experienciaMinima"),
                    "urgente": registro.get("urgente", False),
                },
            )
            creadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{creadas} vacantes válidas sembradas. "
                f"Descartadas: {descartadas_duplicadas} duplicada(s), "
                f"{descartadas_invalidas} inválida(s)."
            )
        )
