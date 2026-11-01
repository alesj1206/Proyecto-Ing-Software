"""Proveedores de inicio de sesión social. Un proveedor está activo solo si su client_id y su secret
están en el entorno (ver docs/cuentas-sociales.md); los demás no muestran botón."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProveedorSocial:
    id: str  # el id de allauth que usa {% provider_login_url %}
    nombre: str
    variable: str  # prefijo de las variables de entorno: SOCIAL_<variable>_ID / _SECRET


# En el orden en que los muestra el login de Magneto.
PROVEEDORES = (
    ProveedorSocial("linkedin", "LinkedIn", "LINKEDIN"),
    ProveedorSocial("facebook", "Facebook", "FACEBOOK"),
    ProveedorSocial("google", "Google", "GOOGLE"),
    ProveedorSocial("microsoft", "Microsoft", "MICROSOFT"),
)


def _credenciales(proveedor: ProveedorSocial) -> tuple[str, str] | None:
    client_id = os.environ.get(f"SOCIAL_{proveedor.variable}_ID", "").strip()
    secret = os.environ.get(f"SOCIAL_{proveedor.variable}_SECRET", "").strip()
    return (client_id, secret) if client_id and secret else None


def proveedores_activos() -> list[ProveedorSocial]:
    return [p for p in PROVEEDORES if _credenciales(p)]


def settings_proveedores() -> dict:
    """SOCIALACCOUNT_PROVIDERS de allauth, armado con los proveedores activos."""
    config: dict = {}
    for proveedor in proveedores_activos():
        client_id, secret = _credenciales(proveedor)
        app = {"client_id": client_id, "secret": secret}
        if proveedor.id == "linkedin":  # LinkedIn usa OpenID Connect ("Sign In with LinkedIn")
            config.setdefault("openid_connect", {"APPS": []})["APPS"].append({
                **app, "provider_id": "linkedin", "name": "LinkedIn",
                "settings": {"server_url": "https://www.linkedin.com/oauth"},
            })
        elif proveedor.id == "google":
            config["google"] = {"APPS": [app], "SCOPE": ["profile", "email"]}
        elif proveedor.id == "microsoft":
            config["microsoft"] = {"APPS": [{**app, "settings": {"tenant": "common"}}]}
        elif proveedor.id == "facebook":
            config["facebook"] = {"APPS": [app], "METHOD": "oauth2", "SCOPE": ["email", "public_profile"]}
    return config
