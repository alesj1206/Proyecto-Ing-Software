from django.db import transaction

from .cv.lector import extraer_texto
from .cv.minimizacion import minimizar
from .cv.secciones import analizar_cv
from .legal import FINALIDAD, VERSION_POLITICA, VERSION_TERMINOS
from .models import Autorizacion, EvidenciaPerfil, Perfil, Usuario


def registrar_autorizacion(usuario: Usuario) -> Autorizacion:
    """Guarda la autorización con las versiones vigentes de la política y los términos."""
    return Autorizacion.objects.create(
        usuario=usuario,
        version_politica=VERSION_POLITICA,
        version_terminos=VERSION_TERMINOS,
        finalidad=FINALIDAD,
    )


@transaction.atomic
def crear_usuario_con_autorizacion(email: str, password: str | None, activo: bool = True) -> Usuario:
    """Nunca existe un usuario sin autorización: los dos se crean en la misma transacción. El registro por correo crea
    la cuenta inactiva hasta verificarla (`activo=False`)."""
    usuario = Usuario.objects.create_user(email=email, password=password, is_active=activo)
    registrar_autorizacion(usuario)
    return usuario


@transaction.atomic
def guardar_perfil_desde_cv(usuario: Usuario, archivo) -> Perfil:
    """Analiza el CV y reemplaza la evidencia del perfil. La evidencia se guarda sin datos personales."""
    cv = analizar_cv(extraer_texto(archivo), archivo.name)
    perfil, _ = Perfil.objects.update_or_create(
        usuario=usuario,
        defaults={
            "nombre": cv.nombre,
            "contacto": cv.contacto,
            "experiencia": cv.experiencia,
            "educacion": cv.educacion or None,
            "habilidades": cv.habilidades,
            "campos_pendientes": cv.campos_pendientes,
            "cv_nombre_archivo": archivo.name,
        },
    )
    perfil.evidencias.all().delete()
    EvidenciaPerfil.objects.bulk_create(
        EvidenciaPerfil(perfil=perfil, texto=minimizar(u.texto, cv.nombre), seccion=u.seccion, posicion=i)
        for i, u in enumerate(cv.unidades)
    )
    return perfil


def eliminar_cuenta(usuario: Usuario) -> None:
    """Supresión total (Ley 1581): todo lo del usuario cuelga de él con on_delete=CASCADE."""
    usuario.delete()
