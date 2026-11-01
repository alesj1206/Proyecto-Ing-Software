"""Fábrica de los modelos según la configuración. fastembed solo se importa si se pide el adaptador real."""

from django.conf import settings

from ..puertos import Embedder, Reordenador


def obtener_embedder() -> Embedder:
    if settings.SCOUTLY_EMBEDDER == "falso":
        from .fakes import EmbedderFalso

        return EmbedderFalso()
    from .fastembed import EmbedderFastembed

    return EmbedderFastembed()


def obtener_reordenador() -> Reordenador | None:
    """Apagado por defecto (P1-b): sin GPU el orden es similitud × cobertura."""
    if not settings.SCOUTLY_RERANKER:
        return None
    if settings.SCOUTLY_RERANKER == "falso":
        from .fakes import ReordenadorFalso

        return ReordenadorFalso()
    from .fastembed import ReordenadorFastembed

    return ReordenadorFastembed()
