from types import SimpleNamespace as N

import pytest

from cuentas.models import EvidenciaPerfil
from matching.restricciones import (
    RESTRICCIONES,
    RestriccionEstudiante,
    RestriccionExperiencia,
    RestriccionModalidad,
    RestriccionSalario,
    RestriccionUbicacion,
)

POLITICA = N(factor_experiencia=0.5)


def perfil(**kw):
    base = dict(exp_modalidad="", exp_salario_min=None, exp_ubicacion="", anios_experiencia=None)
    return N(**{**base, **kw})


def vacante(**kw):
    base = dict(modalidad="Presencial", modalidad_inferida=False, salario_max=None, ubicacion="Medellín",
                experiencia_minima=None, titulo="Analista", descripcion="")
    return N(**{**base, **kw})


def estado(restriccion, p, v):
    return restriccion.evaluar(p, v, POLITICA).estado


@pytest.mark.parametrize("vac,busca,esperado", [("Remoto", "Remoto", "cumple"), ("Híbrido", "Remoto", "parcial"),
                                                ("Presencial", "Remoto", "no_cumple"), ("Presencial", "", "sin_datos")])
def test_modalidad(vac, busca, esperado):
    assert estado(RestriccionModalidad(), perfil(exp_modalidad=busca), vacante(modalidad=vac)) == esperado


def test_modalidad_inferida_es_sin_datos():
    assert estado(RestriccionModalidad(), perfil(exp_modalidad="Remoto"),
                  vacante(modalidad="Presencial", modalidad_inferida=True)) == "sin_datos"


def test_salario_bajo_no_cumple_con_motivo():
    r = RestriccionSalario().evaluar(perfil(exp_salario_min=3000000), vacante(salario_max=2000000), POLITICA)
    assert (r.estado, r.motivo, r.valor_pct) == ("no_cumple", "Ofrece $ 2.000.000 y tu mínimo es $ 3.000.000", 0)


@pytest.mark.parametrize("minimo,maximo,esperado", [(3000000, 3500000, "cumple"), (None, 3000000, "sin_datos"),
                                                    (3000000, None, "sin_datos")])
def test_salario(minimo, maximo, esperado):
    assert estado(RestriccionSalario(), perfil(exp_salario_min=minimo), vacante(salario_max=maximo)) == esperado


@pytest.mark.parametrize("vac_modalidad,vac_ubic,busca,esperado", [
    ("Remoto", "Bogotá", "Medellín", "cumple"), ("Presencial", "Medellín", "", "sin_datos"),
    ("Presencial", "Medellín, Antioquia", "medellin, envigado", "cumple"),
    ("Presencial", "Bogotá, D.C.", "Medellín", "no_cumple")])
def test_ubicacion(vac_modalidad, vac_ubic, busca, esperado):
    assert estado(RestriccionUbicacion(), perfil(exp_ubicacion=busca),
                  vacante(modalidad=vac_modalidad, ubicacion=vac_ubic)) == esperado


def test_experiencia_insuficiente_no_cumple_con_motivo():
    r = RestriccionExperiencia().evaluar(perfil(anios_experiencia=1), vacante(experiencia_minima=3), POLITICA)
    assert (r.estado, r.motivo) == ("no_cumple", "Pide 3 años de experiencia y declaraste 1")


@pytest.mark.parametrize("tiene,pide,esperado", [(None, 2, "sin_datos"), (3, None, "cumple"), (2, 2, "cumple"),
                                                 (0, 1, "parcial"), (1, 2, "parcial"), (0, 2, "no_cumple")])
def test_experiencia(tiene, pide, esperado):
    assert estado(RestriccionExperiencia(), perfil(anios_experiencia=tiene), vacante(experiencia_minima=pide)) == esperado


def test_candidato_sin_expectativas_nunca_viola_nada():
    v = vacante(salario_max=1000000, experiencia_minima=5, ubicacion="Bogotá")
    resultados = [r.evaluar(perfil(), v, POLITICA) for r in RESTRICCIONES]
    assert {r.estado for r in resultados if r is not None} <= {"sin_datos", "cumple"}


def test_orden_y_criterios():
    assert [r.criterio for r in RESTRICCIONES] == ["modalidad", "salario", "ubicacion", "experiencia", "estudiante"]


def _estudiante(perfil_db, educacion: list[str], titulo: str, descripcion: str = ""):
    perfil_db.evidencias.all().delete()
    for i, t in enumerate(educacion):
        EvidenciaPerfil.objects.create(perfil=perfil_db, texto=t, seccion="educacion", posicion=i)
    return RestriccionEstudiante().evaluar(perfil_db, vacante(titulo=titulo, descripcion=descripcion), POLITICA)


@pytest.mark.parametrize("titulo,descripcion", [
    ("Practicante de Diseño Gráfico 2027 - 1", ""), ("Aprendiz Diseño Grafico - Marinilla", ""),
    ("Práctica profesional en contabilidad", ""), ("Auxiliar de diseño", "Tipo de contrato: contrato de aprendizaje."),
])
def test_practica_exige_estudiante(client_con_cv, usuario, titulo, descripcion):
    r = _estudiante(usuario.perfil, ["Tecnología en Diseño Gráfico, Pascual Bravo"], titulo, descripcion)
    assert (r.estado, r.motivo) == ("no_cumple", "La vacante es para estudiantes y tu CV no muestra estudios en curso")


@pytest.mark.parametrize("educacion", ["Diseño Gráfico, cursando 7.º semestre", "Tecnología en Diseño (en curso)",
                                       "Contaduría Pública, Universidad de Antioquia (2023 - actualmente)",
                                       "Técnico en sistemas, SENA, 2025 - a la fecha"])
def test_estudiante_en_curso_no_se_descarta(client_con_cv, usuario, educacion):
    assert _estudiante(usuario.perfil, [educacion], "Practicante de Diseño Gráfico").estado == "cumple"


@pytest.mark.parametrize("titulo,descripcion", [
    ("Asistente Administrativo", "Formación: técnico, tecnólogo o estudiante de carreras administrativas."),
    ("Desarrollador de Software", "Alta capacidad de aprendizaje y trabajo en equipo."),
])
def test_vacante_normal_no_aplica(client_con_cv, usuario, titulo, descripcion):
    assert _estudiante(usuario.perfil, ["Tecnología en Diseño Gráfico"], titulo, descripcion) is None
