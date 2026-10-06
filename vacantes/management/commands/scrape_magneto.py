"""Importa vacantes reales de magneto365.com a vacantes/fixtures/vacantes_magneto.json.

Por qué con un navegador real (Playwright + Chrome) y no con `requests`:
la página de búsqueda de Magneto es una SPA — el HTML que devuelve el
servidor no trae las vacantes, se cargan después por JavaScript. Lo
verificamos en vivo: un fetch simple solo trae el esqueleto de la página
con un mensaje de "cargando resultados".

Por qué por navegador en vez de llamar su API interna directamente:
no hay un endpoint público documentado para la búsqueda de vacantes (los
que sí expone `api.magneto365.com` son para el menú y los filtros, no
para el listado) — así que la única manera confiable es dejar que el
navegador renderice la página, usar el buscador como lo usaría una
persona, y leer el texto ya renderizado.

Respeto al sitio: el robots.txt de Magneto permite expresamente crawling
(incluye bots de IA en la lista de user-agents permitidos) y no bloquea
las rutas de /trabajos/ — solo bloquea URLs con query string ("?"), que
este comando nunca usa (toda la navegación es por interacción con la SPA,
no por URL). Aun así, el comando hace un número acotado de peticiones
(--por-termino, con tope razonable) y espera entre cada una — una sesión
acotada (5 términos, ~20 vacantes), aunque ahora corre automáticamente
una vez al día (HU-11/n8n, primer paso del workflow, antes del scoring)
en vez de ser solo manual.

Uso:
    python manage.py scrape_magneto
    python manage.py scrape_magneto --terminos "desarrollador,devops" --por-termino 5
    python manage.py scrape_magneto --out vacantes/fixtures/vacantes_magneto.json
"""

import hashlib
import json
import re
import time

from django.core.management.base import BaseCommand, CommandError

from vacantes.cv_parser import _normalizar
from vacantes.skills import HABILIDADES_CONOCIDAS

URL_BUSQUEDA = "https://www.magneto365.com/co/trabajos/buscar"
CHROME_PATH = "/usr/bin/google-chrome"

TERMINOS_DEFAULT = [
    "desarrollador",
    "analista de datos",
    "devops",
    "QA software",
    "diseñador UX UI",
]

# Mismo normalizador que cv_parser.py usa para mapear el texto del CV contra
# HABILIDADES_CONOCIDAS — una sola fuente de verdad, para que un requisito
# scrapeado y una habilidad extraída de un CV normalicen exactamente igual
# (acentos, mayúsculas) y de verdad puedan hacer match entre sí.
VOCAB_NORM = {_normalizar(_skill): _skill for _skill in HABILIDADES_CONOCIDAS}


def _mapear_requisitos(habilidades_crudas, titulo, descripcion):
    """Intersecta lo que Magneto lista como habilidades/palabras clave de la
    vacante contra vacantes/skills.py — el matching (matching.py) compara
    requisito vs. habilidad del candidato por igualdad exacta, así que un
    requisito que no esté en ese vocabulario jamás podría hacer match con
    ningún CV, sin importar qué tan real sea el dato scrapeado."""
    encontrados = set()
    for h in habilidades_crudas:
        hn = _normalizar(h)
        for norm_v, original_v in VOCAB_NORM.items():
            if re.search(r"\b" + re.escape(norm_v) + r"\b", hn):
                encontrados.add(original_v)
    if not encontrados:
        texto = _normalizar(titulo + " " + descripcion)
        for norm_v, original_v in VOCAB_NORM.items():
            if re.search(r"\b" + re.escape(norm_v) + r"\b", texto):
                encontrados.add(original_v)
    return sorted(encontrados)


def _limpiar_descripcion(desc_cruda, titulo, empresa):
    patrones = [
        r"^.*?Fecha de publicación \d{4}-\d{2}-\d{2}\s*",
        r"Aplicar\s*Guardar\s*Compartir\s*Expandir\s*Reportar\s*",
        r"Requisitos para aplicar a la vacante:\s*",
        r"\d+\s+años?\s+de experiencia,?\s*[^\n]*",
        r"Salario a convenir",
        r"\$[\d. ]+(?:a\s*\$[\d. ]+)?",
        r"^Palabras clave:\s*",
    ]
    desc = desc_cruda
    for pat in patrones:
        desc = re.sub(pat, " ", desc, flags=re.DOTALL)
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) < 40:
        desc = f"Vacante de {titulo} en {empresa}."
    return desc[:500]


def _id_estable(titulo, empresa):
    """mag-<hash> en vez de mag-<posición en la corrida>: el comando ahora
    corre todos los días (HU-11/n8n) y cada corrida reordena o filtra
    resultados distinto — un id posicional le asignaría el mismo "mag-003"
    a una vacante real distinta de un día para otro, y Postulacion /
    MatchDiario / Notificacion que ya apuntaban a ese id quedarían
    pegadas a la vacante equivocada. El hash de título+empresa es estable:
    la misma publicación real vuelve a mapear al mismo id siempre, sin
    tener que llevar estado entre corridas."""
    clave = _normalizar(f"{titulo}|{empresa}")
    return f"mag-{hashlib.sha1(clave.encode('utf-8')).hexdigest()[:10]}"


def _parsear_bloque(bloque, titulo):
    lineas = bloque.split("\n")
    start = next((i for i, l in enumerate(lineas) if l.strip() == titulo), None)
    if start is None:
        return None
    cuerpo = "\n".join(lineas[start:])

    m_empresa = re.search(r"\n(.+?) \| (.+?), (\d+) cupos", cuerpo)
    empresa = m_empresa.group(1).strip() if m_empresa else "Confidencial"

    m_fecha = re.search(r"Fecha de publicación (\d{4}-\d{2}-\d{2})", cuerpo)
    fecha = m_fecha.group(1) if m_fecha else None
    if not fecha:
        return None

    experiencia_minima = None
    m_req = re.search(r"Requisitos para aplicar a la vacante:\s*\n\s*(.+)", cuerpo)
    if m_req:
        m_anios = re.search(r"(\d+)\s+años?\s+de experiencia", m_req.group(1))
        if m_anios:
            experiencia_minima = int(m_anios.group(1))

    salario_min = salario_max = None
    m_rango = re.search(r"\$\s*([\d.]+)\s*a\s*\$\s*([\d.]+)", cuerpo)
    m_unico = re.search(r"\n\$\s*([\d.]+)\s*\n", cuerpo)
    if m_rango:
        salario_min = int(m_rango.group(1).replace(".", ""))
        salario_max = int(m_rango.group(2).replace(".", ""))
    elif m_unico:
        salario_min = salario_max = int(m_unico.group(1).replace(".", ""))

    m_ubic = re.search(r"(?:convenir|\d\.\d{3}(?:\.\d{3})?)\s*\n([^\n]+)\n", cuerpo)
    ubicacion = (m_ubic.group(1).strip().split(" - ")[0].strip()) if m_ubic else "Colombia"

    m_hab = re.search(r"\nHabilidades\n(.+?)\n\nPalabras clave:", cuerpo, re.DOTALL)
    habilidades_crudas = [h.strip() for h in m_hab.group(1).split("\n") if h.strip()] if m_hab else []

    m_desc = re.search(r"\n([A-ZÁÉÍÓÚÑ].{80,}?)\n\nHabilidades\n", cuerpo, re.DOTALL)
    desc_cruda = m_desc.group(1) if m_desc else cuerpo
    descripcion = _limpiar_descripcion(desc_cruda, titulo, empresa)

    modalidad = "Presencial"
    cuerpo_lower = cuerpo.lower()
    if "híbrid" in cuerpo_lower or "hibrid" in cuerpo_lower:
        modalidad = "Híbrido"
    elif "remoto" in titulo.lower() or "100% remoto" in cuerpo_lower:
        modalidad = "Remoto"

    # Señal real de Magneto, no inferida: el badge "Requerido con urgencia"
    # que la propia plataforma pone sobre algunas vacantes. Alimenta el
    # modificador de disponibilidad (matching.py), no un criterio más.
    urgente = "requerido con urgencia" in cuerpo_lower

    requisitos = _mapear_requisitos(habilidades_crudas, titulo, descripcion)

    return {
        "titulo": titulo.strip(),
        "empresa": empresa,
        "ubicacion": ubicacion,
        "modalidad": modalidad,
        "urgente": urgente,
        "salario": (
            {"min": salario_min, "max": salario_max, "moneda": "COP", "periodo": "mensual"}
            if salario_min is not None
            else None
        ),
        "requisitos": requisitos,
        "descripcion": descripcion,
        "fechaPublicacion": fecha,
        "experienciaMinima": experiencia_minima,
        "fuente": "magneto365.com",
    }


class Command(BaseCommand):
    help = "Importa vacantes reales de magneto365.com (requiere Playwright + Chrome instalados)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--terminos",
            default=",".join(TERMINOS_DEFAULT),
            help="Términos de búsqueda separados por coma.",
        )
        parser.add_argument("--por-termino", type=int, default=4, help="Cuántas vacantes tomar por término.")
        parser.add_argument(
            "--out",
            default="vacantes/fixtures/vacantes_magneto.json",
            help="Dónde guardar el fixture resultante.",
        )
        parser.add_argument(
            "--chrome",
            default=CHROME_PATH,
            help="Ruta al ejecutable de Chrome/Chromium.",
        )

    def handle(self, *args, **options):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise CommandError("Falta playwright — instala con: pip install playwright")

        terminos = [t.strip() for t in options["terminos"].split(",") if t.strip()]
        por_termino = options["por_termino"]
        resultados = []

        try:
            self._scrapear(options, terminos, por_termino, resultados)
        finally:
            # Guardar lo recolectado pase lo que pase — un corte de red a
            # mitad de camino no debe tirar también el trabajo ya hecho.
            # PERO solo si de verdad se recolectó algo: si Chrome ni
            # siquiera logró lanzar (CommandError antes del primer
            # resultado), resultados queda vacío — sobreescribir el
            # fixture con [] borraría el dataset real ya importado en
            # corridas anteriores. Ahora que esto corre solo, sin
            # supervisión, una vez al día (HU-11/n8n), un mal día de Chrome
            # en el host no debe destruir lo que ya se tenía.
            if resultados:
                with open(options["out"], "w", encoding="utf-8") as f:
                    json.dump(resultados, f, ensure_ascii=False, indent=2)
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No se recolectó ninguna vacante — se deja {options['out']} sin tocar."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f"{len(resultados)} vacantes reales guardadas en {options['out']}.")
        )
        self.stdout.write("Corre 'python manage.py seed_vacantes' para cargarlas a la base de datos.")

    def _scrapear(self, options, terminos, por_termino, resultados):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(executable_path=options["chrome"], headless=True, args=["--no-sandbox"])
            except Exception as exc:
                raise CommandError(f"No se pudo lanzar Chrome en '{options['chrome']}': {exc}")

            page = browser.new_page(viewport={"width": 1440, "height": 1400})

            def buscar(termino, intentos=3):
                # Cortes de red transitorios no deben tirar todo el comando
                # ni perder lo ya recolectado — reintenta un par de veces
                # antes de rendirse con ese término.
                for intento in range(intentos):
                    try:
                        page.goto(URL_BUSQUEDA, timeout=30000)
                        page.wait_for_timeout(3500)
                        box = page.get_by_text("Buscar por cargo o profesión").first.bounding_box()
                        if box is None:
                            return False
                        page.mouse.click(box["x"] + 10, box["y"] + 10)
                        page.keyboard.type(termino)
                        page.wait_for_timeout(300)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(3000)
                        return True
                    except Exception as exc:
                        if intento == intentos - 1:
                            self.stdout.write(self.style.WARNING(f"  '{termino}' no cargó tras {intentos} intentos: {exc}"))
                            return False
                        time.sleep(2)
                return False

            for termino in terminos:
                if not buscar(termino):
                    self.stdout.write(self.style.WARNING(f"No se pudo buscar '{termino}', se omite."))
                    continue

                texto_lista = page.inner_text("body")
                lineas = [l.strip() for l in texto_lista.split("\n") if l.strip()]
                indices_titulo = [
                    i + 1
                    for i, l in enumerate(lineas)
                    if l.startswith("Hace ") and i + 1 < len(lineas) and not lineas[i + 1].startswith("Hace")
                ]
                titulos = [lineas[i] for i in indices_titulo]
                # El badge "Requerido con urgencia" de Magneto solo aparece
                # en la tarjeta de la lista, no en el panel de detalle — se
                # captura aquí, antes de hacer click, mirando las líneas de
                # esa misma tarjeta (hasta la siguiente "Hace "). Si dos
                # tarjetas comparten el mismo título, page.get_by_text(...,
                # exact=True).first SIEMPRE hace click en la PRIMERA — así
                # que la urgencia también se mira solo en la primera
                # ocurrencia de cada título, para no contagiarle el badge a
                # una tarjeta distinta que nunca se clickea.
                primera_posicion = {}
                for pos, t in enumerate(titulos):
                    primera_posicion.setdefault(t, pos)

                urgentes = set()
                for t, pos in primera_posicion.items():
                    i = indices_titulo[pos]
                    siguiente = indices_titulo[pos + 1] - 1 if pos + 1 < len(indices_titulo) else len(lineas)
                    if any("Requerido con urgencia" in lineas[j] for j in range(i, siguiente)):
                        urgentes.add(t)

                tomados = 0
                for titulo in titulos:
                    if tomados >= por_termino:
                        break
                    try:
                        page.get_by_text(titulo, exact=True).first.click(timeout=8000)
                        page.wait_for_timeout(2200)
                        texto = page.inner_text("body")
                        idx = texto.rfind("Fecha de publicación")
                        bloque = texto[max(0, idx - 400):idx + 3000]
                        dato = _parsear_bloque(bloque, titulo)
                        if dato:
                            dato["id"] = _id_estable(dato["titulo"], dato["empresa"])
                            dato["urgente"] = dato["urgente"] or titulo in urgentes
                            resultados.append(dato)
                            tomados += 1
                            marca = " [URGENTE]" if dato["urgente"] else ""
                            self.stdout.write(f"  [{dato['id']}] {titulo} -> {dato['empresa']} ({dato['modalidad']}){marca}")
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(f"  omitida '{titulo}': {exc}"))
                    # volver a repetir la búsqueda para el siguiente click —
                    # más lento que navegar dentro de la SPA, pero mucho más
                    # confiable que depender de que el panel de detalle
                    # vuelva a la lista por sí solo.
                    if not buscar(termino):
                        break
                    time.sleep(0.4)

            browser.close()
