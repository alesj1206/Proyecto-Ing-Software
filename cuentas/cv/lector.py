from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_PAGINAS_CV = 10  # un PDF de miles de páginas no debe tumbar el servidor


def extraer_texto(archivo) -> str:
    """Texto de las primeras páginas del PDF. Un PDF dañado da "" (los demás errores no se ocultan)."""
    try:
        paginas = PdfReader(archivo).pages[:MAX_PAGINAS_CV]
        return "\n".join(pagina.extract_text() or "" for pagina in paginas)
    except PyPdfError:
        return ""
