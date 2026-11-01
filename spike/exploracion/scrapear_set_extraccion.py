"""Exploración (Task 8 de la Fase 1): baja el bloque de detalle de ~27 vacantes públicas de Magneto, de áreas
variadas, para etiquetar a mano el set de extracción de requisitos. Guarda en datos/ (no se versiona).
Uso: python -m spike.exploracion.scrapear_set_extraccion [desde cuantas archivo.json]
"""

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_BUSQUEDA = "https://www.magneto365.com/co/trabajos/buscar"
TERMINOS = ["analista de datos", "desarrollador", "auxiliar contable", "asesor comercial",
            "auxiliar de enfermeria", "diseñador grafico", "operario de produccion",
            "auxiliar administrativo", "practicante"]
POR_TERMINO = 3
DATOS = Path(__file__).resolve().parent / "datos"


def titulo_de_detalle(cuerpo: str) -> str | None:
    """El título es la línea anterior a "EMPRESA | contrato, N cupos" (la página no tiene <h1>)."""
    lineas = [l.strip() for l in cuerpo.split("\n") if l.strip()]
    for anterior, linea in zip(lineas, lineas[1:]):
        if re.match(r"^.+ \| .+, \d+ cupos?$", linea):
            return anterior
    return None


def enlaces_de_vacantes(page) -> list[str]:
    hrefs = page.eval_on_selector_all("a[href*='/co/empleos/']", "els => els.map(e => e.href)")
    return list(dict.fromkeys(h.split("?")[0] for h in hrefs if h.rsplit("-", 1)[-1].isdigit()))


def main(desde: int = 0, cuantas: int = POR_TERMINO, nombre: str = "set_extraccion_crudo.json") -> None:
    capturas = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        for termino in TERMINOS:
            page.goto(URL_BUSQUEDA, timeout=30000)
            page.wait_for_timeout(3000)
            box = page.get_by_text("Buscar por cargo o profesión").first.bounding_box()
            page.mouse.click(box["x"] + 10, box["y"] + 10)
            page.keyboard.type(termino)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3500)
            for url in enlaces_de_vacantes(page)[desde:desde + cuantas]:
                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(2500)
                    cuerpo = page.inner_text("body")
                    titulo = titulo_de_detalle(cuerpo)
                    if not titulo:
                        raise ValueError("sin bloque de detalle")
                    capturas.append({"termino": termino, "url": url, "titulo": titulo, "bloque": cuerpo})
                    print(f"ok  {termino} | {titulo}", flush=True)
                except Exception as error:  # exploración: se salta la vacante y se sigue
                    print(f"err {termino} | {url}: {error}", flush=True)
                time.sleep(1.5)
        browser.close()
    salida = DATOS / nombre
    salida.write_text(json.dumps(capturas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(capturas)} capturas en {salida}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:  # prueba aparte: python -m ... 3 1 set_prueba_crudo.json
        main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
    else:
        main()
