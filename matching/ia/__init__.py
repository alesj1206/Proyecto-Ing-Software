"""Fábrica de los modelos según la configuración. fastembed solo se importa si se pide el adaptador real."""

from django.conf import settings

from ..puertos import Embedder, Redactor, Reordenador

DIMENSION_COBERTURA = 768  # paraphrase-multilingual-mpnet-base-v2


def obtener_embedder() -> Embedder:
    if settings.SCOUTLY_EMBEDDER == "falso":
        from .fakes import EmbedderFalso

        return EmbedderFalso()
    from .fastembed import EmbedderFastembed

    return EmbedderFastembed()


def obtener_embedder_cobertura() -> Embedder:
    """El modelo de las matrices requisito × evidencia: mpnet (768), que en la prueba preregistrada subió la exactitud
    de 54% a 69% junto con la fusión. La preselección sigue con `obtener_embedder()` (MiniLM, 384)."""
    if settings.SCOUTLY_EMBEDDER == "falso":
        from .fakes import EmbedderFalso

        return EmbedderFalso(DIMENSION_COBERTURA)
    from .fastembed import MODELO_COBERTURA, EmbedderFastembed

    return EmbedderFastembed(MODELO_COBERTURA)


def obtener_reordenador() -> Reordenador | None:
    """Apagado por defecto (P1-b): sin GPU el orden es similitud × cobertura."""
    if not settings.SCOUTLY_RERANKER:
        return None
    if settings.SCOUTLY_RERANKER == "falso":
        from .fakes import ReordenadorFalso

        return ReordenadorFalso()
    from .fastembed import ReordenadorFastembed

    return ReordenadorFastembed()


def obtener_redactor() -> Redactor | None:
    """Groq si hay clave (GROQ_API_KEY); si no, None y se usa el texto de respaldo."""
    if not settings.GROQ_API_KEY:
        return None
    from .groq import RedactorGroq

    return RedactorGroq(settings.GROQ_API_KEY)
