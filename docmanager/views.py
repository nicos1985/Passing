import json
import urllib.parse

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .forms import IntegrationCredentialForm
from .models import DocumentoControlado, IntegrationCredential
from .services import GoogleDriveService, GoogleDriveServiceError
from .tasks import process_drive_change


@csrf_exempt
def drive_webhook_receiver(request):
	"""Endpoint que recibe notificaciones push de Google Drive.

	Google envía headers `X-Goog-Resource-ID`, `X-Goog-Channel-ID`, `X-Goog-Resource-State`.
	Solo aceptamos POST y encolamos la sincronización para no bloquear el webhook.
	"""

	if request.method != "POST":
		return HttpResponseNotAllowed(["POST"])

	resource_id = request.headers.get("X-Goog-Resource-Id") or request.headers.get("X-Goog-Resource-ID")
	channel_id = request.headers.get("X-Goog-Channel-Id")
	resource_state = request.headers.get("X-Goog-Resource-State")

	if not resource_id:
		return HttpResponseBadRequest("Falta X-Goog-Resource-Id en el webhook")

	process_drive_change.delay(resource_id, channel_id=channel_id, state=resource_state)
	return HttpResponse(status=204)


class DocumentInsightsView(View):
	"""Devuelve un resumen tipo semáforo y quick insights."""

	def get(self, request, *args, **kwargs):
		qs = DocumentoControlado.objects.all()

		# Filtro opcional por carpeta
		folder = request.GET.get("carpeta")
		if folder:
			qs = qs.filter(carpeta_drive_id=folder)

		summary = {"al_dia": 0, "proximo": 0, "vencido": 0, "sin_datos": 0, "no_encontrado": 0}
		highlights = []
		items = []

		for doc in qs:
			estado = doc.estado_cumplimiento
			if estado in summary:
				summary[estado] += 1
			items.append(
				{
					"id": doc.id,
					"nombre": doc.nombre_archivo,
					"estado": estado,
					"color": doc.semaforo_color,
					"link_edicion": doc.link_edicion,
					"dias_restantes": doc.dias_restantes,
				}
			)

		if summary["vencido"]:
			highlights.append(f"Tienes {summary['vencido']} documentos vencidos.")
		if summary["proximo"]:
			highlights.append(f"Tienes {summary['proximo']} documentos próximos a vencer.")

		payload = {
			"resumen": summary,
			"highlights": highlights,
			"documentos": items,
		}
		return JsonResponse(payload)


def _is_staff(user):
	return user.is_staff or user.is_superuser


@login_required
@user_passes_test(_is_staff)
def drive_credential_view(request):
	"""Vista para cargar/actualizar la credencial de Google Drive."""

	instance = (
		IntegrationCredential.objects.filter(service=IntegrationCredential.Service.GOOGLE_DRIVE)
		.order_by("-updated_at")
		.first()
	)

	if request.method == "POST":
		form = IntegrationCredentialForm(request.POST, instance=instance)
		if form.is_valid():
			obj = form.save(commit=False)
			if not obj.created_by:
				obj.created_by = request.user
			obj.save()
			messages.success(request, "Credencial de Google Drive guardada correctamente.")
			return redirect("config")
	else:
		form = IntegrationCredentialForm(instance=instance)

	return render(
		request,
		"docmanager/drive_credential_form.html",
		{"form": form, "instance": instance},
	)


@login_required
@user_passes_test(_is_staff)
def drive_status_view(request):
	"""Pantalla de consulta del estado de la conexión con Google Drive."""

	credential = (
		IntegrationCredential.objects.filter(service=IntegrationCredential.Service.GOOGLE_DRIVE)
		.order_by("-updated_at")
		.first()
	)

	about = None
	error = None

	if credential and request.GET.get("probar"):
		try:
			service = GoogleDriveService(credential)
			about = service.about()
		except GoogleDriveServiceError as exc:
			error = str(exc)
			messages.error(request, "No se pudo consultar Drive. Revisa la credencial.")

	context = {
		"credential": credential,
		"about": about,
		"error": error,
	}
	return render(request, "docmanager/drive_status.html", context)


@login_required
@user_passes_test(_is_staff)
def drive_browser_view(request):
	"""Lista archivos/carpetas de un folder de Drive usando la credencial activa."""

	folder_id = request.GET.get("folder", "root")
	current_name = urllib.parse.unquote(request.GET.get("name", "root"))
	try:
		trail = json.loads(request.GET.get("path", "[]"))
		if not isinstance(trail, list):
			trail = []
	except Exception:
		trail = []

	credential = (
		IntegrationCredential.objects.filter(service=IntegrationCredential.Service.GOOGLE_DRIVE)
		.order_by("-updated_at")
		.first()
	)

	items = []
	error = None
	navigate_trail = trail + [{"id": folder_id, "name": current_name}]
	breadcrumbs = []

	# Construir breadcrumb con URLs válidas
	prev_path: list[dict] = []
	for idx, crumb in enumerate(navigate_trail):
		crumb_name = crumb.get("name") or "(sin nombre)"
		url = f"?folder={crumb.get('id')}&name={urllib.parse.quote(crumb_name)}&path={urllib.parse.quote(json.dumps(prev_path))}"
		breadcrumbs.append({"name": crumb_name, "url": url, "current": idx == len(navigate_trail) - 1})
		prev_path.append({"id": crumb.get("id"), "name": crumb_name})

	if credential:
		try:
			service = GoogleDriveService(credential)
			raw_items = service.listar_carpeta(folder_id)
			items = []
			for it in raw_items:
				is_folder = it.get("mimeType") == "application/vnd.google-apps.folder"
				web_link = it.get("webViewLink") or (
					f"https://drive.google.com/drive/folders/{it.get('id')}" if is_folder else f"https://drive.google.com/file/d/{it.get('id')}/view"
				)
				navigate_url = None
				if is_folder:
					new_path = urllib.parse.quote(json.dumps(navigate_trail))
					name_qs = urllib.parse.quote(it.get("name") or "")
					navigate_url = f"?folder={it.get('id')}&name={name_qs}&path={new_path}"

				# Selección de ícono + etiqueta simple
				icon_class = "fa-regular fa-file text-secondary"
				display_type = "file"
				if is_folder:
					icon_class = "fa-solid fa-folder text-warning"
					display_type = "folder"
				else:
					name_lower = (it.get("name") or "").lower()
					ext = name_lower.rsplit(".", 1)[-1] if "." in name_lower else ""
					mime = it.get("mimeType") or ""
					if mime == "application/pdf" or ext == "pdf":
						icon_class = "fa-solid fa-file-pdf text-danger"
						display_type = "document"
					elif ext in {"doc", "docx"}:
						icon_class = "fa-solid fa-file-word text-primary"
						display_type = "document"
					elif ext in {"xls", "xlsx", "csv"}:
						icon_class = "fa-solid fa-file-excel text-success"
						display_type = "spreadsheet"
					elif ext in {"ppt", "pptx"}:
						icon_class = "fa-solid fa-file-powerpoint text-warning"
						display_type = "presentation"
					elif ext in {"txt"}:
						icon_class = "fa-solid fa-file-lines text-secondary"
						display_type = "text"
					elif ext in {"zip", "rar", "7z"}:
						icon_class = "fa-solid fa-file-zipper text-secondary"
						display_type = "compressed"
					elif ext in {"mp4", "mov", "mkv", "avi"}:
						icon_class = "fa-solid fa-file-video text-info"
						display_type = "video"
					elif ext in {"mp3", "wav", "aac", "flac"}:
						icon_class = "fa-solid fa-file-audio text-info"
						display_type = "audio"
					elif ext in {"png", "jpg", "jpeg", "gif", "webp", "svg"}:
						icon_class = "fa-solid fa-file-image text-info"
						display_type = "image"

				modified = it.get("modifiedTime")
				created = it.get("createdTime")
				modified_dt = parse_datetime(modified) if modified else None
				created_dt = parse_datetime(created) if created else None
				if modified_dt and timezone.is_naive(modified_dt):
					modified_dt = timezone.make_aware(modified_dt)
				if created_dt and timezone.is_naive(created_dt):
					created_dt = timezone.make_aware(created_dt)

				items.append(
					{
						"id": it.get("id"),
						"name": it.get("name") or "(sin nombre)",
						"mimeType": it.get("mimeType"),
						"display_type": display_type,
						"modifiedTime": modified_dt or modified,
						"createdTime": created_dt or created,
						"lastModifyingUser": it.get("lastModifyingUser"),
						"webViewLink": web_link,
						"navigate_url": navigate_url,
						"is_folder": is_folder,
						"icon_class": icon_class,
					}
				)
		except GoogleDriveServiceError as exc:
			error = str(exc)
	else:
		error = "No hay credencial configurada."

	context = {
		"folder_id": folder_id,
		"items": items,
		"error": error,
		"credential": credential,
		"breadcrumbs": breadcrumbs,
	}
	return render(request, "docmanager/drive_browser.html", context)


@login_required
@user_passes_test(_is_staff)
def drive_revisions_view(request):
	file_id = request.GET.get("file_id")
	if not file_id:
		return HttpResponseBadRequest("Se requiere file_id")

	credential = (
		IntegrationCredential.objects.filter(service=IntegrationCredential.Service.GOOGLE_DRIVE)
		.order_by("-updated_at")
		.first()
	)

	if not credential:
		return HttpResponseBadRequest("No hay credencial activa")

	revisions = []
	error = None

	def _human_size(num: int) -> str:
		units = ["B", "KB", "MB", "GB", "TB"]
		step = 1024.0
		n = float(num)
		i = 0
		while n >= step and i < len(units) - 1:
			n /= step
			i += 1
		return f"{n:.1f} {units[i]}"

	try:
		service = GoogleDriveService(credential)
		revisions = service.list_revisions(file_id)
		parsed = []
		for rev in revisions:
			mod = rev.get("modifiedTime")
			mod_dt = parse_datetime(mod) if mod else None
			if mod_dt and timezone.is_naive(mod_dt):
				mod_dt = timezone.make_aware(mod_dt)

			size_val = rev.get("size")
			try:
				size_int = int(size_val) if size_val is not None else None
			except (TypeError, ValueError):
				size_int = None

			rev["modified_dt"] = mod_dt
			rev["size_int"] = size_int
			rev["size_human"] = _human_size(size_int) if size_int is not None else None
			user = rev.get("lastModifyingUser") or {}
			rev["editor"] = user.get("displayName") or user.get("emailAddress") or "-"
			parsed.append(rev)
		revisions = parsed
	except GoogleDriveServiceError as exc:
		error = str(exc)

	context = {
		"file_id": file_id,
		"revisions": revisions,
		"error": error,
	}
	return render(request, "docmanager/drive_revisions.html", context)

