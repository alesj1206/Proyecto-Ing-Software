"""Siembra Vacante a partir de vacantes_raw.json.

El dataset incluye a propósito un registro duplicado (mismo id) y uno con
datos rotos (título vacío), tal como en el Sprint 1 original, para ejercitar
el filtrado defensivo. A diferencia del original (que filtraba en cada
lectura), aquí se valida una sola vez al insertar: las vistas ya no repiten
ese trabajo en cada request.
"""

import json

from django.core.management.base import BaseCommand

from vacantes.models import Vacante

FIXTURE_PATH = "vacantes/fixtures/vacantes_raw.json"


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
        with open(FIXTURE_PATH, encoding="utf-8") as f:
            registros = json.load(f)

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
