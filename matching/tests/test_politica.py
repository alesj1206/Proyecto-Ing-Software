from types import SimpleNamespace as N

from matching.cobertura import Cobertura, RequisitoEvaluado
from matching.politica import POLITICA, Accion, ContextoDecision, decidir
from matching.restricciones import ResultadoRestriccion


def r(texto, estado, tipo="obligatorio", origen="texto", sim=0.6, evidencia="mi evidencia"):
    return RequisitoEvaluado(texto, tipo, origen, estado, sim, evidencia if estado in ("cubierto", "parcial") else None)


def ok(criterio="salario"):
    return ResultadoRestriccion(criterio, "cumple", "bien")


def ctx(requisitos, restricciones=None):
    extraidos = [N(origen=x.origen) for x in requisitos]
    return ContextoDecision(Cobertura(requisitos), restricciones or [ok()], extraidos, POLITICA)


CUBIERTOS = [r("SQL", "cubierto"), r("Excel", "cubierto"), r("Power BI", "cubierto")]


def test_postular_si_cubre_todo():
    v = decidir(ctx(CUBIERTOS))
    assert (v.accion, v.con_nota) == (Accion.POSTULAR, None) and v.motivos == ["Cubres 3/3 obligatorios"]


def test_descartar_por_restriccion_con_su_motivo():
    v = decidir(ctx(CUBIERTOS, [ResultadoRestriccion("salario", "no_cumple", "Ofrece poco")]))
    assert (v.accion, v.motivos) == (Accion.DESCARTAR, ["Ofrece poco"])


def test_sin_datos_si_hay_menos_de_dos_requisitos_de_texto():
    v = decidir(ctx([r("SQL", "cubierto"), r("Docker", "faltante", "deseable", "etiqueta")]))
    assert v.accion == Accion.SIN_DATOS


def test_orden_de_la_cadena_restriccion_gana_a_sin_datos():
    v = decidir(ctx([r("SQL", "cubierto")], [ResultadoRestriccion("salario", "no_cumple", "Ofrece poco")]))
    assert v.accion == Accion.DESCARTAR


def test_descartar_con_tres_faltantes():
    v = decidir(ctx(CUBIERTOS + [r("a b", "faltante"), r("c d", "faltante"), r("e f", "faltante")]))
    assert (v.accion, v.motivos) == (Accion.DESCARTAR, ["Te faltan 3 requisitos obligatorios"])


def test_cerrar_brecha_con_uno_o_dos_faltantes():
    v = decidir(ctx([r("SQL", "cubierto"), r("Docker en producción con Kubernetes", "faltante"),
                     r("Inglés avanzado conversacional fluido", "faltante")]))
    assert v.accion == Accion.CERRAR_BRECHA and "Te falta: Docker en producción con Kubernetes" in v.motivos


def test_ajustar_cv_lleva_el_texto_y_la_evidencia():
    v = decidir(ctx([r("SQL", "cubierto"), r("Power BI", "parcial", evidencia="Hice tableros en Excel")]))
    assert v.accion == Accion.AJUSTAR_CV
    assert v.motivos == ["Haz explícito «Power BI» (tu evidencia: «Hice tableros en Excel»)"]


def test_postular_con_nota_solo_si_cobertura_alta_y_un_faltante_corto():
    cuatro = CUBIERTOS + [r("Atención al cliente", "cubierto")]
    v = decidir(ctx(cuatro + [r("Canva", "faltante")]))
    assert (v.accion, v.con_nota) == (Accion.POSTULAR, "Menciona que puedes aprender Canva rápido")
    largo = decidir(ctx(cuatro + [r("Experiencia liderando equipos de diseño", "faltante")]))
    assert largo.accion == Accion.CERRAR_BRECHA
    baja = decidir(ctx([r("SQL", "cubierto"), r("Excel", "parcial"), r("Canva", "faltante")]))
    assert baja.accion == Accion.CERRAR_BRECHA


def test_etiqueta_faltante_no_bloquea():
    v = decidir(ctx(CUBIERTOS + [r("Docker", "faltante", "deseable", "etiqueta")]))
    assert v.accion == Accion.POSTULAR


def test_formacion_faltante_no_genera_ajustar_cv():
    v = decidir(ctx(CUBIERTOS + [r("Técnico en sistemas", "formacion")]))
    assert v.accion == Accion.POSTULAR
