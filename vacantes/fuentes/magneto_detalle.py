"""Fuente que abre la página de detalle de cada vacante en magneto365.com y toma su texto completo.

Las vacantes se abren por su URL (/co/empleos/<nombre>-<id>): hacer clic en el listado no cambia el panel de
detalle. `parsear_detalle` es una función pura para poder probarla sin red."""

import logging
import os
import re
import time
from urllib.parse import urlsplit
from collections.abc import Iterator
from datetime import date

from . import VacanteCruda

URL_BUSQUEDA = "https://www.magneto365.com/co/trabajos/buscar"
HOST_MAGNETO = "www.magneto365.com"
CHROME = os.environ.get("SCOUTLY_CHROME") or None  # None = el Chromium que instala Playwright
PAUSA_ENTRE_PAGINAS_S = 1.5  # no saturar el sitio
LINEA_EMPRESA = re.compile(r"^(?P<empresa>.+?) \| .+, \d+ cupos?$")
FECHA = re.compile(r"Fecha de publicación (\d{4}-\d{2}-\d{2})")
INICIO_TEXTO = "Requisitos para aplicar a la vacante:"
# "Palabras clave:" NO es un fin: a veces Magneto lo pone justo después del título, antes de la descripción (la
# extracción lo trata como una sección más que no aporta requisitos).
FINES_TEXTO = ("\nHabilidades\n", "\nVer empresa:", "¡Ten cuidado con el fraude!")

log = logging.getLogger(__name__)


def _recortar(cuerpo: str, inicio: int) -> str:
    fines = [i for marca in FINES_TEXTO if (i := cuerpo.find(marca, inicio)) > 0]
    return cuerpo[inicio: min(fines) if fines else None].strip()


def _etiquetas(cuerpo: str, inicio: int) -> tuple[str, ...]:
    """Las "Habilidades" que Magneto lista al final, entre ese título y "Palabras clave"/"Ver empresa"."""
    desde = cuerpo.find("\nHabilidades\n", inicio)
    if desde < 0:
        return ()
    fines = [i for marca in ("\nPalabras clave:", "\nVer empresa:") if (i := cuerpo.find(marca, desde)) > 0]
    bloque = cuerpo[desde + len("\nHabilidades\n"): min(fines) if fines else None]
    return tuple(linea.strip() for linea in bloque.split("\n") if linea.strip())


def enlaces_validos(hrefs: list[str]) -> list[str]:
    """Solo páginas de detalle de magneto365.com por HTTPS, sin parámetros y sin repetir."""
    urls = []
    for href in hrefs:
        partes = urlsplit(href)
        url = f"https://{HOST_MAGNETO}{partes.path}"
        if (partes.scheme == "https" and partes.hostname == HOST_MAGNETO and partes.path.startswith("/co/empleos/")
                and partes.path.rstrip("/").rsplit("-", 1)[-1].isdigit() and url not in urls):
            urls.append(url)
    return urls


def parsear_detalle(cuerpo: str, url: str) -> VacanteCruda | None:
    cuerpo = cuerpo.replace("\xa0", " ")
    lineas = [l.strip() for l in cuerpo.split("\n") if l.strip()]
    titulo = empresa = None
    for anterior, linea in zip(lineas, lineas[1:]):
        if m := LINEA_EMPRESA.match(linea):
            titulo, empresa = anterior, m.group("empresa").strip()
            break
    inicio = cuerpo.find(INICIO_TEXTO)
    fecha = FECHA.search(cuerpo)
    if not (titulo and inicio >= 0 and fecha):
        return None
    texto = _recortar(cuerpo, inicio)
    resumen = [l.strip() for l in texto.split("\n")[1:] if l.strip()][:4]
    ubicacion = next((resumen[i + 1] for i, l in enumerate(resumen[:-1])
                      if l.startswith("$") or l.lower().startswith("salario a convenir")), "")
    return VacanteCruda(
        id=f"mag-{url.rstrip('/').rsplit('-', 1)[-1]}",
        titulo=titulo,
        empresa=empresa,
        ubicacion=ubicacion,
        modalidad="",
        texto_completo=texto,
        etiquetas=_etiquetas(cuerpo, inicio),
        url=url,
        fecha_publicacion=date.fromisoformat(fecha.group(1)),
        urgente="requerido con urgencia" in cuerpo.lower(),
    )


class FuenteMagnetoDetalle:
    nombre = "magneto"

    def __init__(self, terminos: list[str], por_termino: int, chrome: str = CHROME):
        self.terminos, self.por_termino, self.chrome = terminos, por_termino, chrome

    def obtener(self) -> Iterator[VacanteCruda]:
        # Playwright sync mantiene un event loop activo mientras el navegador está abierto, y Django no permite
        # escribir en la base desde ahí: se juntan todas las vacantes, se cierra el navegador y luego se entregan.
        return iter(self._descargar())

    def _descargar(self) -> list[VacanteCruda]:
        from playwright.sync_api import sync_playwright  # solo se importa si se usa esta fuente

        with sync_playwright() as p:
            navegador = p.chromium.launch(executable_path=self.chrome, headless=True)
            try:
                return self._recorrer(navegador.new_page(viewport={"width": 1440, "height": 1400}))
            finally:
                navegador.close()

    def _recorrer(self, pagina) -> list[VacanteCruda]:
        """Una búsqueda o una página que falla se registra y se salta: no se pierde lo ya descargado."""
        vacantes = []
        for termino in self.terminos:
            try:
                urls = self._enlaces(pagina, termino)
            except Exception:  # timeouts de Playwright, cambios en la página de búsqueda
                log.exception("No se pudo buscar %r en Magneto", termino)
                continue
            for url in urls:
                try:
                    pagina.goto(url, timeout=30000)
                    pagina.wait_for_timeout(2500)
                    vacante = parsear_detalle(pagina.inner_text("body"), url)
                except Exception:
                    log.exception("No se pudo abrir %s", url)
                    continue
                if vacante:
                    vacantes.append(vacante)
                else:
                    log.warning("Sin bloque de detalle en %s", url)
                time.sleep(PAUSA_ENTRE_PAGINAS_S)
        return vacantes

    def _enlaces(self, pagina, termino: str) -> list[str]:
        pagina.goto(URL_BUSQUEDA, timeout=30000)
        pagina.wait_for_timeout(3000)
        caja = pagina.get_by_text("Buscar por cargo o profesión").first.bounding_box()
        if caja is None:
            raise RuntimeError("Magneto cambió la página de búsqueda: no aparece la caja de búsqueda")
        pagina.mouse.click(caja["x"] + 10, caja["y"] + 10)
        pagina.keyboard.type(termino)
        pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(3500)
        hrefs = pagina.eval_on_selector_all("a[href*='/co/empleos/']", "els => els.map(e => e.href)")
        return enlaces_validos(hrefs)[: self.por_termino]
