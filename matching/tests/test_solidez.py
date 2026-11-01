from types import SimpleNamespace as N

from matching.cobertura import Cobertura, RequisitoEvaluado
from matching.politica import POLITICA, ContextoDecision, decidir
from matching.restricciones import ResultadoRestriccion
from matching.solidez import calcular_solidez

ORDEN = {"baja": 0, "media": 1, "alta": 2}


def req(texto, sim=0.7, estado="cubierto"):
    return RequisitoEvaluado(texto, "obligatorio", "texto", estado, sim, "evidencia")


def ctx(requisitos, sin_datos=0):
    restricciones = [ResultadoRestriccion("salario", "sin_datos", "La vacante no dice el salario")] * sin_datos
    restricciones += [ResultadoRestriccion("modalidad", "cumple", "ok")]
    return ContextoDecision(Cobertura(requisitos), restricciones, [N(origen="texto")] * len(requisitos), POLITICA)


def solidez(contexto):
    return calcular_solidez(contexto, decidir(contexto))


CINCO = [req(t) for t in ("a", "b", "c", "d", "e")]


def test_datos_completos_y_claros_es_alta():
    assert solidez(ctx(CINCO))[0] == "alta"


def test_solidez_es_monotona_en_datos_faltantes():
    niveles = [ORDEN[solidez(ctx(CINCO, n))[0]] for n in range(4)]
    assert niveles == sorted(niveles, reverse=True)


def test_el_motivo_nombra_el_dato_que_falta():
    assert solidez(ctx(CINCO, 1)) == ("media", "La vacante no dice el salario")


def test_solidez_baja_cerca_del_umbral():
    assert ORDEN[solidez(ctx(CINCO[:4] + [req("e", sim=0.51)]))[0]] < ORDEN["alta"]


def test_pocos_requisitos_baja_la_solidez():
    assert solidez(ctx(CINCO[:2]))[0] == "baja"


def test_sin_datos_siempre_baja():
    assert solidez(ctx(CINCO[:1]))[0] == "baja"
