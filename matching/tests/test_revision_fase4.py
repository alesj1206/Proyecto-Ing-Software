"""Regresiones de la revisión final de la Fase 4 (calidad y seguridad)."""

import json
import os
import stat
from types import SimpleNamespace as N

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from cuentas.models import EvidenciaPerfil
from matching.evaluacion.capturar import sin_contactos
from matching.evaluacion.ciega import asignar, tabular
from matching.restricciones import RestriccionEstudiante

POLITICA = N(factor_experiencia=0.5)


def _estudiante(perfil, educacion, titulo, descripcion=""):
    perfil.evidencias.all().delete()
    for i, t in enumerate(educacion):
        EvidenciaPerfil.objects.create(perfil=perfil, texto=t, seccion="educacion", posicion=i)
    return RestriccionEstudiante().evaluar(perfil, N(titulo=titulo, descripcion=descripcion), POLITICA)


@pytest.mark.parametrize("educacion", [
    "Estudiante de Ingeniería de Sistemas - Universidad EAFIT", "Contaduría Pública (2022 - Actualidad)",
    "Administración de Empresas, 2023 - 2029", "Diseño Gráfico (en progreso)", "Técnico en sistemas (en formación)",
    "Derecho, 2021 – hoy"])
def test_estudiantes_reales_no_se_descartan(client_con_cv, usuario, educacion):
    assert _estudiante(usuario.perfil, [educacion], "Practicante de Diseño").estado == "cumple"


def test_sin_educacion_es_sin_datos(client_con_cv, usuario):
    assert _estudiante(usuario.perfil, [], "Practicante administrativo").estado == "sin_datos"


@pytest.mark.parametrize("titulo", ["Analista de Buenas Prácticas de Manufactura", "Coordinador de prácticas académicas",
                                    "Líder de práctica de consultoría SAP"])
def test_titulos_que_no_son_practicas(client_con_cv, usuario, titulo):
    assert _estudiante(usuario.perfil, ["Tecnología en Diseño"], titulo) is None


def test_practica_profesional_al_inicio_si_aplica(client_con_cv, usuario):
    assert _estudiante(usuario.perfil, ["Tecnología en Diseño"], "Práctica profesional en contabilidad").estado == "no_cumple"


# --- mercado y plan de aprendizaje: solo lo de verdad cercano ------------------------------------------------------

def test_mercado_cuenta_solo_lo_cercano():
    from matching.services import SIMILITUD_CERCANA, _mercado
    cerca = N(accion="POSTULAR", similitud=SIMILITUD_CERCANA + 0.1, vacante=N(salario_min=2, salario_max=3, empresa="A"))
    lejos = N(accion="CERRAR_BRECHA", similitud=SIMILITUD_CERCANA - 0.1, vacante=N(salario_min=9, salario_max=99,
                                                                                    empresa="B"))
    assert _mercado([cerca, lejos]) == {"relevantes": 1, "salario_min": 2, "salario_max": 3, "empresas": [["A", 1]]}


# --- evaluación ciega -----------------------------------------------------------------------------------------------

def test_sorteo_por_defecto_es_secreto():
    claves = [f"cv{i}" for i in range(40)]
    assert asignar(claves, None) != asignar(claves, None)


def test_tabular_reporta_filas_invalidas_y_no_cuenta_duplicados():
    clave = {"1": {"cv": "x", "tiene_cv": False, "listas": {"A": "decisor", "B": "similitud"},
                   "cvs": {"1": "adaptado", "2": "original"}}}
    filas = [{"reclutador": "r1", "paquete": "1", "pregunta": "lista", "eleccion": "A"},
             {"reclutador": "r1", "paquete": "1", "pregunta": "lista", "eleccion": "A"},   # duplicada
             {"reclutador": "total", "paquete": "1", "pregunta": "lista", "eleccion": "B"},  # alias reservado
             {"reclutador": "r2", "paquete": "9", "pregunta": "lista", "eleccion": "B"},     # paquete inexistente
             {"reclutador": "r2", "paquete": "1", "pregunta": "otra", "eleccion": "A"},      # pregunta inválida
             {"reclutador": "r2", "paquete": "1", "pregunta": "cv", "eleccion": "1"},        # el paquete no tiene CV
             {"reclutador": "r3", "paquete": "1", "pregunta": "lista", "eleccion": None}]    # fila corta
    resultado = tabular(filas, clave)
    assert resultado["lista"]["n"] == 1 and resultado["lista"]["decisor"] == 1.0
    assert resultado["errores"] == [3, 4, 5, 6, 7, 8]


def test_la_clave_se_guarda_privada_y_fuera_del_repo(tmp_path, settings, monkeypatch):
    from matching.management.commands import evaluacion_ciega as comando
    monkeypatch.setattr(comando, "_sortear", lambda cvs, semilla: ([], {"1": {}}))
    clave = tmp_path / "secreto" / "clave.json"
    call_command("evaluacion_ciega", "preparar", salida=tmp_path / "paquetes", clave=clave)
    assert stat.S_IMODE(os.stat(clave).st_mode) == 0o600 and stat.S_IMODE(os.stat(clave.parent).st_mode) == 0o700
    with pytest.raises(CommandError, match="fuera del repositorio"):
        call_command("evaluacion_ciega", "preparar", salida=tmp_path / "p2", clave=settings.BASE_DIR / "clave.json")


# --- benchmark: la base real conectada, no el nombre configurado ---------------------------------------------------

def test_benchmark_mira_la_base_conectada(db, monkeypatch):
    from django.db import connection
    monkeypatch.setitem(connection.settings_dict, "NAME", "engaño_bench")  # el nombre dice _bench, la conexión no
    with pytest.raises(CommandError, match="_bench"):
        call_command("benchmark_escala", vacantes=10, muestra=5, candidatos=1, confirmar=True)


def test_benchmark_pide_confirmar(db, monkeypatch):
    from matching.management.commands import benchmark_escala
    monkeypatch.setattr(benchmark_escala, "_base_conectada", lambda: "prueba_bench")
    with pytest.raises(CommandError, match="--confirmar"):
        call_command("benchmark_escala", vacantes=10, muestra=5, candidatos=1)


# --- limpieza de contactos de vacantes capturadas ------------------------------------------------------------------

@pytest.mark.parametrize("texto", ["+573001234567", "https://wa.me/573001234567", "api.whatsapp.com/send?phone=573001234567",
                                   "300.123.4567", "Tel 444 55 66", "cel. 310 555 12 34", "hv [at] empresa.com",
                                   "C.C. 1.036.123.456"])
def test_sin_contactos_cubre_formatos_colombianos(texto):
    limpio = sin_contactos(f"Envía tu hoja de vida: {texto}. Salario $ 1.750.905")
    assert not any(c.isdigit() for c in limpio.split("Salario")[0]) and "empresa.com" not in limpio
    assert "$ 1.750.905" in limpio


def test_plan_de_aprendizaje_ignora_vacantes_lejanas(client_con_cv, usuario, vacante_v1):
    from matching.models import Decision
    from matching.selectors import plan_de_aprendizaje
    from matching.services import SIMILITUD_CERCANA
    falta = [{"texto": "Python", "tipo": "obligatorio", "origen": "texto", "estado": "faltante", "similitud": 0.1,
              "evidencia": ""}]
    Decision.objects.create(perfil=usuario.perfil, vacante=vacante_v1, accion="CERRAR_BRECHA", solidez="media",
                            motivo_solidez="ok", motivos=[], similitud=SIMILITUD_CERCANA - 0.05, cobertura_pct=50,
                            version_politica="t", cobertura=falta, restricciones=[])
    assert plan_de_aprendizaje(usuario.perfil) == []


def test_exportar_rechaza_lo_que_aun_parece_contacto():
    from datetime import date
    from matching.evaluacion.capturar import exportar
    from vacantes.fuentes import VacanteCruda
    sucia = VacanteCruda(id="mag-1", titulo="X", empresa="Y", ubicacion="Cali", modalidad="",
                         texto_completo="Requisitos: SQL. Llamar a la línea 018000 123 456", etiquetas=(), url="u",
                         fecha_publicacion=date(2026, 11, 1))
    rechazadas = []
    assert exportar(type("F", (), {"obtener": lambda self: [sucia]})(), set(), rechazadas) == []
    assert rechazadas == ["mag-1"]


@pytest.mark.parametrize("texto", ["Palabras clave: TI, datos, 1626532605-3", "Vacunador, 224827-36415",
                                   "Asignacion salarial: 1750905 + auxilio", "Salario: Entre 1800000 a 1900000"])
def test_codigos_de_magneto_y_salarios_no_son_sospechosos(texto):
    from matching.evaluacion.capturar import _sospechoso
    assert not _sospechoso(texto)


def test_tabular_rechaza_una_clave_cambiada(tmp_path, monkeypatch):
    from matching.management.commands import evaluacion_ciega as comando
    clave, huella, respuestas = tmp_path / "clave.json", tmp_path / "CLAVE_SHA256.txt", tmp_path / "r.csv"
    clave.write_text(json.dumps({"1": {}}), encoding="utf-8")
    huella.write_text("0" * 64 + "\n", encoding="utf-8")
    respuestas.write_text("reclutador,paquete,pregunta,eleccion\n", encoding="utf-8")
    monkeypatch.setattr(comando, "HUELLA", huella)
    with pytest.raises(CommandError, match="SHA-256"):
        call_command("evaluacion_ciega", "tabular", respuestas=respuestas, clave=clave)
