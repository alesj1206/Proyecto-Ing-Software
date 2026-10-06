import hmac
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, connections
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .ai_explicaciones import guardar_explicacion, resolver_explicacion
from .cv_parser import extraer_datos_cv
from .forms import CVUploadForm, ExpectativasForm
from .matching import compute_match, evaluar_criterios, explicar_match, info_modificador_disponibilidad
from .models import MatchDiario, Perfil, Postulacion, Vacante
from .scoring import recalcular_matches_de_perfil, recalcular_matches_todos

TOP_MATCHES = 3


def _resolver_explicacion_en_hilo(perfil, vacante, criterio):
    """Wrapper para correr resolver_explicacion() (solo lectura/Groq, sin
    escribir) en un hilo del ThreadPoolExecutor de detalle_view. Django
    abre una conexión a la BD por hilo la primera vez que se usa, y no la
    cierra sola cuando el hilo no vive atado al ciclo request/response —
    connections.close_all() aquí evita dejar conexiones SQLite huérfanas."""
    try:
        return resolver_explicacion(perfil, vacante, criterio)
    finally:
        connections.close_all()


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
    criterios = []
    postulacion = None
    modificador = None
    if request.user.is_authenticated:
        perfil = _perfil_con_cv(request.user)
        if perfil:
            criterios_resultado = evaluar_criterios(perfil, vacante)
            modificador = info_modificador_disponibilidad(perfil, vacante)
            score, coincidencias = compute_match(perfil, vacante, modificador=modificador)
            # El detalle de habilidades ya trae "faltantes" calculado —
            # evita recalcularlo aquí con una segunda lista por comprensión
            # que podría divergir si _criterio_habilidades cambia su lógica.
            habilidades_detalle = next(
                c.detalle for c in criterios_resultado if c.criterio == "habilidades"
            )
            match = {
                "score": round(score * 100),
                "coincidencias": coincidencias,
                "faltantes": habilidades_detalle["faltantes"],
                # HU-07 (versión corta, sin IA) — se mantiene por si se
                # necesita en otro lugar; el detalle usa "criterios" abajo.
                "razones": explicar_match(perfil, vacante),
            }

            # Desglose de los 5 criterios, cada uno con su explicación por
            # IA (cacheada — ver vacantes/ai_explicaciones.py). Las
            # llamadas a Groq de los criterios sin caché van en paralelo
            # (en serie, hasta 5 × GROQ_TIMEOUT (8s) podrían sumar ~40s de
            # carga; en paralelo el peor caso queda acotado a
            # ~1×GROQ_TIMEOUT) — pero la escritura en caché NO: SQLite no
            # tolera varios hilos escribiendo a la vez ("database is
            # locked"), así que cada hilo solo lee/llama a Groq
            # (resolver_explicacion) y el hilo principal guarda los
            # resultados uno por uno después, ya sin paralelismo.
            aplicables = [c for c in criterios_resultado if c.aplica]
            explicaciones = {}
            pendientes_de_guardar = []
            if aplicables:
                with ThreadPoolExecutor(max_workers=len(aplicables)) as executor:
                    futuros = {
                        executor.submit(_resolver_explicacion_en_hilo, perfil, vacante, c): c
                        for c in aplicables
                    }
                    for futuro, c in futuros.items():
                        texto, score_a_guardar = futuro.result()
                        explicaciones[c.criterio] = texto
                        if score_a_guardar is not None:
                            pendientes_de_guardar.append((c.criterio, score_a_guardar, texto))

            for criterio_nombre, score_pct, texto in pendientes_de_guardar:
                guardar_explicacion(perfil, vacante, criterio_nombre, score_pct, texto)

            for c in criterios_resultado:
                criterios.append(
                    {
                        "etiqueta": c.etiqueta,
                        "peso_pct": round(c.peso * 100),
                        "score_pct": round(c.score_pct),
                        "aplica": c.aplica,
                        "razon_no_aplica": c.razon_no_aplica,
                        "es_del_candidato": c.es_del_candidato,
                        "explicacion": explicaciones.get(c.criterio),
                    }
                )

            # HU-08: estado del botón "Postularme" — None si nunca aplicó.
            postulacion = Postulacion.objects.filter(perfil=perfil, vacante=vacante).first()

    return render(
        request,
        "vacantes/detalle.html",
        {
            "vacante": vacante,
            "match": match,
            "criterios": criterios,
            "postulacion": postulacion,
            "modificador": modificador,
        },
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
