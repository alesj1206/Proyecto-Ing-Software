"""Proveedores de inicio de sesión social (se configuran en la Task 6)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProveedorSocial:
    id: str
    nombre: str


def proveedores_activos() -> list[ProveedorSocial]:
    return []
