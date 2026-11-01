"""La configuración sensible sale del entorno, nunca del repo.
Cada caso importa settings en un proceso aparte, porque Django la carga una sola vez."""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
CLAVE_VIEJA = 'django-insecure-1(1!@u*m7fmsfkn8d)mp0a2qa22n77%+3-n1$j0z_kiqai55&)'


def cargar_settings(**entorno):
    """Importa scoutly.settings con solo el entorno dado (sin leer el .env local)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    env.update(entorno, SCOUTLY_SIN_DOTENV="1")
    codigo = (
        "import json, scoutly.settings as s;"
        "print(json.dumps({'debug': s.DEBUG, 'key': s.SECRET_KEY, 'hosts': s.ALLOWED_HOSTS,"
        "'cookie_segura': s.SESSION_COOKIE_SECURE, 'csrf_segura': s.CSRF_COOKIE_SECURE}))"
    )
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=env, capture_output=True, text=True)
    return r.returncode, (json.loads(r.stdout) if r.returncode == 0 else r.stderr)


class ConfiguracionSeguraTests(SimpleTestCase):
    def test_debug_apagado_por_defecto(self):
        codigo, s = cargar_settings(DJANGO_SECRET_KEY="x" * 50)
        self.assertEqual(codigo, 0, s)
        self.assertFalse(s["debug"])

    def test_sin_debug_exige_secret_key_del_entorno(self):
        codigo, salida = cargar_settings()
        self.assertNotEqual(codigo, 0)
        self.assertIn("DJANGO_SECRET_KEY", salida)

    def test_la_clave_versionada_ya_no_se_usa(self):
        _, s = cargar_settings(DJANGO_DEBUG="true")
        self.assertNotEqual(s["key"], CLAVE_VIEJA)

    def test_la_clave_viene_del_entorno(self):
        _, s = cargar_settings(DJANGO_SECRET_KEY="k" * 50)
        self.assertEqual(s["key"], "k" * 50)

    def test_hosts_explicitos_sin_comodin(self):
        _, s = cargar_settings(DJANGO_SECRET_KEY="x" * 50)
        self.assertNotIn("*", s["hosts"])
        self.assertIn("localhost", s["hosts"])
        self.assertIn("host.containers.internal", s["hosts"])  # n8n llama desde su contenedor Podman

    def test_cookies_seguras_sin_debug(self):
        _, s = cargar_settings(DJANGO_SECRET_KEY="x" * 50)
        self.assertTrue(s["cookie_segura"])
        self.assertTrue(s["csrf_segura"])

    def test_cookies_normales_en_desarrollo(self):
        _, s = cargar_settings(DJANGO_DEBUG="true")
        self.assertFalse(s["cookie_segura"])
