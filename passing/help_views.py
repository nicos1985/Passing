"""Tenant help pages for the main navigation modules."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from login.utils import user_belongs_to_current_tenant
from .help_content import HELP_ORDER, HELP_TOPICS


LANDING_CHOICES = {
    "recursos": (
        ("resources.view_informationassets", "informationassets-list"),
        ("resources.view_vendor", "vendor-list"),
        ("resources.view_project", "project-list"),
        ("resources.view_clientcompany", "clientcompany-list"),
    ),
    "riesgos": (
        ("resources.view_riskevaluation", "evaluation-list"),
        ("resources.view_threat", "threat-list"),
        ("resources.view_vulnerability", "vulnerability-list"),
        ("resources.view_treatment", "treatment-list"),
    ),
    "inteligencia": (
        ("threat_intel.view_run", "threat_intel:run-list"),
        ("threat_intel.view_aianalysis", "threat_intel:analysis-list"),
        ("threat_intel.view_report", "threat_intel:report-list"),
        ("threat_intel.view_review", "threat_intel:review-list"),
        ("threat_intel.view_source", "threat_intel:config"),
    ),
    "soporte": (
        ("supporthub.view_support_inbox", "supporthub:inbox"),
        ("supporthub.create_support", "supporthub:settings"),
        ("supporthub.edit_support", "supporthub:settings"),
        ("supporthub.delete_support", "supporthub:settings"),
    ),
}


def _landing_name(user, slug):
    if slug == "configuracion":
        return "config" if user.is_staff or user.is_superuser else None
    if slug == "monitorizacion":
        if user.is_superuser or user.has_perm("monitoring.read_monitoring") or user.has_perm("monitoring.manage_monitoring"):
            return "monitoring:dashboard"
        return "monitoring:status"
    choices = LANDING_CHOICES.get(slug)
    if choices:
        for permission, name in choices:
            if user.is_superuser or (slug in ("recursos", "riesgos") and user.is_staff) or user.has_perm(permission):
                return name
        return None
    return HELP_TOPICS[slug]["landing"]


@login_required
def module_help(request, slug):
    if slug not in HELP_TOPICS:
        raise Http404("Guía no encontrada")
    if not user_belongs_to_current_tenant(request.user):
        raise PermissionDenied

    landing_name = _landing_name(request.user, slug)
    if landing_name is None:
        raise PermissionDenied

    modules = []
    for module_slug in HELP_ORDER:
        module_landing = _landing_name(request.user, module_slug)
        modules.append({
            "slug": module_slug,
            "title": HELP_TOPICS[module_slug]["title"],
            "lead": HELP_TOPICS[module_slug]["lead"],
            "icon": HELP_TOPICS[module_slug]["icon"],
            "url": reverse("module_help", args=[module_slug]) if module_landing else None,
        })

    return render(request, "help/module.html", {
        "topic": HELP_TOPICS[slug],
        "slug": slug,
        "landing_url": reverse(landing_name),
        "modules": modules,
    })
