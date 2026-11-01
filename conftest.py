"""Fixtures compartidas por todas las apps."""

import pytest

CLAVE_DE_PRUEBA = "Lienzo-Tardio-73"


@pytest.fixture
def usuario(db):
    from cuentas.services import crear_usuario_con_autorizacion

    return crear_usuario_con_autorizacion("ana@ejemplo.com", CLAVE_DE_PRUEBA)
