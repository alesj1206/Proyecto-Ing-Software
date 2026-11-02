from matching.formato import pesos


def test_pesos_formatea_con_puntos():
    assert pesos(3500000) == "$ 3.500.000"
