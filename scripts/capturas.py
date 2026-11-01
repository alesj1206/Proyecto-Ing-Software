"""Capturas de todas las páginas para comparar el visual de v2 contra v3 (Fase 1, Task 11).

Uso:
  python scripts/capturas.py --base http://127.0.0.1:8802 --salida docs/fase1/capturas/despues \
      --usuario visual@ejemplo.com --clave Lienzo-Tardio-73 --cv cv.pdf --vacante mag-xxxx [--v2]
  python scripts/capturas.py --comparar docs/fase1/capturas/antes docs/fase1/capturas/despues
"""

import argparse
from pathlib import Path

PAGINAS_CON_SESION = ["onboarding", "perfil", "expectativas", "dashboard", "historial", "postulaciones",
                      "notificaciones"]
ANCHO, ALTO = 1440, 900


def _ingresar(pagina, base: str, usuario: str, clave: str, v2: bool) -> None:
    pagina.goto(f"{base}/login")
    pagina.fill("input[name=email]", usuario)
    if v2:  # v2: correo y contraseña en el mismo formulario
        pagina.fill("#form-login input[name=password]", clave)
        pagina.click("#form-login button[type=submit]")
    else:  # v3: correo primero, contraseña después
        pagina.click("form.auth-form button[type=submit]")
        pagina.fill("input[name=password]", clave)
        pagina.click("form.auth-form button[type=submit]")
    pagina.wait_for_load_state("networkidle")


def capturar(base: str, salida: Path, usuario: str, clave: str, cv: Path | None, vacante: str, v2: bool) -> None:
    from playwright.sync_api import sync_playwright

    salida.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
        pagina = navegador.new_page(viewport={"width": ANCHO, "height": ALTO})

        def foto(nombre: str, ruta: str) -> None:
            pagina.goto(f"{base}/{ruta}")
            pagina.wait_for_load_state("networkidle")
            pagina.wait_for_timeout(600)
            pagina.screenshot(path=str(salida / f"{nombre}.png"), full_page=True)

        foto("login", "login")
        foto("registro", "registro")
        _ingresar(pagina, base, usuario, clave, v2)
        foto("onboarding", "onboarding")
        if cv:  # sin --cv se usa el CV que el usuario ya tiene (p. ej. para capturar sus decisiones)
            pagina.set_input_files("input[type=file]", str(cv))
            pagina.click("form[enctype='multipart/form-data'] button[type=submit]")
            pagina.wait_for_load_state("networkidle")
        for ruta in PAGINAS_CON_SESION[1:]:
            foto(ruta, ruta)
        foto("detalle", f"vacantes/{vacante}")
        navegador.close()


def diferencia(a: Path, b: Path) -> float:
    """Fracción de píxeles distintos (sobre el área de la imagen más grande)."""
    import numpy as np
    from PIL import Image, ImageChops

    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    ancho, alto = max(ia.width, ib.width), max(ia.height, ib.height)
    lienzo_a, lienzo_b = Image.new("RGB", (ancho, alto), "white"), Image.new("RGB", (ancho, alto), "white")
    lienzo_a.paste(ia), lienzo_b.paste(ib)
    return float(np.asarray(ImageChops.difference(lienzo_a, lienzo_b)).any(axis=2).mean())


def comparar(antes: Path, despues: Path) -> None:
    for imagen in sorted(antes.glob("*.png")):
        otra = despues / imagen.name
        if otra.exists():
            print(f"{imagen.stem:15} {diferencia(imagen, otra) * 100:6.2f} %")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--salida", type=Path)
    ap.add_argument("--usuario")
    ap.add_argument("--clave")
    ap.add_argument("--cv", type=Path)
    ap.add_argument("--vacante")
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--comparar", nargs=2, type=Path)
    args = ap.parse_args()
    if args.comparar:
        comparar(*args.comparar)
    else:
        capturar(args.base, args.salida, args.usuario, args.clave, args.cv, args.vacante, args.v2)


if __name__ == "__main__":
    main()
