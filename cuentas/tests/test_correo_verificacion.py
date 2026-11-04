"""El correo de verificación usa el mismo diseño que los avisos y conserva el enlace también en texto plano."""

import re

from django.core import mail

from cuentas.tests.test_verificacion import _registrar, cache_limpia  # noqa: F401 (fixture)


def _html(correo) -> str:
    return next(contenido for contenido, tipo in correo.alternatives if tipo == "text/html")


def _enlace(correo) -> str:
    return re.search(r"https?://\S+/cuentas/verificar/\S+", correo.body).group(0)


def test_el_boton_lleva_al_mismo_enlace_del_texto_plano(client, db):
    _registrar(client)
    correo = mail.outbox[-1]
    assert f'href="{_enlace(correo)}"' in _html(correo)


def test_el_enlace_tambien_se_ve_escrito_por_si_el_boton_no_abre(client, db):
    _registrar(client)
    correo = mail.outbox[-1]
    html = _html(correo)
    assert html.count(_enlace(correo)) == 2


def test_dice_cuanto_dura_y_que_hacer_si_no_te_registraste(client, db):
    _registrar(client)
    correo = mail.outbox[-1]
    for texto in (correo.body, _html(correo)):
        assert "3 días" in texto and "ignora este correo" in texto


def test_comparte_el_diseno_de_los_avisos(client, db):
    _registrar(client)
    html = _html(mail.outbox[-1])
    assert "linear-gradient(135deg,#9140fe" in html and "Confirmar mi correo" in html
