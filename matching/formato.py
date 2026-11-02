"""Formatos de presentación compartidos por el decisor y los selectores."""


def pesos(valor: int) -> str:
    return f"$ {valor:,.0f}".replace(",", ".")
