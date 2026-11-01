import logging
import zlib

from pypdf import PdfReader
from pypdf.errors import PyPdfError

# Lo que pypdf lanza ante un PDF malformado. Un TypeError o un AttributeError siguen siendo bugs y no se ocultan.
ERRORES_DE_PDF = (PyPdfError, ValueError, KeyError, IndexError, RecursionError, zlib.error)
log = logging.getLogger(__name__)

MAX_PAGINAS_CV = 10  # un PDF de miles de páginas no debe tumbar el servidor


def extraer_texto(archivo) -> str:
    """Texto de las primeras páginas del PDF. Un PDF dañado da "" (los demás errores no se ocultan)."""
    try:
        paginas = PdfReader(archivo).pages[:MAX_PAGINAS_CV]
        return "\n".join(pagina.extract_text() or "" for pagina in paginas)
    except ERRORES_DE_PDF as error:
        log.warning("PDF ilegible: %s", error)
        return ""
