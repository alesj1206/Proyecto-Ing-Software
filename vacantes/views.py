import hmac

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .cv_parser import extraer_datos_cv
from .forms import CVUploadForm, ExpectativasForm
from .matching import compute_match, explicar_match
from .models import MatchDiario, Perfil, Postulacion, Vacante
from .scoring import recalcular_matches_de_perfil, recalcular_matches_todos

TOP_MATCHES = 3


def _guardar_perfil_desde_cv(usuario, archivo):
    datos = extraer_datos_cv(archivo)
    perfil, _ = Perfil.objects.update_or_create(
        usuario=usuario,
        defaults={**datos, "cv_nombre_archivo": archivo.name},
    )
    # HU-06: no esperar al próximo ciclo del workflow de n8n — un CV nuevo
    # cambia las habilidades, así que el ranking de hoy debe reflejarlo ya.
    recalcular_matches_de_perfil(perfil)
    return perfil


def _perfil_con_cv(usuario):
    """Perfil solo si tiene una hoja de vida cargada. expectativas_view crea
    un Perfil vacío (cv_nombre_archivo="") la primera vez que alguien visita
    /expectativas sin haber pasado por onboarding — ese registro no cuenta
    como "ya tiene CV" para el resto de la app (dashboard, detalle)."""
    perfil = Perfil.objects.filter(usuario=usuario).first()
    if perfil and not perfil.tiene_cv():
        return None
    return perfil


@login_required
def onboarding_view(request):
    form = CVUploadForm()

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            _guardar_perfil_desde_cv(request.user, form.cleaned_data["cv"])
            return redirect("perfil")

    return render(request, "vacantes/onboarding.html", {"form": form})


@login_required
def perfil_view(request):
    form = CVUploadForm()

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            _guardar_perfil_desde_cv(request.user, form.cleaned_data["cv"])
            return redirect("perfil")

    perfil = _perfil_con_cv(request.user)
    return render(request, "vacantes/perfil.html", {"perfil": perfil, "form": form})


@login_required
def expectativas_view(request):
    perfil, _ = Perfil.objects.get_or_create(
        usuario=request.user, defaults={"cv_nombre_archivo": ""}
    )

    if request.method == "POST":
        form = ExpectativasForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            # HU-06: las expectativas pesan en el score (matching.py); si el
            # candidato ya tiene CV, su ranking de hoy debe reflejar el
            # cambio de una vez, no esperar al próximo corrido de n8n.
            if perfil.tiene_cv():
                recalcular_matches_de_perfil(perfil)
            return redirect("expectativas")
    else:
        form = ExpectativasForm(instance=perfil)

    return render(request, "vacantes/expectativas.html", {"form": form, "perfil": perfil})


@login_required
def dashboard_view(request):
    perfil = _perfil_con_cv(request.user)
    todas_vacantes = list(Vacante.objects.all())

    top_matches = []
    if perfil:
        hoy = timezone.localdate()
        matches_hoy = MatchDiario.objects.filter(perfil=perfil, fecha=hoy)
        if not matches_hoy.exists():
            # El workflow de n8n todavía no corrió hoy para este perfil (p.
            # ej. en desarrollo local, o si el candidato es nuevo desde la
            # última corrida) — se calcula y persiste aquí mismo para no
            # dejar el dashboard vacío esperando al próximo ciclo.
            recalcular_matches_de_perfil(perfil, fecha=hoy)
            matches_hoy = MatchDiario.objects.filter(perfil=perfil, fecha=hoy)

        top_matches = []
        for m in matches_hoy.select_related("vacante").order_by("-score")[:TOP_MATCHES]:
            razones = explicar_match(perfil, m.vacante)
            top_matches.append(
                {
                    "vacante": m.vacante,
                    "score_pct": round(m.score * 100),
                    "coincidencias": m.coincidencias,
                    # HU-07: solo la razón más fuerte en la tarjeta del
                    # dashboard — la lista completa va en el detalle.
                    "razon_principal": razones[0] if razones else None,
                }
            )

    modalidad_activa = request.GET.get("modalidad", "")
    vacantes = (
        [v for v in todas_vacantes if v.modalidad == modalidad_activa]
        if modalidad_activa
        else todas_vacantes
    )

    return render(
        request,
        "vacantes/dashboard.html",
        {
            "perfil": perfil,
            "top_matches": top_matches,
            "vacantes": vacantes,
            # Total de la plataforma, no del filtro activo — el filtro ya se
            # ve reflejado en cuántas filas trae la lista de abajo.
            "total_vacantes": len(todas_vacantes),
            "modalidades": Vacante.Modalidad.choices,
            "modalidad_activa": modalidad_activa,
        },
    )


def detalle_view(request, vacante_id):
    vacante = get_object_or_404(Vacante, id=vacante_id)

    match = None
    postulacion = None
    if request.user.is_authenticated:
        perfil = _perfil_con_cv(request.user)
        if perfil:
            score, coincidencias = compute_match(perfil, vacante)
            faltantes = [r for r in vacante.requisitos if r not in coincidencias]
            match = {
                "score": round(score * 100),
                "coincidencias": coincidencias,
                "faltantes": faltantes,
                # HU-07
                "razones": explicar_match(perfil, vacante),
            }
            # HU-08: estado del botón "Postularme" — None si nunca aplicó.
            postulacion = Postulacion.objects.filter(perfil=perfil, vacante=vacante).first()

    return render(
        request,
        "vacantes/detalle.html",
        {"vacante": vacante, "match": match, "postulacion": postulacion},
    )


@login_required
@require_POST
def postular_view(request, vacante_id):
    """HU-08: postulación simulada — no hay integración real con Magneto,
    solo un registro con timestamp (evidencia) que además alimenta el
    tablero de HU-10. Idempotente: postularse dos veces a la misma vacante
    no crea una segunda fila ni reinicia el estado."""
    vacante = get_object_or_404(Vacante, id=vacante_id)
    perfil = _perfil_con_cv(request.user)
    if not perfil:
        messages.error(request, "Carga tu hoja de vida antes de postularte.")
        return redirect("vacante_detalle", vacante_id=vacante_id)

    try:
        _, creada = Postulacion.objects.get_or_create(perfil=perfil, vacante=vacante)
    except IntegrityError:
        # Doble clic / dos pestañas: ambas peticiones pasan el SELECT de
        # get_or_create antes de que la primera confirme su INSERT. La
        # segunda choca con el UniqueConstraint — se trata igual que
        # "ya te habías postulado" en vez de devolver un 500.
        creada = False

    if creada:
        messages.success(request, f'Postulación registrada para "{vacante.titulo}".')
    else:
        messages.info(request, "Ya te habías postulado a esta vacante.")

    return redirect("vacante_detalle", vacante_id=vacante_id)


@login_required
def tablero_view(request):
    """HU-10: tablero Kanban de las postulaciones del candidato, agrupadas
    por estado en las 4 columnas mínimas que pide la historia."""
    perfil = _perfil_con_cv(request.user)
    postulaciones = (
        Postulacion.objects.filter(perfil=perfil).select_related("vacante")
        if perfil
        else Postulacion.objects.none()
    )

    columnas = [
        {"estado": valor, "etiqueta": etiqueta, "postulaciones": []}
        for valor, etiqueta in Postulacion.Estado.choices
    ]
    columnas_por_estado = {c["estado"]: c for c in columnas}
    for p in postulaciones:
        columnas_por_estado[p.estado]["postulaciones"].append(p)

    return render(
        request,
        "vacantes/tablero.html",
        {"columnas": columnas, "perfil": perfil, "estados": Postulacion.Estado.choices},
    )


@login_required
@require_POST
def cambiar_estado_postulacion_view(request, postulacion_id):
    """HU-10: mover una tarjeta del tablero a otra columna. "Simulado" como
    el resto de HU-08 — quien decide el estado en este sprint es el propio
    candidato, no hay bandeja del lado de la empresa todavía."""
    perfil = _perfil_con_cv(request.user)
    postulacion = get_object_or_404(Postulacion, id=postulacion_id, perfil=perfil)

    nuevo_estado = request.POST.get("estado", "")
    if nuevo_estado not in Postulacion.Estado.values:
        messages.error(request, "Estado inválido.")
        return redirect("tablero")

    postulacion.estado = nuevo_estado
    postulacion.save(update_fields=["estado", "actualizado_en"])
    messages.success(request, f'"{postulacion.vacante.titulo}" movida a {postulacion.get_estado_display()}.')
    return redirect("tablero")


@csrf_exempt
@require_POST
def recalcular_matches_api(request):
    """HU-06: punto de entrada que dispara el workflow de n8n (Schedule
    Trigger → HTTP Request, una vez al día). csrf_exempt porque la llamada
    no viene de un navegador con sesión — la autenticación es el token
    compartido, no la cookie de sesión."""
    token_configurado = settings.N8N_SCORING_TOKEN
    # Con DEBUG=False (producción/demo pública), el valor de desarrollo
    # está en el repo en texto plano — aceptar peticiones contra él sería
    # un secreto público. Si nadie puso N8N_SCORING_TOKEN real, el endpoint
    # se cierra en vez de quedar "protegido" por una contraseña conocida.
    if not settings.DEBUG and token_configurado == settings.N8N_SCORING_TOKEN_DEV_DEFAULT:
        return JsonResponse({"error": "N8N_SCORING_TOKEN no configurado"}, status=503)

    token_recibido = request.headers.get("X-Scoutly-Token", "")
    if not token_configurado or not hmac.compare_digest(token_recibido, token_configurado):
        return JsonResponse({"error": "no autorizado"}, status=401)

    resultado = recalcular_matches_todos()
    return JsonResponse(
        {
            "ok": True,
            "fecha": resultado["fecha"].isoformat(),
            "perfiles_procesados": resultado["perfiles_procesados"],
            "matches_guardados": resultado["matches_guardados"],
        }
    )
