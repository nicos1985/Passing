"""Serve uploaded interface images without exposing vault attachments."""

import mimetypes

from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404

from accounts.models import CustomUser, TenantMembership, TenantSettings


@login_required
def private_image(request, media_path):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise Http404

    # TenantFileSystemStorage prefixes URLs with the active schema. The stored
    # name also has the schema recorded by the upload_to functions.
    url_schema, separator, stored_name = media_path.partition("/")
    if not separator or url_schema != tenant.schema_name:
        raise Http404
    parts = stored_name.split("/")
    if len(parts) != 3 or not parts[0] or not parts[2] or ".." in parts or "\\" in stored_name:
        raise Http404

    image_type = parts[1]
    if image_type == "avatars":
        if tenant.schema_name == "public":
            if request.user.avatar.name != stored_name:
                raise Http404
            image = request.user.avatar
        else:
            if not TenantMembership.objects.filter(
                user=request.user, client=tenant, is_active=True,
            ).exists():
                raise Http404
            owner = CustomUser.objects.filter(client=tenant, avatar=stored_name).first()
            if owner is None:
                raise Http404
            image = owner.avatar
    elif image_type == "logos" and tenant.schema_name != "public":
        if not TenantMembership.objects.filter(
            user=request.user, client=tenant, is_active=True,
        ).exists():
            raise Http404
        configuration = TenantSettings.objects.filter(
            client=tenant, company_logo=stored_name,
        ).first()
        if configuration is None:
            raise Http404
        image = configuration.company_logo
    else:
        raise Http404

    content_type, _ = mimetypes.guess_type(stored_name)
    if not content_type or not content_type.startswith("image/") or content_type == "image/svg+xml":
        raise Http404
    try:
        response = FileResponse(image.open("rb"), content_type=content_type)
    except (OSError, ValueError, SuspiciousFileOperation) as exc:
        raise Http404 from exc
    response["Cache-Control"] = "private, no-store"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    return response
