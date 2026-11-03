"""Recorrido de usuario real con navegador contra una copia aislada (scoutly_bench, correo por consola)."""
import os, re, sys, tempfile, time
from pathlib import Path
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scoutly.settings"); sys.path.insert(0, os.getcwd())
import django; django.setup()
import yaml
from playwright.sync_api import sync_playwright
from cuentas.tests.cvs import pdf_cv
BASE, LOG, SAL = "http://localhost:8001", Path(sys.argv[1]), Path(sys.argv[2])
CORREO = f"e2e-{int(time.time())}@correo-ficticio.co"
cv = yaml.safe_load(Path("matching/evaluacion/cvs.yaml").read_text(encoding="utf-8"))["datos_junior"]
pdf = pdf_cv("cv.pdf", nombre=cv["nombre"], contacto=cv.get("contacto"), experiencia=cv["experiencia"], educacion=tuple(cv.get("educacion", ())), habilidades=cv.get("habilidades"))
ruta = Path(tempfile.mkdtemp()) / "cv.pdf"; ruta.write_bytes(pdf.read() if hasattr(pdf, "read") else bytes(pdf))
malas = []
def paso(n, msg): print(f"[{n}] {msg}", flush=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("SCOUTLY_CHROME") or "/usr/bin/google-chrome", headless=True)
    pg = b.new_page(viewport={"width": 1280, "height": 1000})
    pg.on("response", lambda r: malas.append((r.status, r.url)) if r.status >= 400 else None)
    pg.on("pageerror", lambda e: malas.append(("js", str(e)[:100])))
    pg.goto(BASE + "/registro"); pg.fill("input[name=email]", CORREO); pg.fill("input[name=email_confirmacion]", CORREO)
    pg.check("input[name=autoriza_datos]"); pg.check("input[name=acepta_terminos]"); pg.click("button:has-text('Siguiente')")
    pg.fill("input[name=password1]", "Lienzo-Tardio-73"); pg.fill("input[name=password2]", "Lienzo-Tardio-73"); pg.click("button:has-text('Crear cuenta')")
    pg.wait_for_load_state(); paso(1, f"registro -> {pg.url}")
    time.sleep(1); enlaces = re.findall(r"https?://\S*/cuentas/verificar/[\w:\-]+", LOG.read_text(errors="ignore").replace("=\n", ""))
    assert enlaces, "no salió el correo de verificación"
    pg.goto(enlaces[-1].replace("http://testserver", BASE)); pg.wait_for_load_state(); paso(2, f"verificación -> {pg.url}")
    if "login" in pg.url:
        pg.fill("input[name=email]", CORREO); pg.locator("form:has(input[name=email]) button[type=submit]").first.click(); pg.wait_for_load_state()
        pg.fill("input[type=password]", "Lienzo-Tardio-73"); pg.locator("form:has(input[type=password]) button[type=submit]").first.click(); pg.wait_for_load_state(); paso("2b", f"login -> {pg.url}")
    assert "onboarding" in pg.url, pg.url
    pg.set_input_files("input[type=file]", str(ruta)); t0 = time.time(); pg.click("button:has-text('Analizar')"); pg.wait_for_load_state(); paso(3, f"CV -> {pg.url} en {time.time()-t0:.2f} s")
    pg.screenshot(path=SAL / "1_perfil.png", full_page=True)
    q = pg.goto(BASE + "/dashboard"); paso(4, f"dashboard {q.status}; 'analizando' visible={'Estamos analizando' in pg.content()}")
    while time.time() - t0 < 60:
        pg.goto(BASE + "/dashboard")
        if "Estamos analizando" not in pg.content(): break
        time.sleep(0.5)
    paso(5, f"decisiones visibles {time.time()-t0:.1f} s después de subir el CV"); pg.screenshot(path=SAL / "2_dashboard.png", full_page=True)
    assert "solidez" in pg.content()
    urls = list(dict.fromkeys(pg.eval_on_selector_all("a[href*='/vacantes/']", "e=>e.map(x=>x.href)")))
    urls = [u for u in urls if re.search(r"/vacantes/[^/]+$", u)]; paso(6, f"{len(urls)} vacantes enlazadas")
    con_taller = None
    for u in urls[:25]:
        pg.goto(u)
        if pg.locator("a[href$='/taller']").count(): con_taller = u; break
    pg.goto(urls[0]); pg.screenshot(path=SAL / "3_detalle.png", full_page=True); paso(7, f"detalle ok; con taller: {con_taller}")
    if con_taller:
        pg.goto(con_taller + "/taller"); pg.screenshot(path=SAL / "4_taller.png", full_page=True); n = pg.locator("textarea[name=respuesta]").count()
        pg.click("button:has-text('Agregar a mi postulación')"); pg.wait_for_load_state(); aviso = "Escribe con tus palabras" in pg.content()
        pg.fill("textarea[name=respuesta]", "Lo usé en mi práctica durante seis meses."); pg.click("button:has-text('Agregar a mi postulación')"); pg.wait_for_load_state()
        paso(8, f"taller: {n} preguntas; aviso sin texto={aviso}; texto para copiar={'Lo usé en mi práctica' in pg.content()}"); pg.screenshot(path=SAL / "5_taller_respondido.png", full_page=True)
    for r in ("/notificaciones", "/historial", "/perfil", "/expectativas", "/privacidad", "/terminos"):
        q = pg.goto(BASE + r); paso("9", f"{r} {q.status}")
    pg.goto(BASE + "/cuenta/eliminar"); pg.screenshot(path=SAL / "6_eliminar.png"); 
    inputs = pg.eval_on_selector_all("form input:not([type=hidden])", "e=>e.map(x=>[x.name,x.type])"); paso(10, f"campos eliminar: {inputs}")
    b.close()
print("respuestas >=400 / errores JS:", malas)
print("CORREO", CORREO)
