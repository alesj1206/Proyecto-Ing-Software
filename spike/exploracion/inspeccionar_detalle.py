"""Exploración: ¿qué expone el detalle de una vacante en Magneto? (texto completo,
prefiltro, número de postulantes, fecha). Guarda el texto crudo de unas pocas vacantes.
Uso: python -m spike.exploracion.inspeccionar_detalle "analista de datos" 3
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_BUSQUEDA = "https://www.magneto365.com/co/trabajos/buscar"
SALIDA = Path(__file__).resolve().parent / "datos"


def main(termino: str, n: int) -> None:
    capturas = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        respuestas_api = []
        page.on("response", lambda r: respuestas_api.append(r.url) if "json" in (r.headers.get("content-type") or "") else None)

        def buscar():
            page.goto(URL_BUSQUEDA, timeout=30000)
            page.wait_for_timeout(3500)
            box = page.get_by_text("Buscar por cargo o profesión").first.bounding_box()
            page.mouse.click(box["x"] + 10, box["y"] + 10)
            page.keyboard.type(termino)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3500)

        buscar()
        lineas = [l.strip() for l in page.inner_text("body").split("\n") if l.strip()]
        titulos = [lineas[i + 1] for i, l in enumerate(lineas) if l.startswith("Hace ") and i + 1 < len(lineas)][:n]
        for titulo in titulos:
            respuestas_api.clear()
            page.get_by_text(titulo, exact=True).first.click(timeout=8000)
            page.wait_for_timeout(3000)
            capturas.append({"titulo": titulo, "url": page.url, "texto": page.inner_text("body"), "apis_json": sorted(set(respuestas_api))})
            buscar()
            time.sleep(1.5)
        browser.close()
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "detalles_crudos.json").write_text(json.dumps(capturas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(capturas)} capturas")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
